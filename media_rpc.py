import socket
import json
import time
import os
import struct
import requests
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
load_dotenv(env_path)

# --- CONFIGURATION ---
DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")

# 1. Jellyfin Config
JELLYFIN_SERVER = os.getenv("JELLYFIN_SERVER")
JELLYFIN_API_KEY = os.getenv("JELLYFIN_API_KEY")
JELLYFIN_USER_ID = os.getenv("JELLYFIN_USER_ID")
#JELLYFIN_IGNORE_LIBRARIES = ["Bollywood", "Tollywood"] # Sample blacklist to hide certain libraries from showing up in RPC.
JELLYFIN_IGNORE_LIBRARIES = []
TMDB_API_KEY = os.getenv("TMDB_API_KEY")

# 2. Audiobookshelf Config
ABS_SERVER = os.getenv("ABS_SERVER")
ABS_API_TOKEN = os.getenv("ABS_API_TOKEN")

# Optional: Imgur Client ID
IMGUR_CLIENT_ID = os.getenv("IMGUR_CLIENT_ID") 
USE_IMGUR = False # Set to False if you don't have a Client ID

# Optional: whether to show client or movie/show/book title on the discord activity field 
DISCORD_TITLE = os.getenv("DISCORD_TITLE", default = "details") 
ALLOWED_DISCORD_TITLES = ['details', 'client']


# --- STATE MANAGEMENT ---
abs_state = {
    "last_api_time": 0,
    "last_position": None,
    "is_playing": False
}

# Cache files
COVER_CACHE_FILE = "cover_cache.json"
POSTER_CACHE_FILE = "poster_cache.json"
LIBRARY_CACHE_FILE = "library_cache.json"
cover_cache = {}
poster_cache = {}
library_cache = {}

# SYSTEM UTILS
def load_caches():
    global cover_cache, poster_cache, library_cache
    if os.path.exists(COVER_CACHE_FILE):
        try:
            with open(COVER_CACHE_FILE, 'r') as f: cover_cache = json.load(f)
        except: cover_cache = {}
        
    if os.path.exists(POSTER_CACHE_FILE):
        try:
            with open(POSTER_CACHE_FILE, 'r') as f: poster_cache = json.load(f)
        except: poster_cache = {}
        
    if os.path.exists(LIBRARY_CACHE_FILE):
        try:
            with open(LIBRARY_CACHE_FILE, 'r') as f: library_cache = json.load(f)
        except: library_cache = {}

def enforce_cache_limit(cache_dict, max_size=2000):
    while len(cache_dict) > max_size:
        oldest_key = next(iter(cache_dict))
        del cache_dict[oldest_key]

def save_cover_cache():
    enforce_cache_limit(cover_cache, max_size=2000)
    try:
        with open(COVER_CACHE_FILE, 'w') as f: json.dump(cover_cache, f)
    except: pass

def save_poster_cache():
    enforce_cache_limit(poster_cache, max_size=2000)
    try:
        with open(POSTER_CACHE_FILE, 'w') as f: json.dump(poster_cache, f)
    except: pass

def save_library_cache():
    enforce_cache_limit(library_cache, max_size=2000)
    try:
        with open(LIBRARY_CACHE_FILE, 'w') as f: json.dump(library_cache, f)
    except: pass

def get_ipc_path():
    for i in range(10):
        path = f"/run/user/{os.getuid()}/discord-ipc-{i}"
        if os.path.exists(path): return path
    return f"/run/user/{os.getuid()}/discord-ipc-0"

def send_frame(sock, opcode, payload):
    try:
        data = json.dumps(payload).encode()
        header = struct.pack("<II", opcode, len(data))
        sock.sendall(header + data)
    except Exception as e:
        print(f"[RPC] send_frame error: {e}")
        raise

def drain_recv(sock):
    try:
        sock.setblocking(False)
        while True:
            header = sock.recv(8)
            if len(header) < 8:
                break
            _, length = struct.unpack("<II", header)
            if length > 0:
                remaining = length
                while remaining > 0:
                    chunk = sock.recv(min(remaining, 4096))
                    if not chunk:
                        break
                    remaining -= len(chunk)
    except BlockingIOError:
        pass
    except Exception as e:
        print(f"[RPC] drain_recv error: {e}")
        raise
    finally:
        sock.setblocking(True)

# IMGUR / COVER LOGIC
def upload_to_imgur(image_data):
    try:
        url = "https://api.imgur.com/3/image"
        headers = {"Authorization": f"Client-ID {IMGUR_CLIENT_ID}"}
        resp = requests.post(url, headers=headers, files={"image": image_data}, timeout=10)
        data = resp.json()
        if data.get('success'): return data['data']['link']
    except: pass
    return None

