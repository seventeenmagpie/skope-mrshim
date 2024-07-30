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
        sel = selectors.DefaultSelector()
        super().__init__(sel, name)
    
    def send_currents(self, current):
        """Called by matlab. Sends a current."""
        self.logger.info(f"Send current called with {current}")
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

    def main_loop(self):
        # TODO: main_loop should probably be a component of generic client?
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
