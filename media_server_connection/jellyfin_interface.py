import json
import os
import time
import requests

from cache_handler import get_library_cache_key, get_poster_cache_key, save_library_cache, set_library_cache_key, set_poster_cache_key



DEFAULT_JELLYFIN_SERVER_NAME = os.getenv("DEFAULT_JELLYFIN_SERVER_NAME", default="")


class JellyfinServer:
    def __init__(self, server_url, api_key, user_id, ignore_libraries, tmdb_api_key):
        self.server_url = server_url
        self.api_key = api_key
        self.user_id = user_id
        self.ignore_libraries = ignore_libraries
        self.tmdb_api_key = tmdb_api_key

        
    def fetch_data(self):
        try:
            res = requests.get(
                self.server_url, headers={"X-Emby-Token": self.api_key}, timeout=1
            ).json()
            if not res:
                return None
            session = next(
                (
                    s
                    for s in res
                    if "NowPlayingItem" in s
                    and not s["PlayState"].get("IsPaused")
                    and s.get("UserId") == self.user_id
                ),
                None,
            )
            if not session:
                return None
            base_url = self.server_url.split("/Sessions")[0]

            item = session["NowPlayingItem"]
            title = item.get("Name")
            artist_name = DEFAULT_JELLYFIN_SERVER_NAME  # can be changed
            item_id = item.get("Id")
            if item.get("SeriesId"):
                item_id = item.get("SeriesId")
                artist_name = item.get("SeriesName")
            if item.get("ArtistItems"):
                if item.get("ArtistItems")[0].get("Id"):
                    item_id = item.get("ArtistItems")[0].get("Id")
                    artist_name = item.get("AlbumArtist")
            if self.ignore_libraries:
                key = get_library_cache_key(item_id)
                if key is not None:
                    if not key:
                        return None
                else:
                    try:
                        user_id = session.get("UserId")
                        anc_url = f"{base_url}/Items/{item_id}/Ancestors"
                        parents_resp = requests.get(
                            anc_url,
                            params={"userId": user_id},
                            headers={"X-Emby-Token": self.api_key},
                            timeout=9,
                        )

                        if parents_resp.status_code == 200:
                            parents = parents_resp.json()
                            folder_names = [p.get("Name") for p in parents]

                            is_safe = True
                            for name in folder_names:
                                if name in self.ignore_libraries:
                                    print(f"[BLOCKED] Hidden Library Found: {name}")
                                    is_safe = False
                                    break
                            set_library_cache_key(item_id, is_safe)

                            if not is_safe:
                                return None

                        else:
                            print(
                                f"[DEBUG] Ancestor Check Failed: {parents_resp.status_code}"
                            )
                            return None

                    except Exception as e:
                        print(f"[DEBUG] Blacklist Error: {e}")
                        return None

            prog = session["PlayState"].get("PositionTicks", 0) / 10000000
            dur = item.get("RunTimeTicks", 0) / 10000000
            year = item.get("ProductionYear")
            series = item.get("SeriesName")
            state_text = (f"{series} ({year})" if series else f"{year}") + (
                f" • {DEFAULT_JELLYFIN_SERVER_NAME}"
                if DEFAULT_JELLYFIN_SERVER_NAME
                else ""
            )

            # Logic to get client icon in the little area in discord activity details
            client = session.get("Client")
            if not client:
                client = session.get("DeviceName", "Unknown")
                print(f"[DEBUG] Client name fallback to DeviceName: {client}")
            if client.startswith("Moonfin"):
                client = "Moonfin"
            match client:
                case "AFinity":
                    small_icon = "https://raw.githubusercontent.com/MakD/AFinity/refs/heads/master/screenshots/Logo/ic_launcher_round_mdpi.webp"
                case "Streamyfin":
                    small_icon = "https://raw.githubusercontent.com/streamyfin/streamyfin/refs/heads/develop/assets/images/icon-ios-plain.png"
                case "Jellify":
                    small_icon = "https://i.ibb.co/zVCxQFJN/jellify.png"
                case "Pelagica":
                    small_icon = "https://raw.githubusercontent.com/PelagicaApp/pelagica/refs/heads/main/frontend/public/favicons/web-app-manifest-512x512.png"
                case "Kodi":
                    small_icon = (
                        "https://images.icon-icons.com/1495/PNG/512/kodi_102964.png"
                    )
                case "Wholphin":
                    small_icon = "https://raw.githubusercontent.com/damontecres/Wholphin/main/app/src/main/res/mipmap-xxxhdpi/ic_launcher_round.webp"
                case "Moonfin":
                    small_icon = "https://raw.githubusercontent.com/Moonfin-Client/Moonfin-Core/main/assets/icons/moonfin.png"
                case _:
                    # default to jf
                    small_icon = "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcR9hELYbRA5IB6-ci3AzpkvOTJ3BAq6-_LmMg&s"

            discord_type = 3
            status = "dnd"
            if item.get("Type") == "Audio":
                discord_type = 2
                status = "online"
            return {
                "type": discord_type,
                "status": status,
                "details": title,
                "state": state_text,
                "start": int((time.time() - prog) * 1000),
                "end": int((time.time() - prog + dur) * 1000),
                "cover": self.get_jellyfin_cover(
                    base_url,
                    item.get("Id"),
                    self.api_key,
                    series if series else title,
                    year,
                    item.get("Type"),
                ),
                "text": artist_name,
                "client_image": small_icon,
                "client": client,
                "artist": artist_name,
                "name": title + " • " + artist_name,
            }
        except Exception as e:
            print(f"[DEBUG] Failed to fetch data from Jellyfin server: {e}")
            return None

    def get_jellyfin_cover(self,base_url, item_id, api_key, title, year, item_type):
        cache_key = f"jellyfin_{item_id}"
        
        poster_cache_key = get_poster_cache_key(cache_key)
        if poster_cache_key:
            return poster_cache_key
        try:
            cover_url = f"{base_url}/Items/{item_id}/Images/Primary?fillHeight=500&fillWidth=500&quality=96&api_key={api_key}"
            resp = requests.head(cover_url, timeout=2)
            if resp.status_code == 200:
                print(f"[Jellyfin Cover] New cover cached for: {item_id}")
                set_poster_cache_key(cache_key, cover_url)
                return cover_url
        except Exception as e:
            print(f"[Jellyfin Cover] Error: {e}")
        return self.get_tmdb_poster(title, year, item_type)


    

    
    # TMDB / iTunes Cover Helpers
    def get_tmdb_poster(self,title, year, type="movie"):
        cache_key = f"tmdb_{title}_{year}"
        key = get_poster_cache_key(cache_key)
        if key:
            return key
        try:
            endpoint = "tv" if type in ["Series", "Episode"] else "movie"
            url = f"https://api.themoviedb.org/3/search/{endpoint}"
            params = {"api_key": self.tmdb_api_key, "query": title}
            if year:
                params["year" if endpoint == "movie" else "first_air_date_year"] = year
            res = requests.get(url, params=params, timeout=2).json()
            if res.get("results") and res["results"][0].get("poster_path"):
                path = res["results"][0].get("poster_path")
                img = f"https://images.weserv.nl/?url=https://image.tmdb.org/t/p/w500{path}&w=500&h=500&fit=cover"
                set_poster_cache_key(cache_key, img)
                return img
        except:
            pass
        return "https://cdn-icons-png.flaticon.com/512/2699/2699194.png"
