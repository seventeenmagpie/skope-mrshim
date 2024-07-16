#!/usr/bin/env python3

import selectors
import sys
import traceback

from libraries.exceptions import ClientDisconnect
from libraries.parser import parse
from libraries.generic_client import Client


class CommandPrompt(Client):
    """A class to be the command prompt so that we can put it on the selector and select into at the correct times."""

    def __init__(self, selector, name):
        super().__init__(selector, name)
        self.start_connection()

    
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
                self.logger.debug(f"attempting to create request.")
                self.logger.debug(f"command tokens are {command_tokens}")
                request = self.create_request(
                    action,
                    {
                        "to": command_tokens[1],
                        "from": self.name,
                        "content": command_tokens[2],
                    },
                )
                self.logger.debug(f"request is {request}")
            except IndexError:
                print('Usage: message <to name> "<message content>"')
                return
        else:
            action = "command"
            value = command_string
            request = self.create_request(action, value)

        self.send_request(request)
        # once a command is sent, we shouldn't send another until the response is back
        # NOTE: the response packet will set this back to w.
        self._set_selector_mode("r")

    def process_events(self, mask):
        """Called by main loop. Main entry to the prompt, which will either allow a command to be entered or wait for a response."""
        if mask & selectors.EVENT_READ:
            # the selector for the prompt is set back to write mode by the packet once its finished processing.
            pass
        if mask & selectors.EVENT_WRITE:
            self.send_command()

    def create_request(self, action, value):
        """Make a requst from the users entry.

        Here, 'type' tells the packet (and then the server) what to do with the content, how to turn it into a header &c..
        """
        self.logger.debug("inside create request")
        self.logger.debug(f"action is {action}, value is {value}")
        if action == "relay":
            self.logger.debug("detected in relay section")
            # here, value is a dictionary of to: and content:
            return dict(
                type="relay",
                encoding="utf-8",
                content=dict(action=action, value=value),
            )
        elif action == "command":
            return dict(
                type="command",
                encoding="utf-8",
                content=dict(action=action, value=value),
            )
        else:
            return dict(
                type="binary/custom-client-binary-type",
                encoding="binary",
                content=bytes(action + value, encoding="utf-8"),
            )



# check correct arguments (none)
if len(sys.argv) != 1:
    print(f"Usage: {sys.argv[0]}")
    sys.exit(1)


# create the selector
sel = selectors.DefaultSelector()

console_number = int(input("Enter console number (1 or 2): "))
name = "console" + str(console_number)

# create and register the command prompt.
prompt = CommandPrompt(sel, name)
prompt.selector.register(0, selectors.EVENT_WRITE, data=prompt)

debugging = False

try:
    while True:
        #print("everything in the selector is")
        #for fileobj, key in prompt.selector.get_map().items():
            #print(f"{fileobj}: {key}")
        events = prompt.selector.select(
            timeout=0
        )  # get waiting io events. timeout = 0 to wait without blocking.
        # sort by mask so list now in order read -> write -> read/write
        # NOTE: was included to try and help auto-inbox
        # but command prompt input() is always blocking.
        # auto-inbox no work.
        #print(events)
        # TODO: to fix input blocking would need to create a true console gui with something like curses. not now.
        events_sorted_read_priority = sorted(
            events, key=lambda key_mask_pair: key_mask_pair[1]
        )

        if False:
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
