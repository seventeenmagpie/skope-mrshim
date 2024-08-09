#!/usr/bin/env python3

import selectors
import sys
import traceback
import os  # for os.linesep one time

from libraries.exceptions import ClientDisconnect
import libraries.parser as parser
from libraries.generic_client import Client
from libraries.client_packets import Message

JUPITER_PLUGGED_IN = True  # set to True to enable Jupiter functionality.
if JUPITER_PLUGGED_IN:
    # import the libshim library and set the argument types where needs be.
    import ctypes
    mrshim = ctypes.cdll.LoadLibrary(r".\libraries\libshim.dll")  # path to libshim.dll
    mrshim.ShimStart.argtypes = ctypes.c_char_p, ctypes.c_int
    c_int32_p = ctypes.POINTER(ctypes.c_int32)
    mrshim.ShimSetCurr.argtypes = c_int32_p, ctypes.c_int, ctypes.c_bool
else:
    print("NOTE: JUPITER_PLUGGED_IN is not True, Jupiter functionality is disabled and this will write to shims.txt. See line 13 of mrshim_client.py")

class SinopeClient(Client):
    """A class for Sinope. Handles !shim commands and writes shim currents to the file."""

    def __init__(self, name):
        super().__init__(name)
        self.start_connection()
        self.channel_number = 24
        self.shimming = False  # shimming is disabled by default!
        self.currents = [0 for _ in range(1, self.channel_number)]
        self.print_status = False

        # because we never send anything first, we need to create the Message object for this client manually.
        events = selectors.EVENT_READ
        message = Message(self.selector, self.socket, self.server_address, None, self)
        self.selector.modify(self.socket, events, data=message)
        self.logger.debug(f"Added packet to {self.name}")

        # setting up the file to write shim currents to.
        # w mode clears the old shims
        self.shimming_file = open("shims.txt", "w", encoding="utf-8")

        if JUPITER_PLUGGED_IN:
            self.jupiter_ifname = r"\Device\NPF_{58A4C8CA-56D2-4F34-8D5E-74FD1F2E60CA}"
            self.jupiter_ifname_unicode = self.jupiter_ifname.encode('utf-8')
            self._jupiter_start_connection() 

    def _jupiter_start_connection(self):
        rc = mrshim.ShimStart(self.jupiter_ifname_unicode, 1)
        if rc == 0:
            print("Connected to Jupiter device!")
        else:
            self.logger.warn(f"Issue connecting to Jupiter devices. Error code: {rc}")
            print(f"Issue connecting to Jupiter devices. Error code: {rc}")
            print(f"Consult Internal Software Tools Documentation.pdf for interpretation.")
            print("Shimming will not work. Will write to shims.txt instead.")
            JUPITER_PLUGGED_IN = False  # HACK: my constant isn't constant...

    def apply_shims(self):
        """Decide what to do with the shim values."""

        if not self.shimming:
            # if we aren't shimming, set all currents to 0
            print(f"Shimming is disabled. Setting currents to 0.")
            self.currents = [0 for _ in range(self.channel_number)]

        self.logger.debug(f"{self.name} is applying currents: {self.currents}")
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
        max = 2000
        for idx, current in enumerate(self.currents):
            if abs(current) > max:
                print(f"Current exceeds safe maximum +/-{max}mA. Setting to 0mA.")
                self.currents[idx] = 0
        ctype_currents = (ctypes.c_int32 * 24)(*self.currents)
        current_pointer = ctypes.cast(ctype_currents, ctypes.POINTER(ctypes.c_int32))
        mrshim.ShimSetCurr(current_pointer, 24, False)
        print(f"Shims applied: {self.currents}")

        if self.print_status:
            first_diverged_channel = mrshim.ShimChannelDiverged()
            if first_diverged_channel:
                print(f"Channel {first_diverged_channel} did not converge, and later channels may not have either.")
            else:
                # TODO: implement current status and so on.
                # how to return lists: https://stackoverflow.com/questions/26531611/python-ctypes-convert-returned-c-array-to-python-list-without-numpy?rq=3
                print("Shim status nominal.")

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

    def handle_command(self, command_string):
        command_tokens = parser.parse(command_string)
        self.logger.debug(f"Recieved command tokens are {command_tokens}")
        try:
            if command_tokens[0] == "shim":
                tile = [
                    int(current_string) for current_string in command_tokens[1:]
                ]  # the tile.
                flooring = [0 for _ in range(self.channel_number)]  # the empty floor

                if not tile:  # if not passed with any arguments, all zeros.
                    tile = [0]

                # tiles the tile across the floor
                # i think this is very clever, which probably means it's wrong
                for idx, _ in enumerate(flooring):
                    flooring[idx] = tile[idx % len(tile)]

                self.currents = flooring
                self._set_selector_mode("w")
            elif command_tokens[0] == "start":
                print("Shimming enabled.")
                self.shimming = True

                if JUPITER_PLUGGED_IN:
                    mrshim.ShimEnable()
                    mrshim.ShimResetCurr()
                    
            elif command_tokens[0] == "stop":
                print("Shimming disabled.")
                self.shimming = False

                if JUPITER_PLUGGED_IN:
                    mrshim.ShimResetCurr()
                    mrshim.ShimDisable()
                   
            elif command_tokens[0] == "status":
                if JUPITER_PLUGGED_IN:
                    self.print_status = not self.print_satus
                    # toggle printing status information
                else:
                    print("JUPITER_PLUGGED_IN is not True, can't do anything.")
                    print("Either this constant is set to False in mrshim_client.py, or the connection failed in the first instance.")

            elif command_tokens[0] == "reset":
                print("Attempting soft reset of Jupiter connection.")
                if JUPITER_PLUGGED_IN:
                    mrshim.shim_soft_close()
                    self._jupiter_start_connection()
                else:
                    print("JUPITER_PLUGGED_IN is not True, can't do anything.")
                    print("Either this constant is set to False in mrshim_client.py, or the connection failed in the first instance.")

            elif command_tokens[0] == "egg":
                print(f"Step aside Mr. Beat! \a")
        except IndexError:
            print(
                f"Incorrect number of arguments for command {command_tokens[0]}. Look up correct usage in manual."
            )
        super().handle_command(command_string)

    def close(self):
        if JUPITER_PLUGGED_IN:
            mrshim.ShimStop()
        self.shimming_file.close()
        super().close()


# check correct arguments (none)
if len(sys.argv) != 1:
    print(f"Usage: {sys.argv[0]}")
    sys.exit(1)


name = "mrshim"
sinope = SinopeClient(name)

try:
    while True:
        sinope.main_loop()
except KeyboardInterrupt:
    print("Detected keyboard interrupt. Closing program.")
    sinope.close()
finally:
    # very important that we stop shimming.
    if JUPITER_PLUGGED_IN:
        mrshim.ShimStop()
