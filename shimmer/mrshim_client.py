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

    def __init__(self, selector, name):
        super().__init__(selector, name)
        self.start_connection()
        self.channel_number = 24
        self.currents = [0 for _ in range(1, self.channel_number)]
        
        # because we never send anything first, we need to create the Message object for this client manually.
        events = selectors.EVENT_READ
        message = Message(self.selector, self.socket, self.server_address, None, self)
        self.selector.modify(self.socket, events, data = message)
        self.logger.debug(f"Added packet to {self.name}")

        # setting up the file to write shim currents to.
        # w mode clears the old shims
        self.shimming_file = open("shims.txt", "w", encoding="utf-8")

        if JUPITER_PLUGGED_IN:
            device_name = ""
            mrshim.LinkupHardware(device_name,
                                  1,  # safe mode (ramps currents),
                                  None)
            mrshim.LoadShimSets("shims.txt")
            mrshim.ApplyShimManually("reset")

    def write_shims_to_file(self):
        print(f"Writing shims {self.currents} to file.")
        # puts the currents in the way sinope likes them.
        # (space delimited floats)
        formatted_currents = " ".join(["{:5.4f}".format(current) for current in self.currents]) + os.linesep
        self.shimming_file.write(formatted_currents)
        self.shimming_file.flush()
        self._set_selector_mode("r")  # wait for update before doing this again.
        
        if JUPITER_PLUGGED_IN:
            self.send_shims_to_jupiter()
        else:
            print("Jupiter not plugged in. Not attempting to drive shims.")

    def send_shims_to_jupiter(self):
        mrshim.ApplyShimManually("next")
        

    def process_events(self, mask):
        """Called by main loop. Main entry to the prompt, which will either allow a command to be entered or wait for a response."""
        # this client doesn't actually do anything to the server itself.
        # it just waits for shims to be sent to it and then writes them to the file.
        if mask & selectors.EVENT_READ:
            pass
        if mask & selectors.EVENT_WRITE:
            self.write_shims_to_file()

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
        #selector_printer(self.selector, events)

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
            if command_tokens[0] == "echo":
                print(f"{' '.join(command_tokens[1:])}")
            elif command_tokens[0] == "shim":
                print("handling shimming command")
                self.currents = [float(command_tokens[1]) for _ in range(1, self.channel_number)]
                self._set_selector_mode("w")
        except IndexError:
            print(
                f"Incorrect number of arguments for command {command_tokens[0]}. Look up correct usage in manual."
            )

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
sel = selectors.DefaultSelector()

name = "sinope" 

# create and register the command prompt.
sinope = SinopeClient(sel, name)
sinope.selector.register(sinope.descriptor_socket, selectors.EVENT_WRITE, data=sinope)

debugging = False
try:
    while True:
        sinope.main_loop()
except KeyboardInterrupt:
    print("Detected keyboard interrupt. Closing program.")
finally:
    sinope.close()
    sel.close()
    sys.exit(0)
