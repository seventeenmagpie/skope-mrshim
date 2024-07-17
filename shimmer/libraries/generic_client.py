import selectors
import logging
import socket
import sys
from libraries.registry import registry, get_address
from libraries.client_packets import Message

# TODO: load debugging settings per client from a config file.
debugging = False

class Client:
    """Represents a generic client object, having a socket, current packet and internal id associated with it."""

    def __init__(self, selector, name):
        self.name = name  # the role name for this client generic client object.
        self.selector = selector
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

        # uncomment to enable the logging messages to be printed to the console as well as log file
        if debugging:
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
        # zero is the selector corresponding to this client object
        self.selector.modify(0, events, data=self)

    def start_connection(self):
        """Try and make a connection to the server, add this socket to the selector."""
        print(f"Starting connection to {self.server_address}")
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # SO_REUSEADDR avoids bind() exception: OSError: [Errno 48] Address already in use
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(self.my_address)
        self.socket.setblocking(False)
        self.socket.connect_ex(self.server_address)

        events = selectors.EVENT_READ
        # add this socket to the register if successful.
        self.selector.register(self.socket, events, data=None)
        # print(self.selector.get_key(self.socket))
        self.logger.debug(f"Added {self.socket} to selector.")

    def send_request(self, request):
        """Send a request to the server."""
        events = selectors.EVENT_WRITE
        message = Message(
            self.selector, self.socket, self.server_address, request, self
        )
        self.selector.modify(self.socket, events, data=message)
        self.logger.debug(f"Added request to {self.name}")

    def handle_command(self, command_string):
        """Should be overridden by child class."""
        print(f"Client {self.name} is handling command: {command_string}")

    def close(self):
        print(f"Closing {self.name}. Goodbye \\o")
