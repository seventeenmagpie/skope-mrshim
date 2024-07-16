#!/usr/bin/env python3

import selectors
import socket
import sys
import traceback
import tomli

from libraries.client_packets import Message, client_logger, ClientDisconnect
from libraries.name_resolver import registry
from libraries.parser import parse

class CommandPrompt:
    """A class to be the command prompt so that we can put it on the selector and select into at the correct times."""
    def __init__(self, selector, name):
        self.addr = ("command", "prompt")
        self.selector = selector
        self.client_name = name

    def _set_selector_events_mask(self, mode):
        """Set selector to listen for events: mode is 'r', 'w', or 'rw'."""
        if mode == "r":
            events = selectors.EVENT_READ
        elif mode == "w":
            events = selectors.EVENT_WRITE
        elif mode == "rw":
            events = selectors.EVENT_READ | selectors.EVENT_WRITE
        else:
            raise ValueError(f"Invalid events mask mode {mode!r}.")
        self.selector.modify(0, events, data=self)


    def send_command(self):
        """Input a command string from the user, turn it into a request and send it to the server."""

        command_string = input("[shimmer]: ")

        if not command_string:
            print("Please enter a command!")
            return

        command_tokens = parse(command_string)

        if command_tokens[0] == "message":
            action = "relay"
            try:
                request = create_request(action, {
                    "to": command_tokens[1],
                    "from": self.client_name,
                    "content": command_tokens[2]})
            except IndexError: 
                print("Usage: message <to name> \"<message content>\"")
                return
        else:
            action = "command"
            value = command_string
            request = create_request(action, value)

        client_logger.info(f"Created request is: {request}")
        send_request(sock, addr, request)
        # once a command is sent, we shouldn't send another until the response is back
        # NOTE: the response packet will set this back to w.
        self._set_selector_events_mask("r")

    def process_events(self, mask):
        """Called by main loop. Main entry to the prompt, which will either allow a command to be entered or wait for a response."""
        if mask & selectors.EVENT_READ:
            # the selector for the prompt is set back to write mode by the packet once its finished processing.
            pass
        if mask & selectors.EVENT_WRITE:
            self.send_command()

    def close(self):
        print("Closing prompt. Goodbye <3")


def create_request(action, value):
    """Make a requst from the users entry.

    Here, 'type' tells the packet (and then the server) what to do with the content, how to turn it into a header &c.."""
    if action == "search":
        return dict(
            type="text/json",
            encoding="utf-8",
            content=dict(action=action, value=value),
        )
    elif action == "relay":
        # here, value is a dictionary of to: and content:
        return dict(
            type = "relay",
            encoding = "utf-8",
            content = dict(action=action, value=value),
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
    """Try and make a connection to the server, add this socket to the selector."""
    addr = (host, port)
    port = 25000 + console_number
    my_address = (registry[name]["address"], port)

    print(f"Starting connection to {addr}")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # SO_REUSEADDR avoids bind() exception: OSError: [Errno 48] Address already in use 
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(my_address)
    sock.setblocking(False)
    sock.connect_ex(addr)

    events = selectors.EVENT_READ
    # add yourself to the register if successful.
    sel.register(sock, events, data = None)
    client_logger.debug(f"Added {sock} to selector.")
    return sock, addr


def send_request(sock, addr, request):
    """Send a users request to the server by appending data to the selector."""
    events = selectors.EVENT_WRITE
    message = Message(sel, sock, addr, request)
    sel.modify(sock, events, data=message)
    client_logger.debug(f"Modified {sock} in selector.")

# check correct arguments (none)
if len(sys.argv) != 1:
    print(f"Usage: {sys.argv[0]}")
    sys.exit(1)


# create the selector
sel = selectors.DefaultSelector()

console_number = int(input("Enter console number (1 or 2): "))
# TODO: move this into the console object
# do this as part of the general restructuring tomorrow
# when you create a proper generic client class with all
# these methods and so on.
name = "console" + str(console_number)

# connect to the server
host, port = registry["server"]["address"], registry["server"]["port"]
sock, addr = start_connection(host, port) 

# create and register the command prompt.
prompt = CommandPrompt(sel, name)
sel.register(0, selectors.EVENT_WRITE, data=prompt)

debugging = False

try:
    while True:
        events = sel.select(timeout=0)  # get waiting io events. timeout = 0 to wait without blocking.
        #client_logger.debug(f"There are {len(events)} things in events.")
        
        # sort by mask so list now in order read -> write -> read/write
        # NOTE: was included to try and help auto-inbox
        # but command prompt input() is always blocking.
        # auto-inbox no work.
        # TODO: to fix input blocking would need to create a true console gui with something like curses. not now.
        events_sorted_read_priority = sorted(events, key = lambda key_mask_pair: key_mask_pair[1])

        if debugging == True:
            # print("Selector contents:")
            for key, mask in events_sorted_read_priority:
                if key.data is not None:
                    print(f" - Port: {key.data.addr[1]} is in mode {mask},")

        for key, mask in events_sorted_read_priority:
            message = key.data
            try:
                message.process_events(mask)
            except ClientDisconnect:
                print("Disconnected from server.")
                message.close()
                raise KeyboardInterrupt  # to exit the rest of the program.
            except Exception:
                print(
                    f"Main: Error: Exception for {message.addr}:\n"
                    f"{traceback.format_exc()}"
                )
                message.close()


except KeyboardInterrupt:
    print("Exiting program! Take care :)")
finally:
    sel.close()
    sys.exit(0)
