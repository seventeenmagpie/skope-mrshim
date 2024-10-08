import selectors
import sys

import libraries.parser as parser
from libraries.generic_client import Client
from libraries.client_packets import Message
from libraries.printers import selector_printer


class MatlabClient(Client):
    """A class to be the matlab client, this contains functions that are called from within matlab."""

    def __init__(self, name):
        name = "matlab"
        super().__init__(name)

    def close(self):
        super().close()
        sys.exit(0)

    def send_currents(self, currents):
        """Called by matlab. Sends a current."""

        if isinstance(currents, int):
            currents = [currents]
        else:
            currents = currents.tolist()

        currents_string = " ".join([str(_) for _ in currents])
        print(f"Sending currents: {currents_string}")

        # mismatch in dictionary forms because
        # we want to use the python keyword 'from' as a key.
        value = {
            "to": "mrshim",
            "from": "matlab",
            "content": f"!shim {currents_string}",
        }

        request = dict(
            type="relay",
            encoding="utf-8",
            content=value,
        )

        self.send_request(request)
        self.main_loop()


    def send_currents(self, command):
        """Called by matlab. Sends an arbitrary command command."""

        command = str(command)

        # mismatch in dictionary forms because
        # we want to use the python keyword 'from' as a key.
        value = {
            "to": "mrshim",
            "from": "matlab",
            "content": f"{command}",
        }

        request = dict(
            type="relay",
            encoding="utf-8",
            content=value,
        )

        self.send_request(request)
        self.main_loop()
