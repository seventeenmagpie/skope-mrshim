#!/usr/bin/env python3

import selectors
import sys
import traceback

from libraries.exceptions import ClientDisconnect
import libraries.parser as parser
from libraries.generic_client import Client
from libraries.printers import selector_printer


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

        command_tokens = parser.parse(command_string)

        if command_tokens[0] == "relay":
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
                print('Usage: relay <to name> "<content>"')
                return
        else:
            action = "command"
            value = {"to": "server", "from": self.name, "content": command_string}
            request = self.create_request(action, value)
        self.send_request(request)
        # once a command is sent, we shouldn't send another until the response is back
        # NOTE: the response packet will set this back to w.
        # self._set_selector_mode("r")

    def process_events(self, mask):
        """Called by main loop. Main entry to the prompt, which will either allow a command to be entered or wait for a response."""
        if mask & selectors.EVENT_READ:
            # the selector for the prompt is set back to write mode by the packet once its finished processing.
            return mask
        if mask & selectors.EVENT_WRITE:
            self.send_command()
            return mask

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

        # selector_printer(prompt.selector, events)

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
        except IndexError:
            print(
                f"Incorrect number of arguments for command {command_tokens[0]}. Look up correct usage in manual."
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
# prompt.selector.register(prompt.descriptor_socket, selectors.EVENT_WRITE, data=prompt)

debugging = False

try:
    while True:
        prompt.main_loop()
except KeyboardInterrupt:
    print("Exiting program!")
finally:
    prompt.close()
    sel.close()
    sys.exit(0)
