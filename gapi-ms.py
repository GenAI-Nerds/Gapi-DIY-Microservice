import asyncio
import threading
import time
import queue
import websockets
import json
import logging
import argparse
import signal
import sys
from message_handler import on_message
from message import GapiMicroServiceMessage

# Default values
DEFAULT_RECONNECT_TIME = 6  # seconds
DEFAULT_KEEP_ALIVE_TIME = 60  # seconds

# Configure logging
logging.basicConfig(filename='websocket_client.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
LOG_TO_STDOUT = True

# Add a StreamHandler to log to stdout if enabled
if LOG_TO_STDOUT:
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console.setFormatter(formatter)
    logging.getLogger('').addHandler(console)

class WebSocketClient(threading.Thread):
    def __init__(self, url, guid, reconnect_time=DEFAULT_RECONNECT_TIME, keep_alive_time=DEFAULT_KEEP_ALIVE_TIME):
        super().__init__(daemon=True)
        self.url = url
        self.guid = guid
        self.reconnect_time = reconnect_time
        self.keep_alive_time = keep_alive_time
        self.queue = queue.Queue()
        self.connected = False
        self.stop_event = threading.Event()
        self.keep_alive_task = None  # To hold the task for cancelling later

    async def connect(self):
    
        while not self.stop_event.is_set():
            try:
                logging.info(f"Connecting to {self.url}, guid: {self.guid}...")
                async with websockets.connect(self.url) as websocket:
                
                    self.websocket = websocket
                    self.connected = True
                    logging.info(f"Connected successfully using guid: {self.guid}")
                    
                    # Send the "hello" message upon successful connection
                    json_object = {
                        "apiServiceName": "microServiceHello",
                        "microServiceKey": self.guid
                    }
                    await self.websocket.send(json.dumps(json_object))
                    
                    # Schedule the first call to send_alive_message
                    self.keep_alive_task = asyncio.create_task(self.send_alive_message())
                    
                    while self.connected and not self.stop_event.is_set():
                        message = await websocket.recv()
                        self.queue.put(message)
                        
            except Exception as e:
                logging.error(f"Connection failed: {e}")
                self.connected = False
                await asyncio.sleep(self.reconnect_time)

    async def send_alive_message(self):
        while self.connected and not self.stop_event.is_set():
            await asyncio.sleep(self.keep_alive_time)
            if self.connected and not self.stop_event.is_set():
                json_object = {
                    "apiServiceName": "ping"
                }
                await self.websocket.send(json.dumps(json_object))

    def run(self):
        asyncio.run(self.connect())

    def stop(self):
        self.stop_event.set()
        if self.keep_alive_task:
            self.keep_alive_task.cancel()
        if hasattr(self, 'loop') and self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)

class MessageProcessor(threading.Thread):
    def __init__(self, websocket_client):
        super().__init__(daemon=True)
        self.websocket_client = websocket_client
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def cleanup(self):
        self.loop.stop()
        self.loop.close()
        
    def run(self):
        while not self.websocket_client.stop_event.is_set():
        
            message = self.websocket_client.queue.get()
            if isinstance(message, bytes):
            
                micro_service_msg = GapiMicroServiceMessage.decode(message)
                
                self.loop.run_until_complete(on_message(micro_service_msg, self.websocket_client.websocket, logging))
                self.websocket_client.queue.task_done()
                continue
               
            else:
            
                logging.info(f"on_message: {message}")
            
                # Parse the JSON string into a Python dictionary
                json_data = json.loads(message)

                if json_data.get("status") == "error":
                    error_description = json_data.get("errorDescription")
                    logging.info(f"Server side error: {error_description}")
                    self.websocket_client.queue.task_done()
                    continue
            
                if json_data.get("microServiceHelloResponse"):
                    logging.info("Got hello ack")
                    self.websocket_client.queue.task_done()
                    continue

                self.websocket_client.queue.task_done()

def signal_handler(signal, frame):
    print('Ctrl+C pressed, exiting gracefully')
    sys.exit(0)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WebSocket client")
    parser.add_argument("server_address", type=str, help="WebSocket server address")
    parser.add_argument("guid", type=str, help="GUID string")
    parser.add_argument("--reconnect-time", type=int, default=DEFAULT_RECONNECT_TIME, help="Reconnect time in seconds (default: 6)")
    parser.add_argument("--keep-alive-time", type=int, default=DEFAULT_KEEP_ALIVE_TIME, help="Keep-alive message time in seconds (default: 60)")
    args = parser.parse_args()

    # Register signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)

    websocket_client = WebSocketClient(args.server_address, args.guid, args.reconnect_time, args.keep_alive_time)
    websocket_client.start()

    message_processor = MessageProcessor(websocket_client)
    message_processor.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Ctrl+C pressed, exiting gracefully")
        websocket_client.stop()
        message_processor.cleanup()  # Add this line to ensure event loop is stopped properly

