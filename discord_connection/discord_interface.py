import os
import time

from discord_connection.gateway_handler import DiscordGatewayHandler
from discord_connection.rpc_handler import DiscordRPCHandler


class DiscordHandler:

    def __init__(self):
        self.DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
        self.DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
        self.USE_GATEWAY = os.getenv("USE_GATEWAY", "False").lower() == "true"
        self.handler = None
        self.connection_method = None


    def sigint_handler(self,_signum, _frame):
        self.handler.sigint_handler(None, None)


    def connect(self):
        if self.connection_method == "RPC":
            print("connecting via RPC...")
            self.handler = DiscordRPCHandler(self.DISCORD_CLIENT_ID)
        elif self.connection_method == "Gateway":
            self.handler = DiscordGatewayHandler(self.DISCORD_TOKEN, self.DISCORD_CLIENT_ID)

    def discord_connector_startup_check(self):
        if not self.DISCORD_CLIENT_ID:
            print(f"missing DISCORD_CLIENT_ID in .env")
            raise EnvironmentError(
                f"Missing required environment variable: DISCORD_CLIENT_ID"
            )
        if self.USE_GATEWAY and not self.DISCORD_TOKEN:
            print(f"missing DISCORD_TOKEN in .env for gateway mode")
            raise EnvironmentError(
                f"Missing required environment variable: DISCORD_TOKEN for gateway mode"
            )
        if not self.USE_GATEWAY:
            while True:
                try:
                    self.handler = DiscordRPCHandler(self.DISCORD_CLIENT_ID)
                    self.connection_method = "RPC"
                    break
                except Exception as e:
                    print(f"Failed to connect via RPC. Is Discord running? error: {e}. Retrying in 5s...")
                    time.sleep(5)
        elif self.USE_GATEWAY:
            while True:
                try:
                    self.handler = DiscordGatewayHandler(self.DISCORD_TOKEN, self.DISCORD_CLIENT_ID)
                    self.connection_method = "Gateway"
                    break
                except Exception as e:
                    print(f"Failed to connect via Gateway. error: {e}. Retrying in 5s...")
                    time.sleep(5)



    def is_connected(self):
        if self.handler:
            return self.handler.is_connected()
        return False

    def disconnect(self):
        self.handler.disconnect()

    def update_presence(self, activity):
        self.handler.update_presence(activity)

    def clear_presence(self):
        self.update_presence(None)