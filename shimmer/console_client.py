#!/usr/bin/env python3

import selectors
import sys
import traceback

import libraries.parser as parser
from libraries.generic_client import Client
from libraries.printers import selector_printer


class CommandPrompt(Client):
    """A class to be the command prompt so that we can put it on the selector and select into at the correct times."""

    def __init__(self, name):
        super().__init__(name)
        self.start_connection()

    def close(self):
        super().close()

    def send_command(self):
        """Input a command string from the user, turn it into a request and send it to the server."""
        command_string = input("[shimmer]: ")

        if not command_string:
            # if nothing is entered, then try and read
            command_string = "!reader"

        command_tokens = parser.parse(command_string)

        if command_tokens[0][0] == "!":
            self.handle_command(command_string[1:])
            return 1
        else:
            if command_tokens[0] == "relay":
                try:
                    action = "relay"
                    packet = {
                        "to": command_tokens[1],
                        "from": self.name,
                        "content": command_tokens[2],
                    }
                except IndexError:
                    print('Usage: relay <to name> "<content>"')
                    return 1
            else:
                action = "command"
                packet = {
                    "to": "server",
                    "from": self.name,
                    "content": command_tokens[0],
                }
                # NOTE: all server commands (currently) have zero arguments. is this appropriate?

            self.logger.debug(f"Attempting to create request.")
            self.logger.debug(f"Command tokens are {command_tokens}")
            request = self.create_request(
                action,
                packet,
            )
            self.send_request(request)
        return 2

    def process_events(self, mask):
        """Called by main loop. Main entry to the prompt, which will either allow a command to be entered or wait for a response."""
        if mask & selectors.EVENT_READ:
            # the selector for the prompt is set back to write mode by the packet once its finished processing.
            return mask
        if mask & selectors.EVENT_WRITE:
            mask = (
                self.send_command()
            )  # .send_command returns a mask because client commands need us to *not* write afterwards.
            return mask

    def create_request(self, action, value):
        """Make a requst from the users entry.

        Here, 'type' tells the packet (and then the server) what to do with the content, how to turn it into a header &c..
        """
        self.logger.debug(f"action is {action}, value is {value}")
        if action == "relay":
            return dict(
                type="relay",
                content=value,
            )
        elif action == "command":
            return dict(
                type="command",
                content=value,
            )
        else:
            pass  # action is always one of either relay or command. is set by code.

    def handle_command(self, command_string):
        if not command_string:
            return

        command_tokens = parser.parse(command_string)
        self.logger.debug(f"Recieved command tokens are {command_tokens}")
        if command_tokens[0] == "egg":
            print(f"Dogs can't operate MRI scanners... \a")
            print(f"But cats can!")
        elif command_tokens[0] == "reader":
            # temporarily set the mask to read, and call main_loop to read any waiting input.
            # then go back to whatever we were doing before.
            message = self.selector.get_key(self.socket).data
            old_state = self.selector.get_key(self.socket).events
            self.selector.modify(self.socket, selectors.EVENT_READ, data=message)
            self.main_loop()
            self.selector.modify(self.socket, selectors.EVENT_WRITE, data=message)

        super().handle_command(command_string)


# check correct arguments (none)
if len(sys.argv) != 1:
    print(f"Usage: {sys.argv[0]}")
    sys.exit(1)


console_number = int(input("Enter console number (1 or 2): "))
name = "console" + str(console_number)

# create and register the command prompt.
prompt = CommandPrompt(name)

try:
    while prompt.running:
        prompt.main_loop()
except KeyboardInterrupt:
    print("Exiting program!")
finally:
    prompt.close()
    sys.exit(0)
