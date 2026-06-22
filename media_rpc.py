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
    last_printed = "None"
    last_start_time = None
    activity_key = None
    connected = True
    while True:
        while not discord_handler.is_connected():
            if connected:
                print("Connection lost, waiting for reconnect...")
                connected = False
            time.sleep(1)
        if not connected:
            print("Reconnected.")
            last_printed = None
            last_start_time = None
            connected = True
        data = mediaServerInterface.fetch_data()
        if data:
            small_icon = data["client_image"]
            activity_key = (data["details"], data["state"])
            has_seeked = False
            if last_start_time is not None and abs(data["start"] - last_start_time) > 5000:
                has_seeked = True
            if activity_key == last_printed and not has_seeked:
                time.sleep(15)
                continue            

            print(
                f"\n[{data.get('text', 'RPC')}] {data['details']} — {data['state']}"
            )
            last_printed = activity_key
            last_start_time = data["start"]

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
            if last_printed is not None:
                print("\nNo data")
                last_printed = None
                last_start_time = None
                discord_handler.clear_presence()
        time.sleep(15)


def main():
    startup_checks()
    load_caches()
    print("starting media rpc server")
    run_loop()


if __name__ == "__main__":
    main()
