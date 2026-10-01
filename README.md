# Discord Media RPC

A Discord Rich Presence client that shows what you're watching on Jellyfin, listening to on Navidrome, or listening to on Audiobookshelf - with cover art, timestamps, and chapter tracking.

<p align="center">
  <img src="screenshots/preview.png" width="90%" alt="RPC Preview Video">
</p>
<p align="center">
  <img src="screenshots/preview2.png" width="90%" alt="RPC Preview Audio">
</p>

<div align="center">
  <img src="https://img.shields.io/badge/python-3.8+-blue?style=for-the-badge&logo=python&logoColor=ffffff&labelColor=000000&color=333446"/>
  <a href="https://github.com/MakD/media-rpc/releases"><img src="https://img.shields.io/github/downloads/MakD/media-rpc/total?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgLTk2MCA5NjAgOTYwIiBmaWxsPSJ3aGl0ZSI+PHBhdGggZD0iTTIwMC0xNjBoNTYwcTE3IDAgMjguNSAxMS41VDgwMC0xMjBxMCAxNy0xMS41IDI4LjVUNzYwLTgwSDIwMHEtMTcgMC0yOC41LTExLjVUMTYwLTEyMHEwLTE3IDExLjUtMjguNVQyMDAtMTYwWm0yODAtMTA1cS05IDAtMTcuNS00VDQ0OC0yODFMMjUwLTUzNXEtMTUtMjAtNC00Mi41dDM2LTIyLjVoNzh2LTI0MHEwLTE3IDExLjUtMjguNVQ0MDAtODgwaDE2MHExNyAwIDI4LjUgMTEuNVQ2MDAtODQwdjI0MGg3OHEyNSAwIDM2IDIyLjV0LTQgNDIuNUw1MTItMjgxcS02IDgtMTQuNSAxMnQtMTcuNSA0WiIvPjwvc3ZnPg==&logoColor=ffffff&labelColor=000000&color=333446"/></a>
</div>

---

## Runners

### script

media_rpc.py

### docker

in addition, you can run it in docker, either building it yourself, or using
https://hub.docker.com/repository/docker/simoneklundh/media-rpc

---

## Features

- Jellyfin support - movies and TV shows with cover art (falls back to TMDB)
- Audiobookshelf support - audiobooks and podcasts with chapter tracking
- Navidrome support - music, with server based album images
- **Privacy-focused** - filters by your specific User ID so your friends' streams don't show on your profile
- **Secure Configuration** - uses a `.env` file to keep your API tokens and IDs safe
- Cover art fetched directly from your media servers
- Elapsed and remaining time timestamps
- Optional links and buttons to public pages about what's playing (IMDb, TMDB, MusicBrainz, Audible, Open Library, Apple Podcasts), plus up to two custom buttons
- Library blacklist to hide specific Jellyfin libraries (cached for performance)
- Auto-reconnect if Discord connection drops
- Local cover cache to avoid redundant requests
- Can optionally be ran without discord running

---

## Requirements

### script version

- Python 3.10+ (for mac this might require homebrew)

### docker version

- docker

