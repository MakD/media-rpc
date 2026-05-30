import os
import sys
import threading

from pypresence.presence import Presence
import time


class DiscordRPCHandler:
    rpc = None
    def __init__(self, client_id):
        self.client_id = client_id
        self._reconnecting = False
        self.rpc = Presence(client_id)
        while True:
            try:
                self.rpc.connect()
                print("Connected to Discord RPC!")
                break
            except Exception as e:
                print(f"Failed to connect via RPC: {e}.")
                time.sleep(5)

    def sigint_handler(self, signum, frame):
        payload = {
                    "cmd": "SET_ACTIVITY",
                    "args": {"pid": os.getpid(), "activity": None},
                    "nonce": "c",
                }
        try:
            self.rpc.update(payload_override=payload)
        except:
            if self.rpc:
                try:
                    self.rpc.close()
                except:
                    pass
        sys.exit(0)

    def is_connected(self):
        return self.rpc is not None

    def disconnect(self):
        if self.rpc:
            try:
                self.rpc.close()
            except:
                pass
            self.rpc = None

    def update_presence(self, activity):
        if self.rpc:
            try:
                payload = {
                    "cmd": "SET_ACTIVITY",
                    "args": {"pid": os.getpid(), "activity": activity},
                    "nonce": str(time.time()),
                }
                self.rpc.update(payload_override=payload)
            except Exception as e:
                print(f"Error updating RPC presence: {e}")
                self._handle_disconnect()

    def _handle_disconnect(self):
        self.rpc = None
        if not self._reconnecting:
            self._reconnecting = True
            threading.Thread(target=self._reconnect, daemon=True).start()

    def _reconnect(self):
        print("RPC connection lost, reconnecting...")
        while True:
            try:
                rpc = Presence(self.client_id)
                rpc.connect()
                self.rpc = rpc
                print("Reconnected to Discord RPC!")
                self._reconnecting = False
                break
            except Exception as e:
                print(f"Failed to reconnect via RPC: {e}. Retrying in 5s...")
                time.sleep(5)
