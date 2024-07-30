#!/usr/bin/env python3

import selectors
import socket
import sys
import traceback
import copy

import libraries.registry as registry
from libraries.parser import parse
from libraries.server_packets import Message, server_logger
from libraries.exceptions import CommandRecieved, ClientDisconnect

debugging = False


class ModelClient:
    """Represents a generic client object, having a socket, current packet and internal id associated with it."""

    def __init__(self, conn, addr, id, name):
        self.socket = conn
        self.addr = addr
        self.id = id
        self.name = name  # the role name for this client generic client object.


# NOTE: does this really need to be a class?
# yes, so we can pass it to the packet object to respond to commands.
class ShimmingServer:
    """Coordinates packets between clients. Has internal state."""

    def __init__(self):
        self.running = True
        self.shimming = False
        self.sel = selectors.DefaultSelector()
        self.last_used_id = 0
        self.id = 0

        self.address = registry.get_address("server")
        self.host = self.address[0]
        self.port = self.address[1]

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

    def handle_command(self, command_string):
        """Handle a the command part of a 'command' type packet."""
        command_tokens = parse(command_string)
        if command_tokens[0] == "halt":
            print("Halting server")
            self.running = False
        elif command_tokens[0] == "start": 
            # TODO: make these mrshim client commands and make them actually do something there
            print("Starting shimming")
            self.shimming = True
        elif command_tokens[0] == "stop":
            print("Stopping shimming")
            self.shimming = False
        elif command_tokens[0] == "list":
            print("Listing connected clients:")
            for name, client in registry.clients_on_registry.items():
                print(f" - {name}({client.id}) @ {client.addr[0]}:{client.addr[1]},")
        elif command_tokens[0] == "status":
            print(
                f"Server {'is' if self.running else 'is not'} running and shimming is {'enabled' if self.shimming else 'disabled'}."
            )

    def accept_wrapper(self, sock):
        """Accept a new client's connection."""
        conn, addr = sock.accept()  # new socket for the client.
        print(f"Accepted connection from {addr}")
        conn.setblocking(False)
        # create a message object to do the talking on.
        message = Message(self.sel, conn, addr, self)
        name_assigned = False

        # work out which role the newly connected client is by comparing against the directory registry file.
        for role in registry.registry.sections():
            reg_address = registry.get_address(role)
            name_assigned = False

            if (addr[0] == reg_address[0]) and (addr[1] == reg_address[1]): 
                name_assigned = True
                break  # role = the current role

        if not name_assigned:
            # matlab won't let me connect with a static ip,
            # so we need to rewrite the config file to match the actual ip
            # NOTE: may change when matlab implementation done with python.
            role = "matlab"
            registry.registry["matlab"]["address"] = addr[0]
            registry.registry["matlab"]["port"] = str(addr[1])

        print(f"{role} just connected.")
        # create a GenericClient object for keeping track of who is connected.
        generated_id = self._generate_id()
        new_client = ModelClient(conn, addr, generated_id, role)
        registry.clients_on_registry[role] = new_client

        # add the new message to the selector, we're ready to listen to it.
        self.sel.register(conn, selectors.EVENT_READ, data=message)

    def main_loop(self):
        """Choose the socket to send/recieve on and do that. Catch commands and disconnects."""
        events = self.sel.select(timeout=None)  # set of waiting io

        for key, mask in events:  # iterate through waiting sockets.
            # key is a NamedTuple with the socket number and data=message. mask is the io type.
            if key.data is None:  # this is a new socket, we should accept it.
                self.accept_wrapper(key.fileobj)
            else:  # otherwise we should process it.
                if key.data.request:
                    server_logger.debug(f"Key request is {key.data.request}")

                self.current_message = key.data
                try:
                    self.current_message.process_events(mask)
                # during processing, one of the folliwng special exceptions may arise.
                except ClientDisconnect as disconnect_addr:
                    # remove from internal list of clients
                    for name, client in registry.clients_on_registry.items():
                        if str(client.addr) == str(disconnect_addr):
                            print(
                                f"Removed client {client.name} which was at {client.addr}"
                            )
                            del client
                            break
                    del registry.clients_on_registry[name]
                except Exception:
                    print(
                        f"Main: Error: Exception for {self.current_message.addr}:\n"
                        f"{traceback.format_exc()}"
                    )
                    self.current_message.close()


if len(sys.argv) != 1:
    print(f"Usage: {sys.argv[0]}")
    sys.exit(1)

server = ShimmingServer()
server.start()

try:
    while server.running:
        server.main_loop()
except KeyboardInterrupt:
    print("Caught keyboard interrupt, exiting")
finally:
    # TODO: disconnect all clients nicely.
    server.sel.close()
    print("Have a nice day :) - mags")