### both
- A running [Jellyfin](https://jellyfin.org/) and/or [Audiobookshelf](https://www.audiobookshelf.org/) instance
- A [Discord application](https://discord.com/developers/applications) with a Client ID
- A reverse proxy (Caddy, Nginx, Apache, Traefik) with a public domain for ABS cover art - see [Cover Art Setup](#cover-art-setup)

---

## Installation

### Docker Compose version
```yaml
services:
  media-rpc:
    image: simoneklundh/media-rpc:2
    container_name: media-rpc
    restart: unless-stopped
    environment:
      - DISCORD_CLIENT_ID=idhere
      - DISCORD_TOKEN=tokenhere
      - JELLYFIN_SERVER=https://jellyfin.domain.tld/Sessions
      - JELLYFIN_API_KEY=apikeyhere
      - USE_SERIES_IMAGE=false
      - JELLYFIN_USER_ID=useridhere
      - TMDB_API_KEY=api_key_here
      - ABS_SERVER=https://books.domain.tld
      - ABS_API_TOKEN=apitokenhere
      - USE_CHAPTER_TITLE=true
      - USE_CHAPTER_TIMESTAMPS=false
      - DEFAULT_JELLYFIN_SERVER_NAME= Custom Server Name
      - DEFAULT_AUDIOBOOKSHELF_SERVER_NAME= Custom Server Name
      - JELLYFIN_IGNORE_LIBRARIES=Library1,Library2,Library3
      - USE_TMDB_IMAGE=false
      - GET_SHOW_YEAR=false
      - FORCE_SHOW_EPISODE_INDEX=false
      - SHOW_TITLE_IN_TOP=false
      # Navidrome variables, only necessary if using Navidrome, not needed for Jellyfin or AudioBookShelf
      - NAVIDROME_USERNAME=admin
      - NAVIDROME_PASSWORD=adminpassword
      - NAVIDROME_SERVER=https://music.domain.tld
      - DEFAULT_NAVIDROME_SERVER_NAME=Navidrome
      # Navidrome salt, should be a random string, used for hashing passwords, keep it secret
      - NAVIDROME_SALT=averygoodsaltthatshouldberandomandkeptsecret
      - USE_GATEWAY=true
      # optional, links and buttons in the presence, see Configuration
      - USE_MEDIA_LINKS=false
      - DISCORD_BUTTON_1_LABEL=
      - DISCORD_BUTTON_1_URL=
      - DISCORD_BUTTON_2_LABEL=
      - DISCORD_BUTTON_2_URL=
```
[How to get the variables](#Configuration)  

[How To Get Audiobookshelf Images In Discord](#Cover-Art-Setup)

### venv version (recommended for non-docker use)

**1. Clone the repository:**
```bash
git clone https://github.com/MakD/media-rpc.git
cd media-rpc
```
**2. Create and source virtual environment**
```bash
# python or python3 depending on your setup
python -m venv venv

# linux/mac
source venv/bin/activate (or activate.fish for fish users)
# windows powershell:
./venv/bin/Activate.ps1
# in case of permission errors, run this and then retry:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**3. Install dependencies:**

```bash
pip install -r requirements.txt

```

**4. Configure the script:**

```bash
# discord (DISCORD_TOKEN is only required for the gateway version)
DISCORD_TOKEN=YOUR_DISCORD_TOKEN
DISCORD_CLIENT_ID=YOUR_DISCORD_CLIENT_ID
# jellyfin
JELLYFIN_SERVER=https://jellyfin.example.com/Sessions
JELLYFIN_API_KEY=YOUR_JELLYFIN_API_KEY
JELLYFIN_USER_ID=YOUR_JELLYFIN_USER_ID
USE_SERIES_IMAGE=false
TMDB_API_KEY=YOUR_TMDB_API_KEY
# audiobookshelf
ABS_SERVER=https://abs.example.com
ABS_API_TOKEN=YOUR_ABS_API_TOKEN
# optional, defaults to false
USE_CHAPTER_TITLE=true
# optional, defaults to false
USE_CHAPTER_TIMESTAMPS=false
#optional, defaults to empty string
DEFAULT_JELLYFIN_SERVER_NAME=jellyfin_server_name 
#optional, defaults to empty string
DEFAULT_AUDIOBOOKSHELF_SERVER_NAME=audiobookshelf_server_name 
#optional, defaults to empty list
JELLYFIN_IGNORE_LIBRARIES=library1,library2
# optional, defaults to false
USE_TMDB_IMAGE=false
# optional, defaults to false
GET_SHOW_YEAR=false
# optional, defaults to false
FORCE_SHOW_EPISODE_INDEX=false
# optional, defaults to false
SHOW_TITLE_IN_TOP=false
# Navidrome variables, only necessary if using Navidrome, not needed for Jellyfin or AudioBookShelf
NAVIDROME_USERNAME=admin
NAVIDROME_PASSWORD=adminpassword
NAVIDROME_SERVER=https://music.domain.tld
# optional.  defaults to Navidrome
DEFAULT_NAVIDROME_SERVER_NAME=Navidrome
# Navidrome salt, should be a random string, used for hashing passwords, keep it secret
NAVIDROME_SALT=averygoodsaltthatshouldberandomandkeptsecret
# defaults to false
# true => use gateway, false => use rpc (requires discord running on your computer)
USE_GATEWAY=true
# optional, defaults to false. true => link the title and add buttons to public pages about what's playing
USE_MEDIA_LINKS=false
# optional, up to 2 custom buttons (label max 32 characters, url must start with http:// or https://)
DISCORD_BUTTON_1_LABEL=
DISCORD_BUTTON_1_URL=
DISCORD_BUTTON_2_LABEL=
DISCORD_BUTTON_2_URL=
```
**5. Run media-rpc:**
```bash
python media_rpc.py
```

## global version (not recommended)

**1. Clone the repository:**
```bash
git clone https://github.com/MakD/media-rpc.git
cd media-rpc
```

**2. Install dependencies:**
```bash
pip install -r requirements.txt
```

**3. Configure the script:** Create a new file named `.env` in the same directory as the script and fill in your details:

```bash
# discord (DISCORD_TOKEN is only required for media_rpc_gateway.py)
DISCORD_TOKEN=YOUR_DISCORD_TOKEN
DISCORD_CLIENT_ID=YOUR_DISCORD_CLIENT_ID
# jellyfin
JELLYFIN_SERVER=https://jellyfin.example.com/Sessions
JELLYFIN_API_KEY=YOUR_JELLYFIN_API_KEY
JELLYFIN_USER_ID=YOUR_JELLYFIN_USER_ID
USE_SERIES_IMAGE=false
TMDB_API_KEY=YOUR_TMDB_API_KEY
# audiobookshelf
ABS_SERVER=https://abs.example.com
ABS_API_TOKEN=YOUR_ABS_API_TOKEN
# optional, defaults to false
USE_CHAPTER_TITLE=true
# optional, defaults to false
USE_CHAPTER_TIMESTAMPS=false
#optional, defaults to empty string
DEFAULT_JELLYFIN_SERVER_NAME=jellyfin_server_name 
#optional, defaults to empty string
DEFAULT_AUDIOBOOKSHELF_SERVER_NAME=audiobookshelf_server_name 
#optional, defaults to empty list
JELLYFIN_IGNORE_LIBRARIES=library1,library2
# optional, defaults to false
USE_TMDB_IMAGE=false
# optional, defaults to false
GET_SHOW_YEAR=false
# optional, defaults to false
FORCE_SHOW_EPISODE_INDEX=false
# optional, defaults to false
SHOW_TITLE_IN_TOP=false
# Navidrome variables, only necessary if using Navidrome, not needed for Jellyfin or AudioBookShelf
NAVIDROME_USERNAME=admin
NAVIDROME_PASSWORD=adminpassword
NAVIDROME_SERVER=https://music.domain.tld
# optional.  defaults to Navidrome
DEFAULT_NAVIDROME_SERVER_NAME=Navidrome
# Navidrome salt, should be a random string, used for hashing passwords, keep it secret
NAVIDROME_SALT=averygoodsaltthatshouldberandomandkeptsecret
# defaults to false. true => use the gateway, no discord client needed. requires DISCORD_TOKEN
USE_GATEWAY=true
# optional, defaults to false. true => link the title and add buttons to public pages about what's playing
USE_MEDIA_LINKS=false
# optional, up to 2 custom buttons (label max 32 characters, url must start with http:// or https://)
DISCORD_BUTTON_1_LABEL=
DISCORD_BUTTON_1_URL=
DISCORD_BUTTON_2_LABEL=
DISCORD_BUTTON_2_URL=
```

**4. Run manually to test:**
```bash
python3 media_rpc.py
```
---

## Configuration

### USE_SERIES_IMAGE

set this to true if you want to use a series image instead of episode image

### USE_TMDB_IMAGE

set this to true if you want to use TMDB posters instead of the Jellyfin images

### GET_SHOW_YEAR

set this to true if you want to show the year the series started instead of the episode's year

### FORCE_SHOW_EPISODE_INDEX

set this to true if you want episode titles prefixed with season and episode number, e.g. `S01E05 - Title`

### SHOW_TITLE_IN_TOP

set this to true if you want the series name in the top line instead of the episode title

### USE_CHAPTER_TIMESTAMPS

set this to true if you want the Audiobookshelf progress bar to show the current chapter instead of the whole book

### Discord Application ID
1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application
3. Copy the **Application ID** (not a bot token) into `DISCORD_CLIENT_ID`

### Discord User Token
1. log into discord in the browser
2. open browser dev tools (usually ctrl+shift+i or cmd+shift+i)
3. open the network tab
4. refresh page
5. in the search field: search for credentials
6. click the credentials item
7. under "Request Headers", find the "Authorization" part.
8. copy the value and put it into `DISCORD_TOKEN`

it should look something like this `MTIzNDU2Nzg5MDEyMzQ1Njc4.GxKp2A.aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789ab`

### Jellyfin API Key
1. In Jellyfin, go to **Dashboard → API Keys**
2. Create a new key and paste it into `JELLYFIN_API_KEY`

### Jellyfin User ID (Required for Privacy)
To ensure Discord only shows what *you* are watching and ignores other users on your server:
1. Open your Jellyfin web dashboard.
2. Go to **Dashboard → Users** and click on your user profile.
3. Look at the URL in your browser. Copy the long string of letters and numbers after `userId=`. 
4. Paste it into `JELLYFIN_USER_ID` in your `.env` file.

### Audiobookshelf API Token
1. In Audiobookshelf, go to **Settings → Users**
2. Click your user and copy the **API Token**

### TMDB API Key (required for Jellyfin)
1. Create an account at [themoviedb.org](https://www.themoviedb.org/)
2. Go to **Settings → API** and request a key

### Library Blacklist (optional)
To hide specific Jellyfin libraries from showing in RPC, edit the list in the .env or the variable `JELLYFIN_IGNORE_LIBRARIES` in the compose:
```python
JELLYFIN_IGNORE_LIBRARIES = ["Bollywood", "Kids"]
```
```compose
JELLYFIN_IGNORE_LIBRARIES=Bollywood,Kids
```
### Gateway
To use the discord gateway instead of rpc, add
USE_GATEWAY=true and the Discord Token to the .env

### Navidrome salt
just add some string.
NAVIDROME_SALT=averygoodsaltthatshouldberandomandkeptsecret

### Links and buttons (optional)
Set `USE_MEDIA_LINKS=true` to make the title clickable and add buttons that open public pages about what's playing, when your media server has the ids for it:

| Server | Links |
| --- | --- |
| Jellyfin | IMDb and TMDB for movies, IMDb for episodes, MusicBrainz for music |
| Audiobookshelf | Audible (ASIN) and Open Library (ISBN) for books, Apple Podcasts (iTunes ID) for podcasts |
| Navidrome | MusicBrainz |

You can also add up to two custom buttons with a label (max 32 characters) and an `http://` or `https://` url:
```bash
DISCORD_BUTTON_1_LABEL=My Letterboxd
DISCORD_BUTTON_1_URL=https://letterboxd.com/yourname
```
Discord shows at most two buttons, custom buttons come first and media links fill the remaining slots. Discord does not show the buttons on your own profile, check them from another account.

Links are visible to everyone who can see your presence, so media links only point to those public sites and never to your media server.
---

## Cover Art Setup

Discord fetches cover images directly from the URL you provide, which means your media server needs to be publicly accessible. Since Audiobookshelf requires authentication, you need to set up an **authenticated proxy route** in your reverse proxy. This lets Discord access cover art via a short, clean URL, while your token stays on the server and is never exposed.

This only makes cover artwork publicly accessible - not your audio files or any other data.

### Caddy
```caddy
your-abs-domain.com {
    handle /cover/* {
        rewrite * /api/items/{http.request.uri.path.1}/cover
        reverse_proxy localhost:13378 {
            header_up Authorization "Bearer YOUR_ABS_TOKEN"
        }
    }

    reverse_proxy localhost:13378
}
```

### Nginx
```nginx
location /cover/ {
    rewrite ^/cover/(.*)$ /api/items/$1/cover break;
    proxy_pass http://localhost:13378;
    proxy_set_header Authorization "Bearer YOUR_ABS_TOKEN";
}
```

### Apache
```apache
RewriteRule ^/cover/(.*)$ /api/items/$1/cover [PT]
RequestHeader set Authorization "Bearer YOUR_ABS_TOKEN"
ProxyPass /cover/ http://localhost:13378/api/items/
```

After setup, test it by opening this in your browser (no login required):
```
[https://your-abs-domain.com/cover/ANY_LIBRARY_ITEM_ID](https://your-abs-domain.com/cover/ANY_LIBRARY_ITEM_ID)
```

For Jellyfin, no extra proxy setup is needed - Jellyfin serves cover art without authentication, so your API key is never put in the image URL. For Navidrome, the script asks the server for a signed public cover link, so your Navidrome credentials are never put in the image URL either.

---

## Running as a Background Service (Linux)

Because Discord runs under your personal user account, this must be set up as a **User Service**, not a system-wide root service. Do not use `sudo` for these steps.

**1. Create the user systemd directory:**
```bash
mkdir -p ~/.config/systemd/user
```

**2. Create the service file:**
```bash
nano ~/.config/systemd/user/media-rpc.service
```

**3. Paste the following configuration:**
*(Make sure to replace `/home/YOUR_USERNAME/path/to/` with the actual absolute path to your cloned folder!)*
```ini
[Unit]
Description=Media Discord RPC
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /home/YOUR_USERNAME/path/to/media-rpc/media_rpc_gateway.py # or use local if you want to run discord still
WorkingDirectory=/home/YOUR_USERNAME/path/to/media-rpc/
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
```

**4. Enable and start the service:**
```bash
systemctl --user daemon-reload
systemctl --user enable --now media-rpc.service
```

**5. Check the live logs:**
```bash
journalctl --user -u media-rpc.service -f
```

---

## How It Works

Every 15 seconds, the script polls your media servers for active sessions. If something is playing, it constructs a Rich Presence payload with the title, state, timestamps, and cover art, then sends it to Discord over a local Unix socket. Cover URLs are cached in `cover_cache.json` so they are only fetched once per item. If nothing is playing, the presence is cleared.

---

## Troubleshooting

**RPC not showing**
- Make sure Discord is running, and your status is not set to invisible
- Confirm `DISCORD_CLIENT_ID` is the Application ID, not a bot token

**Cover art showing a dice/placeholder icon**
- Your image URL is likely not publicly accessible, or exceeds Discord's 256-character URL limit
- Follow the [Cover Art Setup](#cover-art-setup) instructions for your reverse proxy

**Audiobookshelf not showing**
- The script detects playback by comparing the position between polls - it needs two cycles to confirm something is playing, so there may be a brief delay on startup
- Make sure `ABS_SERVER` has no trailing slash

**Jellyfin not showing**
- Paused sessions are intentionally ignored
- Check that your `JELLYFIN_API_KEY` is valid and your server is reachable

**Navidrome not showing**
- Assumed Paused sessions are intentionally ignored
- make sure your server is reachable and passwords are correct

**IPV6 not working well with docker**
- read the ipv6 docker documentation and verify you've got it correctly https://docs.docker.com/engine/daemon/ipv6/