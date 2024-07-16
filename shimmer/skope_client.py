#!/usr/bin/env python3

import selectors
import socket
import sys
import traceback

from libraries.client_packets import Message, client_logger

sel = selectors.DefaultSelector()

"""
Plan:
-----
skope: Should connect,
skope: Wait to be asked,
server: ask for shim currents
skope: trigger Skope acquisition
skope: trigger calculation of currents,
skope: send packet of currents to the server,
server: pass these on to the sinope client,
sinope: write these currents to file to be read by plugin.
"""

def create_request(action, value):
    if action == "search":
        return dict(
            type="text/json",
            encoding="utf-8",
            content=dict(action=action, value=value),
        )
    elif action == "command":
        return dict(
            type = "command",
            encoding = "utf-8",
            content = dict(action=action, value=value),
        )
    else:
        return dict(
            type="binary/custom-client-binary-type",
            encoding="binary",
            content=bytes(action + value, encoding="utf-8"),
        )


def start_connection(host, port):
    addr = (host, port)
    print(f"Starting connection to {addr}")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setblocking(False)
    sock.connect_ex(addr)
    events = selectors.EVENT_READ
    sel.register(sock, events, data = None)
    client_logger.debug(f"Added {sock} to selector.")
    return sock, addr


def send_request(sock, addr, request):
    events = selectors.EVENT_READ | selectors.EVENT_WRITE
    message = Message(sel, sock, addr, request)
    sel.modify(sock, events, data=message)
    client_logger.debug(f"Modified {sock} in selector.")


if len(sys.argv) != 3:
    print(f"Usage: {sys.argv[0]} <host> <port>")
    sys.exit(1)

host, port = sys.argv[1], int(sys.argv[2])
sock, addr = start_connection(host, port)

try:
    while True:
        events = sel.select(timeout=0)
        client_logger.debug(f"There are {len(events)} things in events.")
        for key, mask in events:
            client_logger.debug("mask is {mask}")

            if key.data.response:
                client_logger.debug(f"Key response is {key.data.response}")
           
            message = key.data
            try:
                message.process_events(mask)
            except Exception:
                print(
                    f"Main: Error: Exception for {message.addr}:\n"
                    f"{traceback.format_exc()}"
                )
                message.close()

        # Check for a socket being monitored to continue.
        if value == "disconnect":
            break
except KeyboardInterrupt:
    print("Caught keyboard interrupt, exiting")
finally:
    sel.close()
