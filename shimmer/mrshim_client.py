#!/usr/bin/env python3

import selectors
import sys
import traceback
import os  # for os.linesep one time

from libraries.exceptions import ClientDisconnect
import libraries.parser as parser
from libraries.generic_client import Client
from libraries.client_packets import Message
from libraries.printers import selector_printer

JUPITER_PLUGGED_IN = False
if JUPITER_PLUGGED_IN:
    import libraries.hwio as mrshim


class SinopeClient(Client):
    """A class for Sinope. Handles !shim commands and writes shim currents to the file."""

    def __init__(self, name):
        super().__init__(name)
        self.start_connection()
        self.channel_number = 24
        self.currents = [0 for _ in range(1, self.channel_number)]

        # because we never send anything first, we need to create the Message object for this client manually.
        events = selectors.EVENT_READ
        message = Message(self.selector, self.socket, self.server_address, None, self)
        self.selector.modify(self.socket, events, data=message)
        self.logger.debug(f"Added packet to {self.name}")

        # setting up the file to write shim currents to.
        # w mode clears the old shims
        self.shimming_file = open("shims.txt", "w", encoding="utf-8")

        if JUPITER_PLUGGED_IN:
            device_name = ""
            mrshim.LinkupHardware(
                device_name, 1, None  # safe mode is on (ramps currents),
            )
            mrshim.LoadShimSets("shims.txt")
            mrshim.ApplyShimManually("reset")

    def _clear(self):
        """Clear the buffers and sentinels ready to do the next thing."""
        self.client.logger.debug(f"_clear called. self.is_relay is {self.is_relay}")
        self.request = None
        self._recv_buffer = b""
        self._send_buffer = b""
        self._request_queued = False
        self._jsonheader_len = None
        self.jsonheader = None
        self.response = None
        self.is_relay = False

        # NOTE: *_client.py sets this back to write once a command is recieved.
        self._set_selector_events_mask("r")
        self.logger.debug(
            f"After clear, mask is {self.selector.get_key(self.sock).events}"
        )

    def write_shims_to_file(self):
        """Decide what to do with the shim values."""
        if JUPITER_PLUGGED_IN:
            self.send_shims_to_jupiter()
        else:
            # puts the currents in the way sinope likes them.
            # (space delimited floats)
            formatted_currents = (
                " ".join(["{:5.4f}".format(current) for current in self.currents])
                + os.linesep  # this doesn't seem to do anything??
            )
            self.shimming_file.write(formatted_currents)
            self.shimming_file.flush()

    def send_shims_to_jupiter(self):
        # TODO: do more interesting checks.
        max = 2
        for idx, current in enumerate(self.currents):
            if abs(current) > max:
                print(f"Current exceeds safe maximum +/-{max}. Setting to 0A.")
                self.currents[idx] = 0
        mrshim.ApplyShimSet(self.currents)
        print(mrshim.HardwareReport())

    def process_events(self, mask):
        """Called by main loop. Main entry to the prompt, which will either allow a command to be entered or wait for a response."""
        # this client doesn't actually do anything to the server itself.
        # it just waits for shims to be sent to it and then writes them to the file.
        if mask & selectors.EVENT_READ:
            self.write_shims_to_file()
            return mask
        if mask & selectors.EVENT_WRITE:
            # to prevent packet writing, set mask to read.
            # also need to make selector accordingly.
            message = self.selector.get_key(self.socket).data
            self.selector.modify(self.socket, selectors.EVENT_READ, data=message)
            return 1

    def create_request(self, action, value):
        """Make a requst from the users entry.

        Here, 'type' tells the packet (and then the server) what to do with the content, how to turn it into a header &c..
        """
        self.logger.debug("inside create request")
        self.logger.debug(f"action is {action}, value is {value}")
        if action == "relay":
            self.logger.debug("detected in relay section")
            return dict(
                type="relay",
                encoding="utf-8",
                content=value,
            )
        elif action == "command":
            return dict(
                type="command",
                encoding="utf-8",
                content=value,
            )
        else:
            return dict(
                type="binary/custom-client-binary-type",
                encoding="binary",
                content=bytes(action + value, encoding="utf-8"),
            )

    def main_loop(self):
        events = self.selector.select(
            timeout=0
        )  # get waiting io events. timeout = 0 to wait without blocking.
        # TODO: fasten to global debugging flag
        # selector_printer(self.selector, events)

        for key, mask in events:
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

    def handle_command(self, command_string):
        command_tokens = parser.parse(command_string)
        self.logger.debug(f"Recieved command tokens are {command_tokens}")
        try:
            if command_tokens[0] == "shim":
                print("handling shimming command")
                self.currents = [
                    float(command_tokens[1]) for _ in range(1, self.channel_number)
                ]
                self._set_selector_mode("w")
            elif command_tokens[0] == "egg":
                print(f"Step aside Mr. Beat! \a")
        except IndexError:
            print(
                f"Incorrect number of arguments for command {command_tokens[0]}. Look up correct usage in manual."
            )
        super().handle_command(command_string)

    def close(self):
        if JUPITER_PLUGGED_IN:
            mrshim.CloseHardwareLink()
        self.shimming_file.close()
        super().close()


# check correct arguments (none)
if len(sys.argv) != 1:
    print(f"Usage: {sys.argv[0]}")
    sys.exit(1)


# create the selector
# every client creates its own default selector, which isnt used outside of the class, shouldn't we do this in the generic client class?

name = "sinope"

# create and register the command prompt.
sinope = SinopeClient(name)
# sinope.selector.register(sinope.descriptor_socket, selectors.EVENT_WRITE, data=sinope)

debugging = False
try:
    while True:
        sinope.main_loop()
except KeyboardInterrupt:
    print("Detected keyboard interrupt. Closing program.")
finally:
    sinope.close()
    sinope.selector.close()
    sys.exit(0)
