import selectors
import logging
import socket
import sys
import traceback
from libraries.registry import registry, get_address
from libraries.client_packets import Message
from libraries.parser import parse
from libraries.printers import selector_printer


class Client:
    """Represents a generic client object, having a socket, current packet and internal id associated with it."""

    def __init__(self, name):
        self.name = name  # the role name for this client generic client object.
        self.selector = selectors.DefaultSelector()
        self.my_address = get_address(name)
        self.server_address = get_address("server")
        self.addr = self.my_address  # for the selector printer

        # set up the logger
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(
            filename=f"./logs/shimmer_{self.name}.log",
            level=logging.DEBUG,
            filemode="w",
        )

        self.debugging = registry[self.name].getboolean("debug")
        # uncomment to enable the logging messages to be printed to the console as well as log file
        if self.debugging:
            print("Debugging mode enabled.")
            handler = logging.StreamHandler(sys.stdout)
            handler.setLevel(logging.DEBUG)
            self.logger.addHandler(handler)

    def _set_selector_mode(self, mode):
        """Set whether this client's selector entry should select for read/write or both."""
        if mode == "r":
            events = selectors.EVENT_READ
        elif mode == "w":
            events = selectors.EVENT_WRITE
        elif mode == "rw":
            events = selectors.EVENT_READ | selectors.EVENT_WRITE
        else:
            raise ValueError(f"Invalid events mask mode {mode!r}.")

    def start_connection(self):
        """Try and make a connection to the server, add this socket to the selector."""
        print(f"Starting connection to {self.server_address}")
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # SO_REUSEADDR avoids bind() exception: OSError: [Errno 48] Address already in use
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(self.my_address)
        self.socket.setblocking(False)
        self.socket.connect_ex(self.server_address)

        events = selectors.EVENT_WRITE
        # add this socket to the register if successful
        # with an empty request
        empty_request = dict(
            type="command",
            content={
                "to": "server",
                "from": self.name,
                "content": 'echo "confirming connection".',
            },
        )
        empty_message = Message(
            self.selector, self.socket, self.server_address, empty_request, self
        )
        self.selector.register(self.socket, events, data=empty_message)
        # print(self.selector.get_key(self.socket))
        self.logger.debug(f"Added {self.socket} to selector.")

    def send_request(self, request):
        """Send a request to the server."""
        events = selectors.EVENT_WRITE
        message = self.selector.get_key(self.socket).data
        message.request = request
        self.selector.modify(self.socket, events, data=message)
        self.logger.debug(f"Added request to {self.name}")
        self.logger.debug(f"That request is {message.request}")

    def handle_command(self, command_string):
        """Should be overridden by child class.

        Leading exclamation mark is removed in packet code, before calling."""
        self.logger.info(f"Client {self.name} is handling command: {command_string}")
        command_tokens = parse(command_string)
        try:
            if command_tokens[0] == "echo":
                print(f"{' '.join(command_tokens[1:])}")
            elif command_tokens[0] == "server_disconnect":
                self.logger.info("Recieved disconnect command from server.")
                self.close()
        except IndexError:
            print(
                f"Incorrect number of arguments for command {command_tokens[0]}. Look up correct usage in manual."
            )

    def process_events(self, mask):
        """Called by the clients packet object either before or after its own read/write methods.

        The packet will call this with a read mask *after* its own read has been executed, because usually the client will want to do something with the data that has been read.

        The packet will call this with a write mask *before* its own write has been executed because usually the client will want to get something in for the packet to write.

        Thus the client reads before the packet writes and writes after the packet reads.

        I have kept the flags backwards here rather than keeping their conventional meanings and changing the flags inside the client's process_events because I felt like this was easier to understand

        But now I've explained it to myself I feel slightly different.
        """
        # TODO: think more about this.

        if mask & selectors.EVENT_READ:
            self.logger.debug("Client is doing something after the packet read.")
        if mask & selectors.EVENT_WRITE:
            self.logger.debug("Client is doing something before the packet wrote.")

        return mask

    def main_loop(self):
        events = self.selector.select(
            timeout=0
        )  # get waiting io events. timeout = 0 to wait without blocking.

        if self.debugging:
            selector_printer(self.selector, events)

        for key, mask in events:
            message = key.data
            try:
                message.process_events(mask)
            except Exception:
                print(
                    f"Main: Error: Exception for {message.addr}:\n"
                    f"{traceback.format_exc()}"
                )
                message.close()

    def close(self):
        try:  # because of outer exception handling, this can get called twice and cause weirdness.
            message = self.selector.get_key(self.socket).data
            message.close()
        except:
            pass
        finally:
            self.selector.close()
            print(f"Closed {self.name} client. Goodbye \\o")
            sys.exit(0)
