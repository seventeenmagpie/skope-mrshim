#!/usr/bin/env python3

import socket
import sys
import traceback
import selectors

#import libserver  # contains server packet-handling code

# config values
# TODO: read these from an actual config file. i think there's a standard library thing for this.
HOST = "127.0.0.1"
PORT = 65432

sel = selectors.DefaultSelector()

def accept_wrapper(sock):
    """Accept the connection to a socket. Add it to the selector."""
    conn, addr = sock.accept()
    print(f"Accepted connection from {addr}")
    conn.setblocking(False)
    # TODO create packet structure class.
    message =  None # libserver.Message(sel, conn, addr)
    sel.register(conn, selectors.EVENT_READ, data = message)
  
# TODO read from a config file.
host, port = HOST, PORT
lsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# socket.SO_REUSEADDR is so we can have multiple connections
lsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
lsock.bind((host, port))
lsock.listen()
print(f"Listening on {(host, port)}")
lsock.setblocking(False)
sel.register(lsock, selectors.EVENT_READ, data = None)

try:
    while True:
        events = sel.select(timeout = None)
        for key, mask in events:
            if key.data is None:  # we have hearda socket.
                accept_wrapper(key.fileobj)
            else:
                message = key.data
                try:
                    message.process_events(mask)
                except Exception:
                    print(
                        f"Main: Error: Exception for {message.addr}:\n"
                        f"{traceback.format_exc()}"
                        )
                    message.close()
except KeyboardInterrupt:
    print("Caught keyboard interrupt, goodbye!")
finally:
    sel.close()