import os



class MediaServerInterface:
    
    def __init__(self):
        print("Initializing media server interface...")
        # 1. Jellyfin Config
        self.JELLYFIN_SERVER = os.getenv("JELLYFIN_SERVER")
        self.JELLYFIN_API_KEY = os.getenv("JELLYFIN_API_KEY")
        self.JELLYFIN_USER_ID = os.getenv("JELLYFIN_USER_ID")
        jellyfin_ignore_libraries_tmp = os.getenv("JELLYFIN_IGNORE_LIBRARIES", "")
        self.JELLYFIN_IGNORE_LIBRARIES = jellyfin_ignore_libraries_tmp.split(",") if jellyfin_ignore_libraries_tmp else []
        self.TMDB_API_KEY = os.getenv("TMDB_API_KEY")

        # 2. Audiobookshelf Config
        self.ABS_SERVER = os.getenv("ABS_SERVER")
        self.ABS_API_TOKEN = os.getenv("ABS_API_TOKEN")

        # 3. Navidrome Config
        self.NAVIDROME_USERNAME = os.getenv("NAVIDROME_USERNAME")
        self.NAVIDROME_PASSWORD = os.getenv("NAVIDROME_PASSWORD")
        self.NAVIDROME_SERVER = os.getenv("NAVIDROME_SERVER")
        self.NAVIDROME_SALT = os.getenv("NAVIDROME_SALT")

        self.servers = {}
        self.media_servers_startup_check()
        if self.JELLYFIN_SERVER:
            from .jellyfin_interface import JellyfinServer
            self.servers[self.JELLYFIN_SERVER] = JellyfinServer(self.JELLYFIN_SERVER, self.JELLYFIN_API_KEY, self.JELLYFIN_USER_ID, self.JELLYFIN_IGNORE_LIBRARIES, self.TMDB_API_KEY)
        if self.ABS_SERVER:
            from .audiobookshelf_interface import ABS_Server
            self.servers[self.ABS_SERVER] = ABS_Server(self.ABS_SERVER, self.ABS_API_TOKEN)
        if self.NAVIDROME_SERVER and self.NAVIDROME_USERNAME and self.NAVIDROME_PASSWORD and self.NAVIDROME_SALT:
            from .navidrome_interface import NavidromeServer
            self.servers[self.NAVIDROME_SERVER] = NavidromeServer(self.NAVIDROME_SERVER, self.NAVIDROME_USERNAME, self.NAVIDROME_PASSWORD, self.NAVIDROME_SALT)

    def fetch_data(self):
        if self.servers.get(self.JELLYFIN_SERVER):
            server = self.servers[self.JELLYFIN_SERVER]
            data = server.fetch_data()
            if data:
                return data
        if self.servers.get(self.ABS_SERVER):
            server = self.servers[self.ABS_SERVER]
            data = server.fetch_data()
            if data:
                return data
        if self.servers.get(self.NAVIDROME_SERVER):
            server = self.servers[self.NAVIDROME_SERVER]
            data = server.fetch_data()
            if data:
                return data
        return None


    def media_servers_startup_check(self):
        if not self.JELLYFIN_SERVER and not self.ABS_SERVER and not self.NAVIDROME_SERVER:
            raise EnvironmentError("No media server configured. Please set JELLYFIN_SERVER, ABS_SERVER, and/or NAVIDROME_SERVER_URL in your .env file.")
        if self.JELLYFIN_SERVER and (not self.JELLYFIN_API_KEY or not self.JELLYFIN_USER_ID):
            raise EnvironmentError("Jellyfin server configured but missing JELLYFIN_API_KEY and/or JELLYFIN_USER_ID in .env file.")
        if self.ABS_SERVER and not self.ABS_API_TOKEN:
            raise EnvironmentError("Audiobookshelf server configured but missing ABS_API_TOKEN in .env file.")
        if not self.TMDB_API_KEY and self.JELLYFIN_SERVER:
            raise EnvironmentError(f"Missing required environment variable: TMDB_API_KEY")
        if self.NAVIDROME_SERVER and (not self.NAVIDROME_USERNAME or not self.NAVIDROME_PASSWORD or not self.NAVIDROME_SALT):
            raise EnvironmentError("Navidrome server configured but missing NAVIDROME_USERNAME, NAVIDROME_PASSWORD, or NAVIDROME_SALT in .env file.")