# ABS Cover Logic with direct linking (no Imgur)
def get_abs_cover(item_id):
    if item_id in cover_cache:
        return cover_cache[item_id]
    
    cover_url = f"{ABS_SERVER}/cover/{item_id}"
    try:
        resp = requests.head(cover_url, timeout=2)
        if resp.status_code == 200:
            print(f"[ABS Cover] New cover cached for: {item_id}")
            cover_cache[item_id] = cover_url
            save_cover_cache()
            return cover_url
        else:
            print(f"[ABS Cover] Failed ({resp.status_code}), falling back to iTunes")
    except Exception as e:
        print(f"[ABS Cover] Error: {e}")
    return None

# TMDB / iTunes Cover Helpers
def get_tmdb_poster(title, year, type="movie"):
    cache_key = f"tmdb_{title}_{year}"
    if cache_key in poster_cache: return poster_cache[cache_key]
    try:
        endpoint = "tv" if type in ["Series", "Episode"] else "movie"
        url = f"https://api.themoviedb.org/3/search/{endpoint}"
        params = {"api_key": TMDB_API_KEY, "query": title}
        if year: params["year" if endpoint == "movie" else "first_air_date_year"] = year
        res = requests.get(url, params=params, timeout=2).json()
        if res.get('results') and res['results'][0].get('poster_path'):
            path = res['results'][0].get('poster_path')
            img = f"https://images.weserv.nl/?url=https://image.tmdb.org/t/p/w500{path}&w=500&h=500&fit=cover"
            poster_cache[cache_key] = img
            save_poster_cache()
            return img
    except: pass
    return "https://cdn-icons-png.flaticon.com/512/2699/2699194.png"

def get_itunes_poster(title, author):
    cache_key = f"itunes_{title}_{author}"
    if cache_key in poster_cache: return poster_cache[cache_key]
    try:
        query = f"{title} {author}".replace(" ", "+")
        url = f"https://itunes.apple.com/search?term={query}&entity=audiobook&limit=1"
        res = requests.get(url, timeout=2).json()
        if res['resultCount'] > 0:
            img = res['results'][0]['artworkUrl100'].replace('100x100bb', '600x600bb')
            poster_cache[cache_key] = img
            save_poster_cache()
            return img
    except: pass
    return "https://cdn-icons-png.flaticon.com/512/6135/6135126.png"


def get_jellyfin_cover(base_url, item_id, api_key, title, year, item_type):
    cache_key = f"jellyfin_{item_id}"
    if cache_key in poster_cache:
        return poster_cache[cache_key]
    try:
        cover_url = f"{base_url}/Items/{item_id}/Images/Primary?fillHeight=500&fillWidth=500&quality=96&api_key={api_key}"
        resp = requests.head(cover_url, timeout=2)
        if resp.status_code == 200:
            print(f"[Jellyfin Cover] New cover cached for: {item_id}")
            poster_cache[cache_key] = cover_url
            save_poster_cache()
            return cover_url
    except Exception as e:
        print(f"[Jellyfin Cover] Error: {e}")
    return get_tmdb_poster(title, year, item_type)

# ABS CHAPTER CALCULATION
def get_chapter_name(item_details, current_time):
    media = item_details.get("media", {})
    chapters = media.get("chapters", [])
    
    if not chapters: return None

    for chapter in chapters:
        if chapter["start"] <= current_time <= chapter["end"]:
            title = chapter.get("title", "Unknown Chapter")
            lower_title = title.lower()
            prefixes = ["chapter", "chap", "ch", "part", "track"]
            if any(lower_title.startswith(p) for p in prefixes):
                return title
            return f"Chapter {title}"
    return "Unknown Chapter"

