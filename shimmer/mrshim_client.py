#!/usr/bin/env python3

import selectors
import sys
import traceback
import os  # for os.linesep that one time
import time

import libraries.parser as parser
from libraries.generic_client import Client
from libraries.client_packets import Message

JUPITER_PLUGGED_IN = False  # set to True to enable Jupiter functionality.
if JUPITER_PLUGGED_IN:
    import libraries.jupiter_interface as jupiter
else:
    print(
        "NOTE: JUPITER_PLUGGED_IN is not True, Jupiter functionality is disabled and this will write to shims.txt. See line 13 of mrshim_client.py"
    )


class MRShimClient(Client):
    """A class for Sinope. Handles !shim commands and writes shim currents to the file."""

    def __init__(self, name):
        super().__init__(name)
        self.start_connection()
        self.channel_number = 24
        self.shimming = False  # shimming is disabled by default!
        self.currents = [0 for _ in range(1, self.channel_number)]
        self.print_status = True
        self.holding = False

        # because we never send anything first, we need to create the Message object for this client manually.
        events = selectors.EVENT_READ
        message = Message(self.selector, self.socket, self.server_address, None, self)
        self.selector.modify(self.socket, events, data=message)

        # setting up the file to write shim currents to.
        # w mode clears the old shims
        self.shimming_file = open("shims.txt", "w", encoding="utf-8")

        if JUPITER_PLUGGED_IN:
            self.channel_number = jupiter.start_connection()

    def close(self):
        if JUPITER_PLUGGED_IN:
            jupiter.stop()
        self.shimming_file.close()
        super().close()

    def apply_shims(self):
        """Decide what to do with the shim values."""

        if not self.shimming:
            # if we aren't shimming, set all currents to 0
            print(f"Shimming is disabled. Setting currents to 0.")
            self.currents = [0 for _ in range(self.channel_number)]

        if JUPITER_PLUGGED_IN:
            self.send_shims_to_jupiter()
        else:
            # puts the currents in the way sinope likes them.
            # (space delimited floats)
            formatted_currents = (
                " ".join(
                    ["{:5.4f}".format(current / 1000) for current in self.currents]
                )
                + os.linesep  # BUG: this doesn't seem to do anything??
            )
            print(f"'Applying' currents: {formatted_currents}")
            self.shimming_file.write(formatted_currents)
            self.shimming_file.flush()

    def send_shims_to_jupiter(self):
        jupiter.set_shim_currents(self.currents)

        if self.print_status:
            if JUPITER_PLUGGED_IN:
                time.sleep(0.5)
                jupiter.display_status()

    def process_events(self, mask):
        """Called by main loop. Main entry to the prompt, which will either allow a command to be entered or wait for a response."""
        # this client doesn't actually do anything to the server itself.
        # it just waits for shims to be sent to it and then writes them to the file.
        if mask & selectors.EVENT_READ:
            self.apply_shims()
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
        self.logger.debug(f"action is {action}, value is {value}")
        if action == "relay":
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

    def handle_command(self, command_string):
        command_tokens = parser.parse(command_string)
        self.logger.debug(f"Recieved command tokens are {command_tokens}")
        try:
            if command_tokens[0] == "shim":
                if self.holding:
                    return

                try:
                    tile = [
                        int(current_string) for current_string in command_tokens[1:]
                    ]  # the tile.
                except ValueError:
                    print(
                        "Invalid currents. (Did you accidentally set a letter?) Will use last currents."
                    )
                    tile = []

                if tile:  # if we have valid arguments:
                    flooring = [
                        0 for _ in range(self.channel_number)
                    ]  # the empty floor

                    # tiles the tile across the floor
                    # i think this is very clever, which probably means it's wrong
                    for idx, _ in enumerate(flooring):
                        flooring[idx] = tile[idx % len(tile)]

                    self.currents = flooring

            elif command_tokens[0] == "start":
                print("Shimming enabled.")
                self.shimming = True

                if JUPITER_PLUGGED_IN:
                    jupiter.enable_shims()

            elif command_tokens[0] == "stop":
                print("Shimming disabled.")
                self.shimming = False

                if JUPITER_PLUGGED_IN:
                    jupiter.disable_shims()

            elif command_tokens[0] == "hold":
                self.holding = not self.holding
                print(f"Currents are{' not ' if not self.holding else ''} held.")

            elif command_tokens[0] == "status":
                if JUPITER_PLUGGED_IN:
                    self.print_status = not self.print_status
                    # toggle printing status information
                else:
                    print("JUPITER_PLUGGED_IN is not True, can't do anything.")
                    print(
                        "Either this constant is set to False in mrshim_client.py, or the connection failed in the first instance."
                    )

            elif command_tokens[0] == "reset":
                print("Attempting soft reset of Jupiter connection.")
                if JUPITER_PLUGGED_IN:
                    jupiter.soft_reset()
                else:
                    print("JUPITER_PLUGGED_IN is not True, can't do anything.")
                    print(
                        "Either this constant is set to False in mrshim_client.py, or the connection failed in the first instance."
                    )

            elif command_tokens[0] == "egg":
                print(f"Step aside Mr. Beat! \a")
        except IndexError:
            print(
                f"Incorrect number of arguments for command {command_tokens[0]}. Look up correct usage in manual."
            )
        super().handle_command(command_string)


# check correct arguments (none)
if len(sys.argv) != 1:
    print(f"Usage: {sys.argv[0]}")
    sys.exit(1)


name = "mrshim"
mrshim = MRShimClient(name)

try:
    while mrshim.running:
        mrshim.main_loop()
finally:
    # very important that we stop shimming.
    if JUPITER_PLUGGED_IN:
        jupiter.stop()
    mrshim.close()
    sys.exit(0)
