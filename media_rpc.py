import os
import signal
import time
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(env_path)


from cache_handler import load_caches
from discord_connection.discord_interface import DiscordHandler
from media_server_connection.media_server_interface import MediaServerInterface

discord_handler = None

mediaServerInterface = None


def startup_checks():
    global discord_handler, mediaServerInterface
    discord_handler = DiscordHandler()
    discord_handler.discord_connector_startup_check()
    mediaServerInterface = MediaServerInterface()
    signal.signal(signal.SIGINT, discord_handler.sigint_handler)


def run_loop():
    while True:
        data = mediaServerInterface.fetch_data()

        if data:
            if discord_handler.USE_GATEWAY:
                if not discord_handler.is_connected():
                    print("Media detected, reconnecting to Discord...")
                    discord_handler.connect()
            else:
                while not discord_handler.is_connected():
                    print("Connection lost, waiting for Discord...")
                    time.sleep(1)

            small_icon = data["client_image"]
            print(
                f"\n[{data.get('text', 'RPC')}] {data['details']} — {data['state']}"
            )
            timestamps = {"start": data["start"], "end": data["end"]}
            activity = {
                "name": data["name"],
                "details": data["details"],
                "state": data["state"],
                "assets": {
                    "large_image": data["cover"],
                    "large_text": data["text"],
                    "small_image": small_icon,
                    "small_text": "Playing",
                },
                "type": data["type"],
                "timestamps": timestamps,
            }
            discord_handler.update_presence(activity)
        else:
            if discord_handler.USE_GATEWAY:
                if discord_handler.is_connected():
                    print("No media playing, disconnecting from Discord...")
                    discord_handler.disconnect()
            else:
                discord_handler.clear_presence()

        time.sleep(15)


def main():
    startup_checks()
    load_caches()
    print("starting media rpc server")
    run_loop()


if __name__ == "__main__":
    main()
