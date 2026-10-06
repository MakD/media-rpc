import hashlib
import os
import time

import requests

from cache_handler import get_poster_cache_key, set_poster_cache_key
from .media_links import media_link, media_links


NAVIDROME_ICON = (
    "https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/png/navidrome.png"
)
DEFAULT_NAVIDROME_SERVER_NAME = os.getenv(
    "DEFAULT_NAVIDROME_SERVER_NAME", default="Navidrome"
)

_cover_retry_at = {}  # album_id -> time.time() after which we try again
COVER_RETRY_SECONDS = 30 * 60

class NavidromeServer:
    def __init__(self, server_url, username, password, salt):
        self.server_url = server_url
        self.username = username
        self.password = password
        self.salt = salt

    def _generate_md5_hash(self, text):
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    def fetch_data(self):
        try:
            md5_hash = self._generate_md5_hash(self.password + self.salt)
            response = requests.get(
                f"{self.server_url}/rest/getNowPlaying",
                timeout=1,
                params={
                    "u": self.username,
                    "t": md5_hash,
                    "s": self.salt,
                    "f": "json",
                    "v": "1.16.1",
                    "c": "media-rpc",
                },
            )
            if response.status_code == 200:
                data = response.json()
                sub = data["subsonic-response"]
                if sub.get("status") == "failed":
                    print(f"[Navidrome] {sub.get('error', {}).get('message')}")
                    return
                now_playing = sub.get("nowPlaying", {})
                entries = now_playing.get("entry", [])
                # One entry per player; the server drops "playing" entries as soon
                # as the track would have ended, so anything not paused is live.
                candidates = [
                    e
                    for e in entries
                    if e.get("username") == self.username and e.get("state") != "paused"
                ]
                entry = min(
                    candidates,
                    key=lambda e: (e.get("minutesAgo", 0), -e.get("positionMs", 0)),
                    default=None,
                )
                if entry:
                    title = entry.get("title")
                    artist = entry.get("artist")
                    positionMs = entry.get("positionMs", 0)
                    duration = entry.get("duration", 0)
                    rate = entry.get("playbackRate") or 1.0
                    prog = positionMs / 1000  # seconds elapsed into the track
                    year = entry.get("year", "")
                    state = (f"{year}" if year else "") + (
                        f" • {DEFAULT_NAVIDROME_SERVER_NAME}"
                        if DEFAULT_NAVIDROME_SERVER_NAME
                        else ""
                    )
                    url = self.get_cover_url(entry.get("albumId"))
                    print(f"Now playing on Navidrome: {title} by {artist}")
                    return {
                        "type": 2,
                        "status": "online",
                        "details": title,
                        "state": state,
                        "artist": artist,
                        "text": artist,
                        "start": int((time.time() - prog / rate) * 1000),
                        "end": int((time.time() + (duration - prog) / rate) * 1000),
                        "cover": url,
                        "name": title + " • " + artist,
                        "client_image": NAVIDROME_ICON,  # TODO: this should be a client icon, but I'm not done yet. based on playerName
                        "links": media_links(media_link("musicbrainz_recording", entry.get("musicBrainzId"))),
                    }
                return None
            else:
                print(
                    f"Failed to fetch data from Navidrome server: {response.status_code}"
                )
                return None
        except Exception as e:
            print(f"[Navidrome] Failed to fetch data: {type(e).__name__}")
            return None

   

    def get_cover_url(self, album_id):
        """
        Get a public cover url for the album. getCoverArt urls need the subsonic credentials,
        which would be visible to everyone who sees the presence, while getAlbumInfo2 returns
        image links signed by the server that work without credentials.
        """
        if not album_id:
            return NAVIDROME_ICON
        cache_key = f"navidrome_{album_id}"
        cached_url = get_poster_cache_key(cache_key)
        if cached_url:
            return cached_url
        if time.time() < _cover_retry_at.get(album_id, 0):
            return NAVIDROME_ICON
        try:
            response = requests.get(
                f"{self.server_url}/rest/getAlbumInfo2",
                params={
                    "id": album_id,
                    "u": self.username,
                    "t": self._generate_md5_hash(self.password + self.salt),
                    "s": self.salt,
                    "f": "json",
                    "v": "1.16.1",
                    "c": "media-rpc",
                },
                timeout=2,
            )
            album_info = response.json()["subsonic-response"].get("albumInfo", {})
            url = album_info.get("smallImageUrl")
            if url and url.startswith("http"):
                set_poster_cache_key(cache_key, url)
                _cover_retry_at.pop(album_id, None)
                return url
            print(f"[Navidrome Cover] No public cover found for album {album_id}")
            
        except Exception as e:
            # the request url contains the credentials, so only log the error type
            print(
                f"[Navidrome Cover] Failed to fetch cover for album {album_id}: {type(e).__name__}"
            )
        _cover_retry_at[album_id] = time.time() + COVER_RETRY_SECONDS
        return NAVIDROME_ICON
