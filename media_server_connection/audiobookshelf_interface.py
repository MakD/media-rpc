import os
import requests
import time

from cache_handler import (
    get_cover_cache_key,
    get_poster_cache_key,
    save_cover_cache,
    set_cover_cache_key,
    set_poster_cache_key,
)
from .media_links import media_link, media_links

USE_CHAPTER_TITLE = os.getenv("USE_CHAPTER_TITLE", "False").lower() == "true"
DEFAULT_AUDIOBOOKSHELF_SERVER_NAME = os.getenv(
    "DEFAULT_AUDIOBOOKSHELF_SERVER_NAME", default=""
)
USE_CHAPTER_TIMESTAMPS = os.getenv("USE_CHAPTER_TIMESTAMPS", "False").lower() == "true"


class ABS_Server:
    def __init__(self, server_url, api_token):
        self.server_url = server_url
        self.api_token = api_token
        self.abs_state = {
            "last_api_time": 0,
            "last_position": None,
            "is_playing": False,
        }

    def fetch_data(self):
        session = None
        try:
            url = f"{self.server_url}/api/me/listening-sessions?itemsPerPage=1"
            res = requests.get(
                url, headers={"Authorization": f"Bearer {self.api_token}"}, timeout=2
            ).json()

            if isinstance(res, dict) and "sessions" in res:
                sessions = res["sessions"]
            else:
                sessions = res if isinstance(res, list) else []

            if not sessions:
                return None
            session = sessions[0]
            current_time = session.get("currentTime", 0)

            now = time.time()

            if self.abs_state["last_position"] is None:
                self.abs_state["last_position"] = current_time
                self.abs_state["last_api_time"] = now
                self.abs_state["is_playing"] = False

            last_time = self.abs_state["last_position"]
            last_api_time = self.abs_state["last_api_time"]
            elapsed = now - last_api_time

            if elapsed >= 10 and abs(current_time - last_time) < 1.0:
                self.abs_state["is_playing"] = False
                self.abs_state["last_position"] = current_time
                self.abs_state["last_api_time"] = now
                return None

            elif abs(current_time - last_time) >= 1.0:
                self.abs_state["is_playing"] = True

            self.abs_state["last_position"] = current_time
            self.abs_state["last_api_time"] = now

            if not self.abs_state["is_playing"]:
                return None

            meta = session.get("mediaMetadata", {})
            display_title = session.get("displayTitle", "Unknown")
            display_author = session.get("displayAuthor", "Unknown")
            dur = session.get("duration", 0)
            item_id = session.get("libraryItemId")

            try:
                item_url = f"{self.server_url}/api/items/{item_id}?include=chapters"
                item_resp = requests.get(
                    item_url,
                    headers={"Authorization": f"Bearer {self.api_token}"},
                    timeout=2,
                )
                item_details = item_resp.json() if item_resp.status_code == 200 else {}
            except Exception as e:
                print(f"[ABS] Failed to fetch item details for {display_title}: {e}")
                item_details = {}

            is_podcast = (
                item_details.get("mediaType") == "podcast" or "podcastTitle" in meta
            )

            item_metadata = item_details.get("media", {}).get("metadata") or meta
            if is_podcast:
                episode_id = session.get("episodeId")
                episodes = item_details.get("media", {}).get("episodes", [])
                episode = next((e for e in episodes if e.get("id") == episode_id), {})

                line1 = (
                    episode.get("title") or meta.get("displayTitle") or display_title
                )

                line2 = meta.get("title") or display_author

                season = episode.get("season")
                episode_num = episode.get("episode")
                if season and episode_num:
                    line1 = f"{line1} (S{season}:E{episode_num})"

                links = media_links(media_link("apple_podcasts", item_metadata.get("itunesId")))
            else:
                line1 = self.get_chapter_name(item_details, current_time)
                if not line1:
                    line1 = meta.get("title") or "Unknown Chapter"
                line2 = display_title

                links = media_links(
                    media_link("audible", str(item_metadata.get("asin") or "").upper()),
                    media_link("openlibrary", str(item_metadata.get("isbn") or "").replace("-", "")),
                )

            cover = self.get_abs_cover(item_id)
            if not cover:
                print(
                    f"[ABS Cover] Using iTunes fallback for: {display_title} by {display_author}"
                )
                cover = self.get_itunes_poster(display_title, display_author)
            if USE_CHAPTER_TIMESTAMPS:
                print(
                    f"[ABS] Chapter timestamps enabled, attempting to find current chapter for: {display_title}"
                )
                chapters = item_details.get("media", {}).get("chapters", [])
                current_chapter = None
                print(f"[ABS] Total chapters found: {len(chapters)}")
                for chapter in chapters:
                    if chapter["start"] <= current_time <= chapter["end"]:
                        current_chapter = chapter
                        break
                print(
                    f"[ABS] Current chapter: {current_chapter['title'] if current_chapter else 'None'}"
                )
                if current_chapter:
                    chapter_start_time = current_chapter["start"]
                    chapter_end_time = current_chapter["end"]
                    chapter_duration = chapter_end_time - chapter_start_time
                    chapter_progress = current_time - chapter_start_time
                    start_ts = int((now - chapter_progress) * 1000)
                    end_ts = int((now + (chapter_duration - chapter_progress)) * 1000)
                    print(
                        f"[ABS] Using chapter timestamps for: {display_title}, chapter: {current_chapter['title']}, start_ts: {start_ts}, end_ts: {end_ts}"
                    )
                else:
                    print(
                        f"[ABS] No chapter found for current time, using overall audiobook duration for: {display_title}"
                    )
                    start_ts = int((now - current_time) * 1000)
                    end_ts = int((now - current_time + dur) * 1000)
            else:
                print(
                    f"[ABS] Chapter timestamps disabled, using overall audiobook duration for: {display_title}"
                )
                start_ts = int((now - current_time) * 1000)
                end_ts = int((now - current_time + dur) * 1000)

            abs_state_text = f"{display_author}" + (
                f" • {DEFAULT_AUDIOBOOKSHELF_SERVER_NAME}"
                if DEFAULT_AUDIOBOOKSHELF_SERVER_NAME
                else ""
            )
            # logic for which client icon to show
            device_info = session.get("deviceInfo", {})
            client = device_info.get("clientName")
            if not client:
                client = device_info.get("deviceName", "Unknown")
                print(f"[DEBUG] Client name fallback to DeviceName: {client}")
            match client:
                case "AFinity":
                    icon = "https://raw.githubusercontent.com/MakD/AFinity/refs/heads/master/screenshots/Logo/ic_launcher_round_mdpi.webp"
                case _:
                    icon = "https://raw.githubusercontent.com/advplyr/audiobookshelf/refs/heads/master/client/static/Logo.png"
            print(
                f"[ABS] timestamps for {display_title} - start: {start_ts}, end: {end_ts}"
            )
            return {
                "type": 2,
                "details": line1,
                "state": line2,
                "start": start_ts,
                "end": end_ts,
                "cover": cover,
                "text": abs_state_text,
                "status": "Playing",
                "client_image": icon,
                "client": client,
                "artist": display_author,
                "name": display_title + " • " + display_author,
                "links": links,
            }
        except Exception as e:
            title = (
                session.get("displayTitle", "Unknown")
                if isinstance(session, dict)
                else "Unknown"
            )
            print(f"[ABS] Error processing session data for {title}: {e}")
            return None

    def get_chapter_name(self, item_details, current_time):
        media = item_details.get("media", {})
        chapters = media.get("chapters", [])
        if not chapters:
            return None

        for chapter in chapters:
            if chapter["start"] <= current_time <= chapter["end"]:
                if not USE_CHAPTER_TITLE:
                    return f"Chapter {chapter.get('id') + 1}"
                title = chapter.get("title", "Unknown Chapter")
                lower_title = title.lower()
                prefixes = ["chapter", "chap", "ch", "part", "track"]
                if any(lower_title.startswith(p) for p in prefixes):
                    return title
                return f"Chapter {title}"
        return "Unknown Chapter"

    # ABS Cover Logic with direct linking
    def get_abs_cover(self, item_id):
        cover = get_cover_cache_key(item_id)
        if cover:
            return cover

        cover_url = f"{self.server_url}/cover/{item_id}"
        try:
            resp = requests.head(cover_url, timeout=2)
            if resp.status_code == 200:
                print(f"[ABS Cover] New cover cached for: {item_id}")
                set_cover_cache_key(item_id, cover_url)
                return cover_url
            else:
                print(
                    f"[ABS Cover] Failed ({resp.status_code}), falling back to iTunes"
                )
        except Exception as e:
            print(f"[ABS Cover] Error: {e}")
        return None

    def get_itunes_poster(self, title, author):
        cache_key = f"itunes_{title}_{author}"
        poster_cache_key = get_poster_cache_key(cache_key)
        if poster_cache_key:
            return poster_cache_key
        try:
            query = f"{title} {author}".replace(" ", "+")
            url = (
                f"https://itunes.apple.com/search?term={query}&entity=audiobook&limit=1"
            )
            res = requests.get(url, timeout=2).json()
            if res["resultCount"] > 0:
                img = res["results"][0]["artworkUrl100"].replace(
                    "100x100bb", "600x600bb"
                )
                set_poster_cache_key(cache_key, img)
                return img
        except:
            print(
                f"[iTunes Cover] Failed to fetch cover for {title} by {author}, using fallback icon"
            )
            pass
        return "https://cdn-icons-png.flaticon.com/512/6135/6135126.png"
