from __future__ import annotations

import json
import os
import socket
import ssl
import time
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import httplib2
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from . import usage_tracker

SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]

YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"


# Network-level failures that are worth retrying (e.g. SSLEOFError, which is an
# OSError subclass and NOT an HttpError, so it previously bypassed our wrapper).
TRANSIENT_NET_ERRORS = (
    ssl.SSLError,
    socket.error,
    ConnectionError,
    TimeoutError,
    httplib2.HttpLib2Error,
)
TRANSIENT_HTTP_STATUSES = (429, 500, 502, 503, 504)


class VideoStatusCheckError(Exception):
    """
    Raised by get_video_status() when the Data API call itself failed
    (auth, quota, transient network/server error) — as opposed to a
    normal 200 response confirming the video genuinely doesn't exist.
    Callers must not treat this the same as "video not found".
    """


class YouTubePublisher:
    def __init__(
        self,
        credentials_path: str = "credentials.json",
        token_path: str = "token.json",
    ):
        self.credentials_path = Path(credentials_path)
        self.token_path = Path(token_path)
        self.youtube = None
        self.credentials: Optional[Credentials] = None  # exposed so engines/analytics.py can reuse this OAuth session

    def authenticate(self, interactive: bool = True):
        """
        NOTE: SCOPES now includes yt-analytics.readonly (added for
        engines/analytics.py's 48h performance tracking) on top of the
        original upload scope. A token.json/YOUTUBE_TOKEN_JSON minted
        before that addition only has the old scope and will need ONE
        fresh interactive re-auth (`python main.py auth`) to pick up the
        new one — Google doesn't silently widen an existing token's scope.
        """
        creds: Optional[Credentials] = None

        # GitHub Actions can provide the already-authorized token as JSON.
        token_json = os.getenv("YOUTUBE_TOKEN_JSON")
        if token_json:
            creds = Credentials.from_authorized_user_info(
                json.loads(token_json),
                SCOPES,
            )

        elif self.token_path.exists():
            creds = Credentials.from_authorized_user_file(
                str(self.token_path),
                SCOPES,
            )

        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())

        if not creds or not creds.valid:
            if not interactive:
                raise RuntimeError(
                    "No valid YouTube credentials available in non-interactive mode."
                )

            if not self.credentials_path.exists():
                raise FileNotFoundError(
                    "credentials.json not found. Create a Google OAuth Desktop App "
                    "credential and place the downloaded file here."
                )

            flow = InstalledAppFlow.from_client_secrets_file(
                str(self.credentials_path),
                SCOPES,
            )
            creds = flow.run_local_server(port=0)

        if not self.token_path.exists() and not os.getenv("YOUTUBE_TOKEN_JSON"):
            self.token_path.write_text(creds.to_json(), encoding="utf-8")

        self.youtube = build(
            YOUTUBE_API_SERVICE_NAME,
            YOUTUBE_API_VERSION,
            credentials=creds,
        )
        self.credentials = creds
        return self.youtube

    def upload_video(
        self,
        file_path: str,
        title: str,
        description: str,
        tags: list[str],
        category_id: str = "27",
        privacy_status: str = "unlisted",
        publish_at: Optional[str] = None,
    ) -> str:
        """
        `publish_at`, when given, is an ISO 8601 UTC timestamp
        ("...Z"-suffixed) for YouTube's own `status.publishAt`. This is
        real scheduling — YouTube itself flips the video to public at
        that exact timestamp — as opposed to the old approach of
        uploading public/unlisted immediately and manually re-scheduling
        by hand afterward in Studio, which is what caused a video to
        briefly go live before its intended date (and then, once
        re-scheduled, keep leaning on that original live timestamp).

        Passing `publish_at` forces `privacyStatus` to "private"
        regardless of what `privacy_status` was given — YouTube requires
        a scheduled video to be private until `publishAt` arrives, and
        rejects `publishAt` on any other privacyStatus.
        """
        if self.youtube is None:
            self.authenticate()

        effective_privacy = "private" if publish_at else privacy_status

        status: dict = {
            "privacyStatus": effective_privacy,
            "selfDeclaredMadeForKids": False,
        }
        if publish_at:
            status["publishAt"] = publish_at

        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags,
                "categoryId": category_id,
            },
            "status": status,
        }

        media = MediaFileUpload(
            file_path,
            chunksize=8 * 1024 * 1024,
            resumable=True,
        )

        request = self.youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )

        usage_tracker.log_call("youtube_upload")  # videos.insert: ~1600 quota units

        response = None
        while response is None:
            _, response = request.next_chunk(num_retries=5)

        return response["id"]

    def get_video_status(self, video_id: str) -> Optional[dict]:
        """
        Raw `status` + `snippet` for a single video via the Data API.
        Returns None only when the video genuinely doesn't exist — a
        normal API response with no matching items. Raises
        VideoStatusCheckError if the lookup call itself fails, so
        callers can react differently to "confirmed absent" vs.
        "couldn't check".

        Used by engines/scheduling.py to verify the local database's
        idea of the most recently scheduled video against what YouTube
        actually has on record, before trusting it to anchor the next
        video's publish time. Mirrors the pattern already established in
        engines/analytics.py's `_get_live_publish_info` (never trust
        local state alone for anything that gates a real publish
        action) — kept as a separate public method here rather than
        reusing that private helper, since this needs the full
        status/snippet payload rather than the reduced is_public shape
        analytics.py needs.
        """
        if self.youtube is None:
            self.authenticate()

        attempts = 4
        response = None
        last_exc: Optional[Exception] = None
        for attempt in range(1, attempts + 1):
            try:
                usage_tracker.log_call("youtube_data_status")
                response = self.youtube.videos().list(
                    part="status,snippet",
                    id=video_id,
                ).execute(num_retries=3)
                break
            except HttpError as e:
                if e.resp.status not in TRANSIENT_HTTP_STATUSES:
                    raise VideoStatusCheckError(
                        f"YouTube status check failed for video_id={video_id}: {e}"
                    ) from e
                last_exc = e
            except TRANSIENT_NET_ERRORS as e:
                last_exc = e
            print(
                f"[get_video_status] attempt {attempt}/{attempts} failed "
                f"for {video_id}: {last_exc!r}"
            )
            if attempt < attempts:
                time.sleep(15 * attempt)
        else:
            raise VideoStatusCheckError(
                f"YouTube status check failed for video_id={video_id} "
                f"after {attempts} attempts: {last_exc!r}"
            ) from last_exc

        items = response.get("items", [])
        if not items:
            return None

        return {
            "status": items[0].get("status", {}),
            "snippet": items[0].get("snippet", {}),
        }

    def list_playlists(self) -> list[dict]:
        if self.youtube is None:
            self.authenticate()

        playlists = []
        request = self.youtube.playlists().list(
            part="snippet,contentDetails,status",
            mine=True,
            maxResults=50,
        )

        while request is not None:
            usage_tracker.log_call("youtube_playlist_list")  # playlists.list: 1 quota unit
            response = request.execute()
            playlists.extend(response.get("items", []))
            request = self.youtube.playlists().list_next(request, response)

        return playlists

    def create_playlist(
        self,
        title: str,
        description: str = "",
        privacy_status: str = "public",
    ) -> str:
        if self.youtube is None:
            self.authenticate()

        response = self.youtube.playlists().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": title,
                    "description": description,
                },
                "status": {
                    "privacyStatus": privacy_status,
                },
            },
        ).execute()

        usage_tracker.log_call("youtube_playlist_create")  # playlists.insert: 50 quota units

        return response["id"]

    @staticmethod
    def _error_text(error: HttpError) -> str:
        """str(error) plus the raw response body, so reason codes are matched
        regardless of how googleapiclient chooses to format the message."""
        content = getattr(error, "content", b"") or b""
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="replace")
        return f"{error} {content}"

    @staticmethod
    def _is_propagation_error(error: HttpError) -> bool:
        """
        True for the 404s YouTube returns when a just-uploaded (or just-created)
        resource isn't visible to the API yet — an eventual-consistency delay,
        not a real "missing" signal:
          - playlistNotFound: a playlist created seconds ago (Fact 174).
          - videoNotFound:    a video uploaded seconds ago (Fact 241), even
                              though Studio shows it fine moments later.
        """
        if getattr(error.resp, "status", None) != 404:
            return False
        text = YouTubePublisher._error_text(error)
        return "playlistNotFound" in text or "videoNotFound" in text

    def playlist_contains_video(self, playlist_id: str, video_id: str) -> bool:
        if self.youtube is None:
            self.authenticate()

        try:
            response = self.youtube.playlistItems().list(
                part="snippet",
                playlistId=playlist_id,
                videoId=video_id,
                maxResults=1,
            ).execute()
        except HttpError as e:
            # The videoId filter 404s with videoNotFound when the API can't see
            # the video yet. That is not "already in the playlist", so answer
            # False and let add_to_playlist's insert + retry loop decide.
            if getattr(e.resp, "status", None) == 404 and "videoNotFound" in self._error_text(e):
                usage_tracker.log_call("youtube_playlist_item_list")
                return False
            raise

        usage_tracker.log_call("youtube_playlist_item_list")  # playlistItems.list: 1 quota unit

        return bool(response.get("items"))

    def add_to_playlist(self, playlist_id: str, video_id: str, max_retries: int = 6) -> None:
        """
        Adds video_id to playlist_id (idempotent: skips if already present).

        Retries with backoff (5s, 10s, 20s, 40s, 60s ≈ 2m15s total) on:
          - propagation 404s (playlistNotFound / videoNotFound) — brand-new
            uploads and playlists take a little while to become visible;
          - transient HTTP statuses (429/5xx) and network-level errors.
        Anything else (403 quota/permission, 400, etc.) raises immediately.
        """
        if self.youtube is None:
            self.authenticate()

        delays = (5, 10, 20, 40, 60, 90, 120)
        last_error: Optional[Exception] = None

        for attempt in range(max_retries):
            try:
                if self.playlist_contains_video(playlist_id, video_id):
                    return

                self.youtube.playlistItems().insert(
                    part="snippet",
                    body={
                        "snippet": {
                            "playlistId": playlist_id,
                            "resourceId": {
                                "kind": "youtube#video",
                                "videoId": video_id,
                            },
                        }
                    },
                ).execute()
                usage_tracker.log_call("youtube_playlist_item_insert")  # playlistItems.insert: 50 quota units
                return
            except HttpError as e:
                retryable = (
                    self._is_propagation_error(e)
                    or getattr(e.resp, "status", None) in TRANSIENT_HTTP_STATUSES
                )
                last_error = e
                if retryable and attempt < max_retries - 1:
                    wait = delays[min(attempt, len(delays) - 1)]
                    print(
                        f"Playlist add not ready (attempt {attempt + 1}/{max_retries}, "
                        f"HTTP {e.resp.status}), retrying in {wait}s..."
                    )
                    time.sleep(wait)
                    continue
                raise
            except TRANSIENT_NET_ERRORS as e:
                last_error = e
                if attempt < max_retries - 1:
                    wait = delays[min(attempt, len(delays) - 1)]
                    print(
                        f"Playlist add network error (attempt {attempt + 1}/{max_retries}): "
                        f"{e!r}, retrying in {wait}s..."
                    )
                    time.sleep(wait)
                    continue
                raise

        if last_error is not None:
            raise last_error

    def find_or_create_playlist(
        self,
        playlist_name: str,
        auto_create: bool = True,
    ) -> Optional[str]:
        for playlist in self.list_playlists():
            if playlist["snippet"]["title"].strip().lower() == playlist_name.strip().lower():
                return playlist["id"]

        if not auto_create:
            return None

        return self.create_playlist(
            playlist_name,
            description=f"Videos from You Never Knew about {playlist_name}.",
        )