def fetch_jellyfin():
    try:
        res = requests.get(JELLYFIN_SERVER, headers={"X-Emby-Token": JELLYFIN_API_KEY}, timeout=1).json()
        if not res: return None
        session = next(
            (s for s in res 
            if "NowPlayingItem" in s
            and not s["PlayState"].get("IsPaused")
            and s.get("UserId") == JELLYFIN_USER_ID), None)
        if not session: return None
        base_url = JELLYFIN_SERVER.split("/Sessions")[0]

        item = session["NowPlayingItem"]
        title = item.get('Name')
        if JELLYFIN_IGNORE_LIBRARIES:
            artist_name = "StreamNode" # can be changed
            item_id = item.get("Id")
            if item.get("SeriesId"):
                item_id = item.get("SeriesId")
            if item.get("ArtistItems"):
                if item.get("ArtistItems")[0].get("Id"):
                    item_id = item.get("ArtistItems")[0].get("Id")
                    artist_name = item.get("AlbumArtist") 
            if item_id in library_cache:
                print("item cached")
                if not library_cache[item_id]:
                    return None 
            else:
                try:
                    print("testing item")
                    user_id = session.get("UserId")
                    anc_url = f"{base_url}/Items/{item_id}/Ancestors"
                    parents_resp = requests.get(
                        anc_url, 
                        params={"userId": user_id},
                        headers={"X-Emby-Token": JELLYFIN_API_KEY}, 
                        timeout=9
                    )
                    
                    if parents_resp.status_code == 200:
                        parents = parents_resp.json()
                        folder_names = [p.get("Name") for p in parents]
                        
                        is_safe = True
                        for name in folder_names:
                            if name in JELLYFIN_IGNORE_LIBRARIES:
                                print(f"[BLOCKED] Hidden Library Found: {name}")
                                is_safe = False
                                break
                        
                        library_cache[item_id] = is_safe
                        save_library_cache()
                        
                        if not is_safe:
                            return None
                            
                    else:
                        print(f"[DEBUG] Ancestor Check Failed: {parents_resp.status_code}")
                        return None
                        
                except Exception as e:
                    print(f"[DEBUG] Blacklist Error: {e}")
                    return None

        prog = session["PlayState"].get("PositionTicks", 0) / 10000000
        dur = item.get("RunTimeTicks", 0) / 10000000
        year = item.get('ProductionYear')
        series = item.get('SeriesName')
        state_text = f"{series} ({year})" if series else f"{year} • StreamNode" # You should replace "StreamNode" with your own branding or remove it entirely if you prefer a cleaner look.
        
        # Logic to get client icon in the little area in discord activity details
        client = session.get("Client")
        match client:
            case "AFinity":
                small_icon = "https://raw.githubusercontent.com/MakD/AFinity/refs/heads/master/screenshots/Logo/ic_launcher_round_mdpi.webp"
            case "Streamyfin":
                small_icon = "https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/webp/streamyfin.webp"
            case "Jellify":
                small_icon = "https://i.ibb.co/zVCxQFJN/jellify.png"
            case "Pelagica":
                small_icon = "https://raw.githubusercontent.com/KartoffelChipss/pelagica/refs/heads/main/frontend/public/favicons/web-app-manifest-512x512.png"
            case _:
                    # default to jf
                small_icon = "https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/webp/jellyfin.webp"
        discord_type = 3
        if item.get('Type') == 'Audio':
            discord_type = 2
        return {
            "type": discord_type,
            "details": title,
            "state": state_text,
            "start": int(time.time() - prog),
            "end": int(time.time() - prog + dur),
            "cover": get_jellyfin_cover(base_url, item.get("Id"), JELLYFIN_API_KEY, series if series else title, year, item.get('Type')),
            "text": artist_name,
            "status": "Playing",
            "client_image": small_icon,
            "client": client,
            "artist": artist_name
        }
    except Exception as e: 
        print(f"[DEBUG] Error: {e}")
        return None

