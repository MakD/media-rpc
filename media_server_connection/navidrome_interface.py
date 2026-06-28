

import hashlib
import os
import time

import requests


DEFAULT_NAVIDROME_SERVER_NAME = os.getenv("DEFAULT_NAVIDROME_SERVER_NAME", default="Navidrome")


class NavidromeServer:
    def __init__(self, server_url, username, password, salt):
        self.server_url = server_url
        self.username = username
        self.password = password
        self.salt = salt
        self.last_position = 0
    def _generate_md5_hash(self, text):
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    def fetch_data(self):
        try:
            md5_hash = self._generate_md5_hash(self.password + self.salt)
            response = requests.get(
                f"{self.server_url}/rest/getNowPlaying?u={self.username}&t={md5_hash}&s={self.salt}&f=json&v=1.16.1&c=media-rpc",
                timeout=1
            )
            if response.status_code == 200:
                data = response.json()
                now_playing = data["subsonic-response"].get("nowPlaying", {})
                entries = now_playing.get("entry", [])
                entry = next(
                    (e for e in entries if e.get("username") == self.username),
                    None,
                )
                if entry:
                    if entry.get("minutesAgo") is not None and entry.get("minutesAgo") > 1:
                        if self.last_position == entry.get("positionMs", 0):
                            print(f"Now playing entry is older than 1 minute with no changes, ignoring: {entry}")
                            return None
                    self.last_position = entry.get("positionMs", 0)
                    title = entry.get("title")
                    artist = entry.get("artist")
                    positionMs = entry.get("positionMs", 0)
                    duration = entry.get("duration", 0)
                    prog = positionMs / 1000  # seconds elapsed into the track
                    year = entry.get("year", "")
                    state = (f"{year}" if year else "") + (
                            f" • {DEFAULT_NAVIDROME_SERVER_NAME}" if DEFAULT_NAVIDROME_SERVER_NAME else ""
                        )
                    print(DEFAULT_NAVIDROME_SERVER_NAME)
                    print("state:")
                    print(state)
                    cover = entry.get("coverArt") 
                    url = self.cover_art_url(cover, size=300)
                    print(f"Now playing on Navidrome: {title} by {artist}")
                    return {
                        "type": 2,
                        "status": "online",
                        "details": title,
                        "state": state,
                        "artist": artist,
                        "text": artist,
                        "start": int((time.time() - prog) * 1000),
                        "end": int((time.time() - prog + duration) * 1000),
                        "cover": url,
                        "name": title + " • " + artist,
                        "client_image": "https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/png/navidrome.png" # TODO: this should be a client icon, but I'm not done yet. based on playerName 
                    }
                return None
            else:
                print(f"Failed to fetch data from Navidrome server: {response.status_code}")
                return None
        except Exception as e:
            print(f"Error fetching data from Navidrome server: {e}")
            return None

    def cover_art_url(self, cover_art_id, size=None):
        md5_hash = self._generate_md5_hash(self.password + self.salt)
        url = (
            f"{self.server_url}/rest/getCoverArt"
            f"?id={cover_art_id}&u={self.username}&t={md5_hash}&s={self.salt}"
            f"&v=1.16.1&c=media-rpc"
        )
        if size:
            url += f"&size={size}"
        return url