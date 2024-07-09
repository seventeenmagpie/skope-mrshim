#!/usr/bin/env python3

import selectors
import socket
import sys
import traceback

from server_packets import Message, CommandRecieved, server_logger



class GenericClient():
    def __init__(self, conn, addr, message, id):
        self.conn = conn
        self.addr = addr
        self.message = message
        self.id = id

# TODO: this really doesn't need to be a class. it only gets used once.
class ShimmingServer():
    def __init__(self):
        self.running = True
        self.shimming = False
        self.connected_clients = {}
        self.sel = selectors.DefaultSelector()
        self.last_used_id = 0
        self.id = 0

        # TODO: load from config.toml
        self.host = "127.0.0.1"
        self.port = 65432

    def _generate_id(self):
        self.last_used_id += 1
        return self.last_used_id

    def start(self):
        self.lsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Avoid bind() exception: OSError: [Errno 48] Address already in use
        self.lsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.lsock.bind((self.host, self.port))
        self.lsock.listen()
        print(f"Listening on {(self.host, self.port)}")
        server_logger.info(f"Listening on {(self.host, self.port)}")
        self.lsock.setblocking(False)
        self.sel.register(self.lsock, selectors.EVENT_READ, data=None)

    def handle_command_string(self, command_string):
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
            # print a stuts message
            print(f"Server {'is' if self.running else 'is not'} running and shimming is {'enabled' if self.shimming else 'disabled'}.")


    def accept_wrapper(self, sock):
        # TODO: create a generic client object and use it to store its address and such
        # so that we can send currents to a particular client &c..
        conn, addr = sock.accept()  # Should be ready to read

        print(f"Accepted connection from {addr}")
        conn.setblocking(False)
        message = Message(self.sel, conn, addr)
        generated_id = self._generate_id()
        new_client = GenericClient(conn, addr, message, generated_id)
        id = new_client.id
        self.connected_clients[id] = new_client
        self.sel.register(conn, selectors.EVENT_READ, data=message)

    def main_loop(self):
        # uses the selector to get the current task (either read a packet, write a packet)
        # events is a tuple with a key (which will be a server Packet object here)
        # and a mask, which will be a selector.EVENT_ thing, 
        # these are then used by the packet code (.process_events) to do things.
        events = self.sel.select(timeout=None)

        server_logger.debug(f"There are {len(events)} things in events.")
        for key, mask in events:
            server_logger.debug(f"mask is {mask}")

            if key.data is None:  # this is a new socket, we should accept it.
                self.accept_wrapper(key.fileobj)
            else:
                if key.data.request:
                    server_logger.debug(f"Key request is {key.data.request}")

                message = key.data
                try:
                    message.process_events(mask)
                except CommandRecieved as command_string:
                    # commands get back to the server by raising this exception
                    # print(f"In main loop. Command {command_string} recieved.")
                    # str is so we go from an exception string to a real string we can compare with.
                    self.handle_command_string(str(command_string))
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
    # TODO: disconnect all clients
    for id, client in server.connected_clients.items():
        pass
    server.sel.close()
    print("Have a nice day :) - mags")

