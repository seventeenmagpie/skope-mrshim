#!/usr/bin/env python3

import selectors
import socket
import sys
import traceback

#import libclient  # contains the packet handling code

sel = selectors.DefaultSelector()

def create_request(action, value):
    if action == "shimming":
        return dict(
            type="text/json",
            encoding="ascii",
            content = dict(action = action, value = value))
    else:
        return dict(
            type="binary/custom-client-binary-type",
            encoding="binary",
            content=bytes(action + value, encoding="ascii"),
            )
    
def start_connection(host, port, request):
    addr = (host, port)
    print(f"Starting connection to {addr}")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setblocking(False)
    sock.connect_ex(addr)
    events = selectors.EVENT_READ | selectors.EVENT_WRITE
    message = None # libclient.Message(sel, sock, addr, request)
    sel.register(sock, events, data=message)

# TODO load from config file.    
HOST = "127.0.0.1"
PORT = 65432

if len(sys.argv) != 2:
    print(f"Usage: {sys.argv[0]} <action> <value>")
    sys.exit(1)

host, port = HOST, PORT
action, value = sys.argv[1], sys.argv[2]
request = create_request(action, value)
start_connection(host, port, request)

try:
    while True:
        events = sel.select(timeout = 1)
        for key, mask in events:
            message = key.data
            try:
                message.process_events(mask)
            except Exception:
                print(
                    f"Main: Error: Exception for {message.addr}:\n"
                    f"{traceback.format_exc()}"
                )
                message.close()
        
        # check for a socket being monitored to continue
        if not sel.get_map():
            break
except KeyboardInterrupt:
    print("Caught keyboard interrupt. Goodbye!")
finally:
    sel.close()