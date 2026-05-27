# Gateway connection
import sys
import time

import requests

from discord_connection import client_properties
from discord_connection.gateway import Gateway

mp_url_cache = {}


class DiscordGatewayHandler:

    def __init__(self, token, client_id):
        print("Connecting via Gateway...")
        self.gateway = self.setup_gateway(token)
        self.token = token
        self.client_id = client_id

    def setup_gateway(self, DISCORD_TOKEN):
        client_prop = client_properties.get_default_properties()
        client_prop_gateway = client_properties.add_for_gateway(client_prop)
        user_agent = client_prop["browser_user_agent"]

        while True:
            try:
                gw = Gateway(DISCORD_TOKEN, None, client_prop_gateway, user_agent)

                gw.connect()
                print("Connecting to Discord gateway...")
                while not gw.get_ready():
                    if gw.error:
                        raise Exception(gw.error)
                    time.sleep(0.2)
                print("Connected to Discord!")
                return gw
            except Exception as e:
                print(f"Gateway error: {e}, retrying in 5s...")
                time.sleep(10)

    def sigint_handler(self, signum, frame):
        print("SIGINT received, shutting down...")
        if self.gateway and self.gateway.get_state() == 1:
            print("Disconnecting from gateway...")
            self.disconnect()
        sys.exit(0)

    def is_connected(self):
        return self.gateway and self.gateway.get_state() == 1

    def disconnect(self):
        if self.gateway:
            print("Disconnecting from gateway...")
            try:
                self.gateway.update_presence("idle", activities=[], afk=True)
                self.gateway.disconnect_ws()
            except Exception as e:
                print(f"Error disconnecting from gateway: {e}")

    def update_presence(self, activity):
        self.pending_activity = activity
        if activity is None:
            if self.gateway and self.gateway.get_state() == 1:
                try:
                    self.gateway.update_presence("idle", activities=[], afk=True)
                    return
                except Exception as e:
                    print(f"Error clearing gateway presence: {e}")
                    return
        small_image = activity["assets"]["small_image"]
        if small_image and small_image.startswith("http"):
            activity["assets"]["small_image"] = self.resolve_mp_url(small_image)
        large_image = activity["assets"]["large_image"]
        if large_image and large_image.startswith("http"):
            activity["assets"]["large_image"] = self.resolve_mp_url(large_image)
        if self.gateway and self.gateway.get_state() == 1:
            try:

                self.gateway.update_presence(
                    "idle",
                    activities=[activity],
                    afk=True,
                )
            except Exception as e:
                print(f"Error updating gateway presence: {e}")

    def resolve_mp_url(self, url):
        """Convert an external image URL to a Discord mp:external/... proxy URL."""
        if url in mp_url_cache:
            return mp_url_cache[url]
        try:
            resp = requests.post(
                f"https://discord.com/api/v9/applications/{self.client_id}/external-assets",
                headers={
                    "Authorization": self.token,
                    "Content-Type": "application/json",
                },
                json={"urls": [url]},
                timeout=5,
            )
            data = resp.json()
            if isinstance(data, list) and data:
                mp_url = "mp:" + data[0]["external_asset_path"]
                mp_url_cache[url] = mp_url
                return mp_url
        except Exception as e:
            print(f"[mp:external] Failed to resolve {url}: {e}")
        return url  # fall back to raw url
