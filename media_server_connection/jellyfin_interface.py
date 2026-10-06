import json
import os
import time
import requests

from cache_handler import get_library_cache_key, get_poster_cache_key, save_library_cache, set_library_cache_key, set_poster_cache_key
from .media_links import media_link, media_links



DEFAULT_JELLYFIN_SERVER_NAME = os.getenv("DEFAULT_JELLYFIN_SERVER_NAME", default="")
GET_SHOW_YEAR = os.getenv("GET_SHOW_YEAR", default="False").lower() == "true"
USE_SERIES_IMAGE = os.getenv("USE_SERIES_IMAGE", default="False").lower() == "true"
USE_TMDB_IMAGE = os.getenv("USE_TMDB_IMAGE", default="False").lower() == "true"
FORCE_SHOW_EPISODE_INDEX = os.getenv("FORCE_SHOW_EPISODE_INDEX", default="false").lower() == "true"
SHOW_TITLE_IN_TOP = os.getenv("SHOW_TITLE_IN_TOP", default="false").lower() == "true"

show_to_year = {}

class JellyfinServer:
    

    def __init__(self, server_url, api_key, user_id, ignore_libraries, tmdb_api_key):
        self.server_url = server_url
        self.api_key = api_key
        self.user_id = user_id
        self.ignore_libraries = ignore_libraries
        self.tmdb_api_key = tmdb_api_key

    def get_show_year(self, base_url, series_id, api_key, user_id):
        year = show_to_year.get(series_id)
        if year is not None: 
            return year
        try:
            url = f"{base_url}/Items"
            params = {"userId": user_id, "ids": series_id}
            headers = {"Authorization": f'MediaBrowser Token={api_key}'}
            response = requests.get(url, params=params, headers=headers, timeout=2)
            if response.status_code == 200:
                data = response.json().get("Items", [None])[0] # Assuming the first item is the series (which it will be because we ask for just one show)
                year = data.get("ProductionYear")
                show_to_year[series_id] = year
                return year
            else:
                print(f"[DEBUG] Failed to fetch show year: {response.status_code}")
                return None
        except Exception as e:
            print(f"[DEBUG] Error fetching show year: {e}")
            return None
    
    
    def fetch_data(self):
        try:
            res = requests.get(
                self.server_url, headers={"Authorization": f'MediaBrowser Token={self.api_key}'}, timeout=1
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
            title_with_prefix = title
            artist_name = DEFAULT_JELLYFIN_SERVER_NAME  # can be changed
            item_id = item.get("Id")
            year = item.get("ProductionYear")
            if item.get("SeriesId"):
                item_id = item.get("SeriesId")
                artist_name = item.get("SeriesName")
                if FORCE_SHOW_EPISODE_INDEX:
                    season_number = item.get("ParentIndexNumber")
                    episode_number = item.get("IndexNumber")
                    if season_number is not None and episode_number is not None:
                        title_with_prefix = f"S{season_number:02}E{episode_number:02} - {title}"

                if GET_SHOW_YEAR and item.get("Type") == "Episode":
                    year = self.get_show_year(base_url, item_id, self.api_key, self.user_id)
            if  item.get("Type") == "Movie":
                year = item.get("ProductionYear")
            if item.get("ArtistItems") and item.get("ArtistItems")[0].get("Id"):   
                item_id = item.get("ArtistItems")[0].get("Id")
                artist_name = item.get("AlbumArtist")

            if self.ignore_libraries:
                folder_names = get_library_cache_key(item_id)
                if not isinstance(folder_names, list):
                    try:
                        user_id = session.get("UserId")
                        anc_url = f"{base_url}/Items/{item_id}/Ancestors"
                        parents_resp = requests.get(
                            anc_url,
                            params={"userId": user_id},
                            headers={"Authorization": f'MediaBrowser Token={self.api_key}'},
                            timeout=9,
                        )

                        if parents_resp.status_code != 200:
                            print(f"[DEBUG] Ancestor Check Failed: {parents_resp.status_code}")
                            return None
                        folder_names = [p.get("Name") for p in parents_resp.json()]
                        set_library_cache_key(item_id, folder_names)     
                    except Exception as e:
                        print(f"[DEBUG] Blacklist Error: {e}")
                        return None
                blocked = next((n for n in folder_names if n in self.ignore_libraries), None)
                if blocked:
                    print(f"[BLOCKED] Hidden Library Found: {blocked}")
                    return None

            prog = session["PlayState"].get("PositionTicks", 0) / 10000000
            dur = item.get("RunTimeTicks", 0) / 10000000
            if not GET_SHOW_YEAR or item.get("Type") == 'Audio':
                year = item.get("ProductionYear")
            series = item.get("SeriesName")
            year_text = (f"({year})" if series else f"{year}") if year else ""
            state_text = (f"{series} {year_text} " if series else year_text) + (
                f" • {DEFAULT_JELLYFIN_SERVER_NAME}"
                if DEFAULT_JELLYFIN_SERVER_NAME
                else ""
            )
            name = title + " • " + artist_name
            if SHOW_TITLE_IN_TOP and item.get("SeriesName"):
                name = item.get("SeriesName")



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
            item_id_for_image = item.get("Id")
            if USE_SERIES_IMAGE and item.get("SeriesId"):
                item_id_for_image = item.get("SeriesId")

            return {
                "type": discord_type,
                "status": status,
                "details":title_with_prefix,
                "state": state_text,
                "start": int((time.time() - prog) * 1000),
                "end": int((time.time() - prog + dur) * 1000),
                "cover": self.get_jellyfin_cover(
                    base_url,
                    item_id_for_image,
                    series if series else title,
                    year,
                    item.get("Type"),
                ),
                "text": artist_name,
                "client_image": small_icon,
                "client": client,
                "artist": artist_name,
                "name": name ,
                "links": self.get_media_links(item),
            }
        except Exception as e:
            print(f"[DEBUG] Failed to fetch data from Jellyfin server: {e}")
            return None

    def get_media_links(self, item):
        provider_ids = {k.lower(): v for k, v in (item.get("ProviderIds") or {}).items()}
        if item.get("Type") == "Audio":
            return media_links(media_link("musicbrainz_release", provider_ids.get("musicbrainzalbum")))
        return media_links(
            media_link("imdb", provider_ids.get("imdb")),
            media_link("tmdb_movie", provider_ids.get("tmdb")) if item.get("Type") == "Movie" else None,
        )

    def get_jellyfin_cover(self,base_url, item_id, title, year, item_type):
        cache_key = f"jellyfin_{item_id}"
        
        poster_cache_key = get_poster_cache_key(cache_key)
        # older versions cached cover urls containing the api key, don't reuse those
        if poster_cache_key and "api_key=" not in poster_cache_key:
            return poster_cache_key

        if USE_TMDB_IMAGE:
            return self.get_tmdb_poster(title, year, item_type)
        try:
            # jellyfin serves images without auth, and this url is public in the presence, so it must not contain the api key
            cover_url = f"{base_url}/Items/{item_id}/Images/Primary?fillHeight=500&fillWidth=500&quality=96"
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
