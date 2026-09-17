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
    paused_since = None
    playing_confirmations = 0

    while True:
        data = mediaServerInterface.fetch_data()

        if data:
            is_paused = data.get("is_paused", False)

            if is_paused and not discord_handler.USE_GATEWAY:
                discord_handler.clear_presence()
                time.sleep(15)
                continue

            if discord_handler.USE_GATEWAY and paused_since is not None:
                if is_paused:
                    playing_confirmations = 0
                else:
                    playing_confirmations += 1
                    if playing_confirmations < 2:
                        print(
                            "Possible resume detected, waiting for confirmation..."
                        )
                        time.sleep(15)
                        continue

                    print("Playback resumed.")
                    paused_since = None
                    playing_confirmations = 0

            if is_paused and discord_handler.USE_GATEWAY:
                if paused_since is None:
                    paused_since = time.monotonic()
                    playing_confirmations = 0

                    if discord_handler.is_connected():
                        activity = {
                            "name": data["name"],
                            "details": data["details"],
                            "state": data["state"],
                            "assets": {
                                "large_image": data["cover"],
                                "large_text": data["text"],
                                "small_image": "https://raw.githubusercontent.com/RayneYoruka/discord-rich-presence-plugin/refs/heads/feat/add-presence-status-configuration/assets/pause.png",
                                "small_text": "Paused",
                            },
                            "type": data["type"],
                            "timestamps": {
                                "start": int(time.time() * 1000),
                            },
                        }
                        discord_handler.update_presence(activity)

                    print("Media paused, starting 5-minute Discord grace period...")

                if time.monotonic() - paused_since >= 300:
                    if discord_handler.is_connected():
                        print("Media paused for 5 minutes, disconnecting from Discord...")
                        discord_handler.disconnect()
                    time.sleep(15)
                    continue

                time.sleep(15)
                continue

            paused_since = None
            playing_confirmations = 0

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
            paused_since = None
            playing_confirmations = 0

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
