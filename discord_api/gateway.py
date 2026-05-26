import base64
import gc
import http.client
import logging
import random
import socket
import ssl
import struct
import threading
import time
import traceback
import urllib
import urllib.parse
import zlib
from threading import Lock

import json

import socks
import websocket
from discord_protos import PreloadedUserSettings
from google.protobuf.json_format import MessageToDict

DISCORD_HOST = "discord.com"
LOCAL_MEMBER_COUNT = 50   # members per guild, CPU-RAM intensive
ZLIB_SUFFIX = b"\x00\x00\xff\xff"
VOICE_FLAGS = 3   # CLIPS_ENABLED and ALLOW_VOICE_RECORDING
DEFAULT_CAPABILITIES = 30717
DEFAULT_INTENTS = 50364033
QOS_HEARTBEAT = True
QOS_PAYLOAD = {"ver": 26, "active": True, "reason": "foregrounded"}
inflator = zlib.decompressobj()
logger = logging.getLogger(__name__)
status_unpacker = struct.Struct("!H")


def zlib_decompress(data):
    """Decompress zlib data, if it is not zlib compressed, return data instead"""
    if len(data) < 4 or data[-4:] != ZLIB_SUFFIX:
        return data
    try:
        return inflator.decompress(data)
    except zlib.error as e:
        logger.error(f"zlib error: {e}")
        print(f"zlib error: {e}")
        return None


def reset_inflator():
    """Resets inflator object"""
    global inflator
    del inflator
    inflator = zlib.decompressobj()   # noqa




