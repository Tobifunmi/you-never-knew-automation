from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube"]

YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"


class YouTubePublisher:
    def __init__(
        self,
        credentials_path: str = "credentials.json",
        token_path: str = "token.json",
    ):
        self.credentials_path = Path(credentials_path)
        self.token_path = Path(token_path)
        self.youtube = None

    def authenticate(self, interactive: bool = True):
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
        return self.youtube

    def upload_video(
        self,
        file_path: str,
        title: str,
        description: str,
        tags: list[str],
        category_id: str = "27",
        privacy_status: str = "unlisted",
    ) -> str:
        if self.youtube is None:
            self.authenticate()

        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags,
                "categoryId": category_id,
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False,
            },
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

        response = None
        while response is None:
            _, response = request.next_chunk()

        return response["id"]

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

        return response["id"]

    def playlist_contains_video(self, playlist_id: str, video_id: str) -> bool:
        if self.youtube is None:
            self.authenticate()

        response = self.youtube.playlistItems().list(
            part="snippet",
            playlistId=playlist_id,
            videoId=video_id,
            maxResults=1,
        ).execute()

        return bool(response.get("items"))

    def add_to_playlist(self, playlist_id: str, video_id: str, max_retries: int = 5) -> None:
        if self.youtube is None:
            self.authenticate()

        last_error = None
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
                return
            except HttpError as e:
                if "playlistNotFound" in str(e) and attempt < max_retries - 1:
                    wait = 2 ** attempt  # 1, 2, 4, 8, 16 seconds
                    print(f"Playlist not yet available (attempt {attempt + 1}/{max_retries}), retrying in {wait}s...")
                    time.sleep(wait)
                    last_error = e
                    continue
                raise

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
