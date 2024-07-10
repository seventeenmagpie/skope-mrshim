#!/usr/bin/env python3

import selectors
import socket
import sys
import traceback

from server_packets import Message, CommandRecieved, ClientDisconnect, server_logger

class GenericClient():
    """Represents a generic client object, having a socket, current packet and internal id associated with it."""
    def __init__(self, conn, addr, message, id):
        self.conn = conn
        self.addr = addr
        self.message = message
        self.id = id

# TODO: does this really need to be a class?
class ShimmingServer():
    """Coordinates packets between clients. Has internal state."""
    def __init__(self):
        self.running = True
        self.shimming = False
        self.connected_clients = {}  # stores connected clients. id (int) : client (GenericClient)
        self.sel = selectors.DefaultSelector()
        self.last_used_id = 0
        self.id = 0

        # TODO: load from config.toml
        self.host = "127.0.0.1"
        self.port = 65432

    def _generate_id(self):
        """Generate the next unused internal id.

        The server has an id of 0."""
        self.last_used_id += 1
        return self.last_used_id

    def start(self):
        """Start the server."""

        # open a listening socket to listen for new connections.
        self.lsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # SO_REUSEADDR avoids bind() exception: OSError: [Errno 48] Address already in use 
        self.lsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.lsock.bind((self.host, self.port))
        self.lsock.listen()
        print(f"Listening on {(self.host, self.port)}")
        server_logger.info(f"Listening on {(self.host, self.port)}")
        self.lsock.setblocking(False)
        # adds this socket to the register is a read type io.
        self.sel.register(self.lsock, selectors.EVENT_READ, data=None)

    def handle_command_string(self, command_string: str):
        """Handle a the command part of a 'command' type packet."""
        # TODO: add a parser and so on. use the frynab cli stuff.
        if command_string == "halt":
            print("Halting server")
            self.running = False
        elif command_string == "start":
            print("Starting shimming")
            self.shimming = True
        elif command_string == "stop":
            print("Stopping shimming")
            self.shimming = False
        elif command_string == "list":
            print("Listing connected clients:")
            for id, client in self.connected_clients.items():
                print(f" - id:{id} @ {client.addr[0]}:{client.addr[1]},")
        elif command_string == "status":
            print(f"Server {'is' if self.running else 'is not'} running and shimming is {'enabled' if self.shimming else 'disabled'}.")


    def accept_wrapper(self, sock):
        """Accept a new client's connection."""
        conn, addr = sock.accept()  # new socket for the client.
        print(f"Accepted connection from {addr}")
        conn.setblocking(False)
        # create a message object to do the talking on.
        message = Message(self.sel, conn, addr)

        # create a GenericClient object for keeping track of who is connected.
        generated_id = self._generate_id()
        new_client = GenericClient(conn, addr, message, generated_id)
        id = new_client.id
        self.connected_clients[id] = new_client

        # add the new client to the selector, we're ready to listen to it.
        self.sel.register(conn, selectors.EVENT_READ, data=message)

    def main_loop(self):
        """Choose the socket to send/recieve on and do that. Catch commands and disconnects."""
        events = self.sel.select(timeout=None)  # set of waiting io

        server_logger.debug(f"There are {len(events)} things in events.")
        for key, mask in events:  # iterate through waiting sockets.
            # key is a NamedTuple with the socket number and data=message. mask is the io type.
            server_logger.debug(f"mask is {mask}")

            if key.data is None:  # this is a new socket, we should accept it.
                self.accept_wrapper(key.fileobj)
            else:  # otherwise we should process it.
                if key.data.request:
                    server_logger.debug(f"Key request is {key.data.request}")
            
                message = key.data
                try:
                    message.process_events(mask)
                # during processing, one of the folliwng special exceptions may arise.
                except CommandRecieved as command_string:
                    self.handle_command_string(str(command_string))  # str() because exceptions object is not a string.
                except ClientDisconnect as disconnect_addr:
                    # remove from internal list of clients
                    for id, client in self.connected_clients.items():
                        if str(client.addr) == str(disconnect_addr):
                            print(f"Removed client {client.id} which was at {client.addr}")
                            del client
                            break
                    del self.connected_clients[id]
                except Exception:
                    print(
                        f"Main: Error: Exception for {message.addr}:\n"
                        f"{traceback.format_exc()}"
                    )
                    message.close()
  

if len(sys.argv) != 1:
    print(f"Usage: {sys.argv[0]}")
    sys.exit(1)

server = ShimmingServer()

server.start()

try:
    # TODO: write a better server stop system.
    # if running is false, it should go through and do all the remaining write events and close
    # everything that's on the server.
    # this is a crash-stop.
    # ideally we would finish processing the events in the for loop
    # before we actually close the server.
    while server.running:
        server.main_loop()
except KeyboardInterrupt:
    print("Caught keyboard interrupt, exiting")
finally:
    # TODO: disconnect all clients nicely.
    for id, client in server.connected_clients.items():
        pass
    server.sel.close()
    print("Have a nice day :) - mags")

