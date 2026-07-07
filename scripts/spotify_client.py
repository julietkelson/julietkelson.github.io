"""Thin Spotify Web API client. Only the endpoints we still can use."""

from __future__ import annotations

import base64
from typing import Any

import requests

TOKEN_URL = "https://accounts.spotify.com/api/token"
API_ROOT = "https://api.spotify.com/v1"
TIMEOUT_S = 10


class SpotifyError(Exception):
    pass


class SpotifyClient:
    def __init__(self, client_id: str, client_secret: str, refresh_token: str):
        self._client_id = client_id
        self._client_secret = client_secret
        self._refresh_token = refresh_token
        self._access_token: str | None = None

    def _refresh_access_token(self) -> None:
        basic = base64.b64encode(
            f"{self._client_id}:{self._client_secret}".encode()
        ).decode()
        resp = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": self._refresh_token,
            },
            headers={
                "Authorization": f"Basic {basic}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            timeout=TIMEOUT_S,
        )
        if resp.status_code != 200:
            raise SpotifyError(
                f"token refresh failed: {resp.status_code} {resp.text[:200]}"
            )
        self._access_token = resp.json()["access_token"]

    def _headers(self) -> dict[str, str]:
        if not self._access_token:
            self._refresh_access_token()
        return {"Authorization": f"Bearer {self._access_token}"}

    def currently_playing(self) -> dict[str, Any] | None:
        resp = requests.get(
            f"{API_ROOT}/me/player/currently-playing",
            headers=self._headers(),
            timeout=TIMEOUT_S,
        )
        if resp.status_code == 204:
            return None
        if resp.status_code == 401:
            self._refresh_access_token()
            resp = requests.get(
                f"{API_ROOT}/me/player/currently-playing",
                headers=self._headers(),
                timeout=TIMEOUT_S,
            )
        if resp.status_code == 204:
            return None
        if resp.status_code != 200:
            raise SpotifyError(
                f"currently-playing failed: {resp.status_code} {resp.text[:200]}"
            )
        return resp.json()

    def artist_genres(self, artist_ids: list[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for artist_id in artist_ids:
            resp = requests.get(
                f"{API_ROOT}/artists/{artist_id}",
                headers=self._headers(),
                timeout=TIMEOUT_S,
            )
            if resp.status_code == 401:
                self._refresh_access_token()
                resp = requests.get(
                    f"{API_ROOT}/artists/{artist_id}",
                    headers=self._headers(),
                    timeout=TIMEOUT_S,
                )
            if resp.status_code != 200:
                raise SpotifyError(
                    f"artist fetch failed for {artist_id}: {resp.status_code}"
                )
            for g in resp.json().get("genres", []):
                if g not in seen:
                    seen.add(g)
                    ordered.append(g)
        return ordered
