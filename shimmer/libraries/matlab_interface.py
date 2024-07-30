import selectors

from libraries.exceptions import ClientDisconnect
import libraries.parser as parser
from libraries.generic_client import Client
from libraries.client_packets import Message
from libraries.printers import selector_printer

class MatlabClient(Client):
    """A class to be the matlab client, this contains functions that are called from within matlab."""

    def __init__(self, name):
        name = 'matlab'
        super().__init__(name)
    
    def send_currents(self, current):
        """Called by matlab. Sends a current."""
        print(f"Sending currents: {current}")
        # mismatch in dictionary forms because
        # we want to use the python keyword 'from' as a key.
        value = {
                "to":"sinope",
                "from":"matlab",
                "content":f"!shim {current}",
                }

        request = dict(
                type="relay",
                encoding="utf-8",
                content=value,
        )

        self.send_request(request)
        self.main_loop() 