class Gateway():
    """Methods for fetching and sending data to Discord gateway through websocket"""

    def __init__(self, token, host, client_prop, user_agent, proxy=None, capablities=None):
        if host:
            host_obj = urllib.parse.urlsplit(host)
            if host_obj.netloc:
                self.host = host_obj.netloc
            else:
                self.host = host_obj.path
        else:
            self.host = DISCORD_HOST

        self.header = [
            "Connection: keep-alive, Upgrade",
            "Sec-WebSocket-Extensions: permessage-deflate",
            f"User-Agent: {user_agent}",
        ]
        self.capabilities = None
        if capablities is not None:
            try:
                self.capabilities = int(capablities)
            except ValueError:
                pass

        self.client_prop = client_prop
        self.init_time = time.time() * 1000
        self.token = token
        self.proxy = urllib.parse.urlsplit(proxy)
        self.run = True
        self.wait = False
        self.state = 0
        self.heartbeat_received = True
        self.sequence = None
        self.resume_gateway_url = ""
        self.session_id = ""
        self.ready = False
        self.my_status = {}
        self.reconnect_requested = False
        self.status_changed = False
        self.user_settings_proto = None
        self.proto_changed = False
        self.legacy = "spacebar" in self.host
        self.token_update = None
        self.error = None
        self.resumable = False
        self.state_lock = Lock()  # protect state changes
        self.heartbeat_missed_count = 0  # track missed heartbeats
        threading.Thread(target=self.thread_guard, daemon=True, args=()).start()


    def thread_guard(self):
        """Check if reconnect is requested and run reconnect thread if its not running"""
        while self.run:
            if self.reconnect_requested:
                self.reconnect_requested = False
                if not self.reconnect_thread.is_alive():
                    self.reconnect_thread = threading.Thread(target=self.reconnect, daemon=True, args=())
                    self.reconnect_thread.start()
            time.sleep(0.5)


    def connect_ws(self, resume=False):
        """Connect to websocket"""
        if resume and self.resume_gateway_url:
            gateway_url = self.resume_gateway_url
        else:
            gateway_url = self.gateway_url
        self.ws = websocket.WebSocket()
        if self.proxy.scheme:
            self.ws.connect(
                gateway_url + "/?v=9&encoding=json&compress=zlib-stream",
                header=self.header,
                proxy_type=self.proxy.scheme,
                http_proxy_host=self.proxy.hostname,
                http_proxy_port=self.proxy.port,
            )
        else:
            self.ws.connect(gateway_url + "/?v=9&encoding=json&compress=zlib-stream", header=self.header)


    def disconnect_ws(self, timeout=2, status=1000):
        """Close websocket with timeout"""
        if self.ws:
            try:
                self.ws.settimeout(timeout)
                self.ws.close(status=status)
                logger.info(f"Disconnected with status code {status}")
                print(f"Disconnected with status code {status}")
            except Exception as e:
                logger.warning("Error closing websocket:", e)
                print("Error closing websocket:")
            finally:
                self.ws = None


    def connect(self):
        """Create initial connection to Discord gateway"""
        # get proxy
        if self.proxy.scheme:
            if self.proxy.scheme.lower() == "http":
                connection = http.client.HTTPSConnection(self.proxy.hostname, self.proxy.port)
                connection.set_tunnel(self.host, port=443)
            elif "socks" in self.proxy.scheme.lower():
                proxy_sock = socks.socksocket()
                proxy_sock.set_proxy(socks.SOCKS5, self.proxy.hostname, self.proxy.port)
                proxy_sock.connect((self.host, 443))
                ssl_context = ssl.create_default_context()
                ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
                proxy_sock = ssl_context.wrap_socket(proxy_sock, server_hostname=self.host)
                proxy_sock.do_handshake()   # seems like its not needed
                connection = http.client.HTTPSConnection(self.host, 443)
                connection.sock = proxy_sock
            else:
                logger.warning("Invalid proxy, continuing without proxy")
                print("Invalid proxy, continuing without proxy")
                connection = http.client.HTTPSConnection(self.host, 443)
        else:
            connection = http.client.HTTPSConnection(self.host, 443)

        # get gateway url
        try:
            # subscribe works differently in v10
            connection.request("GET", "/api/v9/gateway")
        except (socket.gaierror, TimeoutError):
            connection.close()
            logger.warning("No internet connection. Exiting...")
            raise SystemExit("No internet connection. Exiting...")
        response = connection.getresponse()
        if response.status == 200:
            data = response.read()
            connection.close()
            self.gateway_url = json.loads(data)["url"]
        else:
            connection.close()
            logger.error(f"Failed to get gateway url. Response code: {response.status}. Exiting...")
            raise SystemExit(f"Failed to get gateway url. Response code: {response.status}. Exiting...")

        self.connect_ws()
        with self.state_lock:
            self.state = 1
        self.heartbeat_interval = int(json.loads(zlib_decompress(self.ws.recv()))["d"]["heartbeat_interval"])
        self.receiver_thread = threading.Thread(target=self.safe_function_wrapper, daemon=True, args=(self.receiver, ))
        self.receiver_thread.start()
        self.heartbeat_thread = threading.Thread(target=self.send_heartbeat, daemon=True)
        self.heartbeat_thread.start()
        self.reconnect_thread = threading.Thread()
        self.authenticate()


    def safe_function_wrapper(self, function, args=()):
        """
        Wrapper for a function running in a thread that captures error and stores it for later use.
        Error can be accessed from main loop and handled there.
        """
        try:
            function(*args)
        except BaseException as e:
            self.error = "".join(traceback.format_exception(e))


    def send(self, request):
        """Send data to gateway"""
        try:
            self.ws.send(json.dumps(request))
        except websocket._exceptions.WebSocketException:
            self.reconnect_requested = True


    def set_my_user_data(self, data):
        """Set my user data from user object"""
        tag = None
        if data.get("primary_guild") and "tag" in data["primary_guild"]:   # spacebar_fix - get
            tag = data["primary_guild"]["tag"]
        if data.get("bot"):
            extra_data = None
        else:
            extra_data = {
                "avatar": data["avatar"],
                "avatar_decoration_data": data.get("avatar_decoration_data"),   # spacebar_fix - get
                "discriminator": data["discriminator"],
                "flags": data.get("flags"),   # spacebar_fix - get
                "premium_type": data["premium_type"],
            }
        self.my_user_data = {
            "id": data["id"],
            "guild_id": None,
            "username": data["username"],
            "global_name": data.get("global_name"),   # spacebar_fix - get
            "nick": None,
            "bio": data.get("bio"),
            "pronouns":  data.get("pronouns"),
            "joined_at": None,
            "tag": tag,
            "bot": data.get("bot"),
            "extra": extra_data,
            "roles": None,
        }
        self.user_changed = True


    def receiver(self):
        """Receive and handle all traffic from gateway, should be run in a thread"""
        logger.debug("Receiver started")
        self.resumable = False
        while self.run and not self.wait:
            try:
                ws_opcode, data = self.ws.recv_data()
            except (
                ConnectionResetError,
                websocket._exceptions.WebSocketConnectionClosedException,
            ):
                self.resumable = True
                break
            if ws_opcode == 8 and len(data) >= 2:
                if not data:
                    self.resumable = True
                    break
                status = status_unpacker.unpack(data[0:2])[0]
                reason = data[2:].decode("utf-8", "replace")
                if status not in (1000, 1001):
                    logger.warning(f"Gateway status code: {status}, reason: {reason}")
                    print(f"Gateway status code: {status}, reason: {reason}")
                if status == 4004:
                    self.run = False
                self.resumable = status in (4000, 4009)
                break
            try:
                data = zlib_decompress(data)
                if data:
                    try:
                        response = json.loads(data)
                        opcode = response["op"]
                    except ValueError:
                        response = None
                        opcode = None
                    del data
                else:
                    response = None
                    opcode = None
            except Exception as e:
                logger.warning(f"Receiver error: {e}")
                print(f"Receiver error: {e}")
                self.resumable = True
                break
            logger.debug(f"Received: opcode={opcode}, optext={response["t"] if (response and "t" in response and response["t"] and "LIST" not in response["t"]) else 'None'}")
            # debug_events
            # if response.get("t"):
            #     debug.save_json(response, f"{response["t"]}.json", False)

            if opcode == 11:
                self.heartbeat_received = True

            elif opcode == 10:
                self.heartbeat_interval = int(response["d"]["heartbeat_interval"])

            elif opcode == 1:
                self.send({"op": 1, "d": self.sequence})

            elif opcode == 0:
                self.sequence = int(response["s"])
                optext = response["t"]
                data = response["d"]
                if optext == "READY":
                    self.resume_gateway_url = data["resume_gateway_url"]
                    self.session_id = data["session_id"]
                    self.ready = False
                    self.my_status = {}

                    # get my user data
                    self.set_my_user_data(data["user"])
                    self.my_id = data["user"]["id"]
                    if data.get("auth_token"):
                        self.token_update = data["auth_token"]

                    # get user settings
                    if "user_settings_proto" in data and not self.legacy:
                        decoded = PreloadedUserSettings.FromString(base64.b64decode(data["user_settings_proto"]))
                        self.user_settings_proto = MessageToDict(decoded)
                    else:
                        self.legacy = True
                        old_user_settings = data["user_settings"]
                        old_user_settings.update({
                            "status": {
                                "status": old_user_settings.get("status", "online"),
                                "guildFolders": {
                                    "guildPositions": old_user_settings.get("guild_positions"),
                                },
                            },
                        })
                        self.user_settings_proto = old_user_settings
                        if old_user_settings.get("custom_status"):
                            self.user_settings_proto["status"]["customStatus"] = old_user_settings["custom_status"]
                    self.proto_changed = True

                    # READY is huge so lets save some memory
                    del (response, data)
                    data = None
                    gc.collect()

                    self.ready = True

                elif optext == "SESSIONS_REPLACE":
                    # received when new client is connected
                    activities = []
                    for activity in data[0]["activities"]:
                        if activity["type"] in (0, 2):
                            if "assets" in activity:
                                small_text = activity["assets"].get("small_text")
                                large_text = activity["assets"].get("large_text")
                            else:
                                small_text = None
                                large_text = None
                            activities.append({
                                "type": activity["type"],
                                "name": activity["name"],
                                "state": activity.get("state", ""),
                                "details": activity.get("details", ""),
                                "small_text": small_text,
                                "large_text": large_text,
                            })
                    self.my_status = {
                        "activities": activities,
                    }
                    self.status_changed = True

                elif optext == "USER_SETTINGS_PROTO_UPDATE":
                    if data["partial"] or data["settings"]["type"] != 1:
                        continue
                    decoded = PreloadedUserSettings.FromString(base64.b64decode(data["settings"]["proto"]))
                    self.user_settings_proto = MessageToDict(decoded)
                    self.proto_changed = True

                elif optext == "USER_UPDATE":
                    self.set_my_user_data(data)


            elif opcode == 7:
                logger.info("Host requested reconnect")
                print("Host requested reconnect")
                self.resumable = True
                break

            elif opcode == 9:
                if response["d"]:
                    logger.info("Session invalidated, reconnecting")
                    print("Session invalidated, reconnecting")
                    break

        with self.state_lock:
            self.state = 0
        logger.debug("Receiver stopped")
        self.reconnect_requested = True
        self.heartbeat_running = False


    def send_heartbeat(self):
        """Send heartbeat to gateway, if response is not received, triggers reconnect, should be run in a thread"""
        logger.debug(f"Heartbeater started, interval={self.heartbeat_interval/1000} s")
        self.heartbeat_running = True
        self.heartbeat_received = True
        # wait for ready event for some time
        elapsed_time = 0
        timeout = max(15, self.heartbeat_interval / 1000 * 5)  # 5x heartbeat interval, minimum 15 seconds
        while not self.ready:
            if elapsed_time >= timeout:
                logger.error("Ready event could not be processed in time, probably because of too many servers. Exiting...")
                raise SystemExit("Ready event could not be processed in time, probably because of too many servers. Exiting...")
            time.sleep(0.5)
            elapsed_time += 0.5
        # Use minimum jitter of 0.75 to avoid heartbeats arriving too early
        jitter = max(0.75, 0.8 - 0.6 * random.random())
        heartbeat_interval_rand = int(self.heartbeat_interval * jitter / 1000)
        heartbeat_sent_time = int(time.time())
        time_spent_event_time = int(time.time()) - 1990   # send it 10s after start, then every 30min
        self.heartbeat_missed_count = 0
        while self.run and not self.wait and self.heartbeat_running:
            send_time_spent_event = not self.legacy and int(time.time()) - time_spent_event_time >= 1800
            if send_time_spent_event:
                self.send({
                    "op": 41,
                    "d": {
                        "initialization_timestamp": self.init_time,
                        "session_id": self.client_prop["client_heartbeat_session_id"],
                        "client_launch_id": self.client_prop["client_launch_id"],
                    },
                })
                logger.debug("Sent Time Spent event")
                time_spent_event_time = int(time.time())
            if time.time() - heartbeat_sent_time >= heartbeat_interval_rand or send_time_spent_event:
                if QOS_HEARTBEAT and not self.legacy:
                    self.send({
                        "op": 1,
                        "d": {
                            "seq": self.sequence,
                            "qos": QOS_PAYLOAD,
                        },
                    })
                else:
                    self.send({"op": 1, "d": self.sequence})
                heartbeat_sent_time = int(time.time())
                logger.debug("Sent heartbeat")
                if not self.heartbeat_received:
                    self.heartbeat_missed_count += 1
                    logger.warning(f"Heartbeat reply not received ({self.heartbeat_missed_count}/3)")
                    print(f"Heartbeat reply not received ({self.heartbeat_missed_count}/3)")
                    if self.heartbeat_missed_count >= 3:
                        logger.warning("Too many missed heartbeats, reconnecting")
                        print("Too many missed heartbeats, reconnecting")
                        self.resumable = True
                        break
                else:
                    self.heartbeat_missed_count = 0
                self.heartbeat_received = False
                jitter = max(0.75, 0.8 - 0.6 * random.random())
                heartbeat_interval_rand = int(self.heartbeat_interval * jitter / 1000)
            # sleep(heartbeat_interval * jitter), but jitter is limited to (0.75 - 0.8)
            # in this time heartbeat ack should be received from discord
            time.sleep(1)
        with self.state_lock:
            self.state = 0
        logger.debug("Heartbeater stopped")
        self.reconnect_requested = True


    def authenticate(self):
        """Authenticate client with discord gateway"""
        payload = {
            "op": 2,
            "d": {
                "token": self.token,
                "capabilities": self.capabilities or DEFAULT_CAPABILITIES,
                "properties": self.client_prop,
                "presence": {
                    "activities": [],
                    "status": "online",
                    "since": None,
                    "afk": False,
                },
            },
        }
        if self.token.startswith("Bot"):
            payload["d"].pop("capabilities")
            payload["d"]["intents"] = self.capabilities or DEFAULT_INTENTS
        self.send(payload)


    def resume(self):
        """
        Try to resume discord gateway session on url provided by Discord in READY event.
        Return gateway response code, 9 means resumming has failed
        """
        self.ws.close(timeout=0)   # this will stop receiver
        time.sleep(1)   # so receiver ends before opening new socket
        reset_inflator()   # otherwise decompression wont work
        self.ws = websocket.WebSocket()
        try:
            self.connect_ws(resume=True)
        except websocket._exceptions.WebSocketBadStatusException:
            logger.info("Failed to resume connection")
            print("Failed to resume connection")
            return 9
        _ = zlib_decompress(self.ws.recv())
        payload = {"op": 6, "d": {"token": self.token, "session_id": self.session_id, "seq": self.sequence}}
        self.send(payload)
        try:
            op = json.loads(zlib_decompress(self.ws.recv()))["op"]
            logger.debug(f"Connection resumed with code {op}")
            return op or True
        except json.JSONDecodeError:
            logger.info("Failed to resume connection")
            print("Failed to resume connection")
            return 9


    def reconnect(self):
        """Try to resume session, if cant, create new one"""
        if not self.wait:
            with self.state_lock:
                self.state = 2
            logger.info("Trying to reconnect")
        try:
            code = None
            if self.resumable:
                self.resumable = False
                code = self.resume()
            if code == 9 or code is None:
                logger.debug("Restarting connection")
                self.ws.close(timeout=0)   # this will stop receiver
                time.sleep(1)   # so receiver ends before opening new socket
                reset_inflator()   # otherwise decompression wont work
                self.ready = False   # will receive new ready event
                self.ws = websocket.WebSocket()
                self.connect_ws()
                self.authenticate()
            self.wait = False
            # restarting threads
            if not self.receiver_thread.is_alive():
                self.receiver_thread = threading.Thread(target=self.safe_function_wrapper, daemon=True, args=(self.receiver, ))
                self.receiver_thread.start()
            if not self.heartbeat_thread.is_alive():
                self.heartbeat_thread = threading.Thread(target=self.send_heartbeat, daemon=True)
                self.heartbeat_thread.start()
            with self.state_lock:
                self.state = 1
            logger.info("Connection established")
            print("Connection established")
        except websocket._exceptions.WebSocketAddressException:
            if not self.wait:   # if not running from wait_oline
                logger.warning("No internet connection")
                print("No internet connection")
                self.ws.close()
                threading.Thread(target=self.wait_online, daemon=True, args=()).start()


    def wait_online(self):
        """Wait for network, try to reconnect every 5s"""
        self.wait = True
        while self.run and self.wait:
            self.reconnect_requested = True
            time.sleep(5)


    def get_state(self):
        """
        Return current state of gateway:
        0 - gateway is disconnected
        1 - gateway is connected
        2 - gateway is reconnecting
        """
        return self.state


    def update_presence(self, status, custom_status=None, custom_status_emoji=None, activities=None, afk=False):
        """Update client status. Statuses: 'online', 'idle', 'dnd', 'invisible', 'offline'"""
        if self.legacy:
            return   # spacebar_fix - gateway returns error if this event is sent

        all_activities = []
        if custom_status:
            all_activities.append({
                "name": "Custom Status",
                "type": 4,
                "state": custom_status,
            })
            if custom_status_emoji:
                all_activities[0]["emoji"] = custom_status_emoji
        if activities:
            for activity in activities:
                all_activities.append(activity)
        print(f"Updating presence: status={status}, custom_status={custom_status}, activities={activities}, afk={afk}")

        payload = {
            "op": 3,
            "d": {
                "status": status,
                "afk": afk,
                "since": 0,
                "activities": all_activities,
            },
        }
        self.send(payload)
        logger.debug("Updated presence")
    



    def get_ready(self):
        """Return wether gateway processed entire READY event"""
        return self.ready