def fetch_abs():
    try:
        url = f"{ABS_SERVER}/api/me/listening-sessions?itemsPerPage=1"
        res = requests.get(url, headers={"Authorization": f"Bearer {ABS_API_TOKEN}"}, timeout=2).json()
        
        if isinstance(res, dict) and "sessions" in res: sessions = res["sessions"]
        else: sessions = res if isinstance(res, list) else []

        if not sessions: return None
        session = sessions[0]
        current_time = session.get("currentTime", 0)
        
        now = time.time()
        
        if abs_state["last_position"] is None:
            abs_state["last_position"] = current_time
            abs_state["last_api_time"] = now
            abs_state["is_playing"] = False

        last_time = abs_state["last_position"]
        last_api_time = abs_state["last_api_time"]
        elapsed = now - last_api_time

        if elapsed >= 10 and abs(current_time - last_time) < 1.0:
            abs_state["is_playing"] = False
            abs_state["last_position"] = current_time
            abs_state["last_api_time"] = now
            return None

        elif abs(current_time - last_time) >= 1.0:
            abs_state["is_playing"] = True

        abs_state["last_position"] = current_time
        abs_state["last_api_time"] = now
        
        if not abs_state["is_playing"]: return None
        
        meta = session.get("mediaMetadata", {})
        display_title = session.get("displayTitle", "Unknown")
        display_author = session.get("displayAuthor", "Unknown")
        dur = session.get("duration", 0)
        item_id = session.get("libraryItemId")

        try:
            item_url = f"{ABS_SERVER}/api/items/{item_id}?include=chapters"
            item_resp = requests.get(item_url, headers={"Authorization": f"Bearer {ABS_API_TOKEN}"}, timeout=2)
            item_details = item_resp.json() if item_resp.status_code == 200 else {}
        except:
            item_details = {}

        is_podcast = item_details.get("mediaType") == "podcast" or "podcastTitle" in meta

        if is_podcast:
            episode_id = session.get("episodeId")
            episodes = item_details.get("media", {}).get("episodes", [])
            episode = next((e for e in episodes if e.get("id") == episode_id), {})

            line1 = episode.get("title") or meta.get("displayTitle") or display_title
            
            line2 = meta.get("title") or display_author

            season = episode.get("season")
            episode_num = episode.get("episode")
            if season and episode_num:
                line1 = f"{line1} (S{season}:E{episode_num})"
        else:
            line1 = get_chapter_name(item_details, current_time)
            if not line1: line1 = meta.get("title") or "Unknown Chapter"
            line2 = display_title

        cover = get_abs_cover(item_id)
        if not cover:
            print(f"[ABS Cover] Using iTunes fallback for: {display_title} by {display_author}")
            cover = get_itunes_poster(display_title, display_author)

        start_ts = int(now - current_time)
        end_ts = int(start_ts + dur)
        abs_state_text = f"{display_author} • AudioNode" # You should replace "AudioNode" with your own branding or remove it entirely if you prefer a cleaner look.
        # logic for which client icon to show
        client = session["deviceInfo"].get("clientName")
        match client:
            case "AFinity":
                icon = "https://raw.githubusercontent.com/MakD/AFinity/refs/heads/master/screenshots/Logo/ic_launcher_round_mdpi.webp"
            case _:
                icon = "https://raw.githubusercontent.com/advplyr/audiobookshelf/refs/heads/master/client/static/Logo.png"
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
            "client": client
        }
    except: return None

# RPC Main
def connect():
    while True:
        try:
            ipc = get_ipc_path()
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(ipc)
            send_frame(sock, 0, {"v": 1, "client_id": DISCORD_CLIENT_ID})
            drain_recv(sock)
            print(f"Connected to Discord at {ipc}!")
            return sock
        except:
            print("Waiting for Discord...", end="\r")
            time.sleep(5)

def main():
    print("Starting RPC...")
    load_caches()
    sock = None
    last_printed = None

    global DISCORD_TITLE
    if DISCORD_TITLE not in ALLOWED_DISCORD_TITLES:
        print("INVALID DISCORD TITLE FOUND. SETTING DETAILS INSTEAD. PLEASE VALIDATE")
        DISCORD_TITLE = 'details'
    while True:
        if not sock: sock = connect()

        data = fetch_jellyfin()
        if not data: 
            data = fetch_abs()
            
        if data:
            small_icon = data["client_image"]
            activity_key = (data['details'], data['state'])
            if activity_key != last_printed:
                print(f"\n[{data.get('text', 'RPC')}] {data['details']} — {data['state']}")
                print(f"  cover: {data['cover']}")
                last_printed = activity_key

            timestamps = {"start": data['start'], "end": data['end']}
            name_key = DISCORD_TITLE
            name = data[name_key]
            if data["artist"]:
                name = name + " • " + data["artist"]
            activity = {
                "name": name,
                "details": data['details'],
                "state": data['state'],
                "assets": {
                    "large_image": data['cover'],
                    "large_text": data['text'],
                    "small_image": small_icon,
                    "small_text": "Playing"
                },
                "type": data['type'],
                "timestamps": timestamps,
                "instance": True
            }
            payload = {"cmd": "SET_ACTIVITY", "args": {"pid": os.getpid(), "activity": activity}, "nonce": str(time.time())}
        else:
            if last_printed is not None:
                print("\n[RPC] Idle")
                last_printed = None
            payload = {"cmd": "SET_ACTIVITY", "args": {"pid": os.getpid(), "activity": None}, "nonce": "c"}

        try:
            send_frame(sock, 1, payload)
            drain_recv(sock)
        except:
            print("\nConnection lost. Reconnecting...")
            if sock:
                try: sock.close()
                except: pass
            sock = None
        time.sleep(15)

if __name__ == "__main__":
    main()
