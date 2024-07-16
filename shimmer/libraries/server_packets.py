import io
import json
import selectors
import struct
import sys
import logging
import copy

import libraries.registry as registry
from .parser import parse
from .exceptions import CommandRecieved, ClientDisconnect

server_logger = logging.getLogger(__name__)
logging.basicConfig(
    filename="./logs/shimmer_server.log", level=logging.DEBUG, filemode="w"
)

# uncomment to enable the debug messages to be printed to the console as well as the file
# handler = logging.StreamHandler(sys.stdout)
# handler.setLevel(logging.DEBUG)
# server_logger.addHandler(handler)


class Message:
    def __init__(self, selector, sock, addr):
        self.selector = selector
        self.sock = sock
        self.addr = addr
        self._recv_buffer = b""
        self._send_buffer = b""
        self._jsonheader_len = None
        self.jsonheader = None
        self.request = None
        self.response_created = False
        self.disconnect = (
            False  # sentinel for whether to disconnect this socket or not.
        )

        self.is_relayed_message = (
            False  # is this the message created by the server to pass on?
        )

    def _set_selector_events_mask(self, mode):
        """Set selector to listen for events: mode is 'r', 'w', or 'rw'."""
        if mode == "r":
            events = selectors.EVENT_READ
        elif mode == "w":
            events = selectors.EVENT_WRITE
        elif mode == "rw":
            events = selectors.EVENT_READ | selectors.EVENT_WRITE
        else:
            raise ValueError(f"Invalid events mask mode {mode!r}.")
        self.selector.modify(self.sock, events, data=self)

    def _read(self):
        """Read from the open socket. Writes data into a buffer."""
        server_logger.debug(f"trying my best to read from {self.sock}")
        try:
            # Should be ready to read
            server_logger.debug("trying to use .recv")
            data = self.sock.recv(4096)
        except BlockingIOError:
            server_logger.debug("blocking ioerror reached")
            # Resource temporarily unavailable (errno EWOULDBLOCK)
            pass
        else:  # then
            if data:
                self._recv_buffer += data
            else:
                raise RuntimeError("Peer closed.")

    def _clear(self):
        """Reset the buffers and set the selector back to read, ready to recieve more data."""
        self._recv_buffer = b""
        self._send_buffer = b""
        self._jsonheader_len = None
        self.jsonheader = None
        self.request = None
        self.response_created = False

        # after we send something, we should be ready to listen again.
        # this appears twice because during relayi
        # the new destination socket is set to write, so we need to put that back
        # onto read
        # then retrieve the original socket
        # and make sure that is on read too.
        self._set_selector_events_mask("r")

        if self.is_relayed_message:
            self.is_relayed_message = False
            self._set_selector_events_mask("r")

    def _write(self):
        """Write data to the socket."""
        if self._send_buffer:
            try:
                # Should be ready to write
                if self.is_relayed_message:
                    server_logger.info(
                        f"Sending {self._send_buffer!r} to {self.to_address}"
                    )
                    sent = self.to_socket.send(self._send_buffer)
                else:
                    server_logger.info(f"Sending {self._send_buffer!r} to {self.addr}")
                    sent = self.sock.send(self._send_buffer)
            except BlockingIOError:
                # Resource temporarily unavailable (errno EWOULDBLOCK)
                pass
            else:
                self._send_buffer = self._send_buffer[sent:]
                # once whole response sent and buffer drained,
                # clear protoheader, header and request, go back to waiting for read events.
                if sent and not self._send_buffer:
                    # print("sent and send buffer empty")
                    self._clear()
                    if self.disconnect:
                        self.close()
                        raise ClientDisconnect(self.addr)

    def _json_encode(self, obj, encoding):
        """Encode json data into bytes (to send down the wire)."""
        return json.dumps(obj, ensure_ascii=False).encode(encoding)

    def _json_decode(self, json_bytes, encoding):
        """Decode bytes (from the wire) into json data."""
        tiow = io.TextIOWrapper(io.BytesIO(json_bytes), encoding=encoding, newline="")
        obj = json.load(tiow)
        tiow.close()
        return obj

    def _create_message(
        self, optional_header=None, *, content_bytes, content_type, content_encoding
    ):
        """Assemble the bytes representing the message that we will send down the wire."""
        # assemble jsonheader
        jsonheader = {
            "byteorder": sys.byteorder,
            "content-type": content_type,
            "content-encoding": content_encoding,
            "content-length": len(content_bytes),
        }
        jsonheader.update(optional_header)
        server_logger.info(f"jsonheader is {jsonheader}")
        jsonheader_bytes = self._json_encode(jsonheader, "utf-8")

        # get protoheader (length of jsonheader)
        message_hdr = struct.pack(">H", len(jsonheader_bytes))
        message = message_hdr + jsonheader_bytes + content_bytes
        return message

    def _create_response_json_content(self):
        """Generate the json response that we'll send back to the client."""
        if self.jsonheader["content-type"] == "command":
            command = self.request.get("value")
            command_tokens = parse(command)
            content = {"result": f"Command {command_tokens[0]} recieved by server."}

            # generate the response message if we are disconnected
            if self.disconnect:
                server_logger.debug("creating disconnect response")
                content = {"result": f"disconnect"}

        elif self.jsonheader["content-type"] == "relay":
            content = {"result": self.request}
        else:
            content = {"result": f"Error: invalid action '{action}'."}

        content_encoding = "utf-8"
        response = {
            "content_bytes": self._json_encode(content, content_encoding),
            "content_type": "text/json",
            "content_encoding": content_encoding,
        }

        return response

    def _create_response_binary_content(self):
        """Generate a binary response that we'll send back to the client."""
        response = {
            "content_bytes": b"First 10 bytes of request: " + self.request[:10],
            "content_type": "binary/custom-server-binary-type",
            "content_encoding": "binary",
        }
        return response

    def process_events(self, mask):
        """Read or write depending on state of socket."""
        server_logger.debug("processing events")
        if mask & selectors.EVENT_READ:
            server_logger.debug("server is reading")
            self.read()
        if mask & selectors.EVENT_WRITE:
            server_logger.debug("server is writing")
            self.write()

    def read(self):
        """Reads from socket, then processes data as it comes."""
        self._read()
        if self._jsonheader_len is None:
            server_logger.debug("processing protoheader")
            self.process_protoheader()

        if self._jsonheader_len is not None:
            if self.jsonheader is None:
                server_logger.debug("processing jsonheader")
                self.process_jsonheader()

        if self.jsonheader:
            if self.request is None:
                server_logger.debug("processing request")
                self.process_request()

    def write(self):
        """Creates a response if neceserry then writes it to the socket."""
        if self.request:
            server_logger.debug(f"self.request is {self.request}")
            if not self.response_created:
                server_logger.debug("creating response")
                self.create_response()

        self._write()

    def close(self):
        """Unregister the socket from the selector and closes the socket."""
        print(f"Closing connection to {self.addr}")
        try:
            server_logger.debug("unregistering socket.")
            self.selector.unregister(self.sock)
        except Exception as e:
            print(f"Error: selector.unregister() exception for " f"{self.addr}: {e!r}")

        try:
            self.sock.close()
        except OSError as e:
            print(f"Error: socket.close() exception for {self.addr}: {e!r}")
        finally:
            # Delete reference to socket object for garbage collection
            self.sock = None

    def process_protoheader(self):
        """Process the protoheader to find out the length of the json header."""
        hdrlen = 2
        if len(self._recv_buffer) >= hdrlen:  # enough data has been sent in.
            self._jsonheader_len = struct.unpack(">H", self._recv_buffer[:hdrlen])[0]
            self._recv_buffer = self._recv_buffer[
                hdrlen:
            ]  # remove the protoheader from the buffer. we don't want to read it again.

    def process_jsonheader(self):
        """Process the jsonheader to find out information about the content."""
        hdrlen = self._jsonheader_len
        if len(self._recv_buffer) >= hdrlen:  # enough data has been sent in.
            self.jsonheader = self._json_decode(self._recv_buffer[:hdrlen], "utf-8")
            self._recv_buffer = self._recv_buffer[
                hdrlen:
            ]  # remove from buffer so we don't read it again.
            for reqhdr in (
                "byteorder",
                "content-length",
                "content-type",
                "content-encoding",
            ):  # check we have everything.
                if reqhdr not in self.jsonheader:
                    raise ValueError(f"Missing required header '{reqhdr}'.")

            if self.jsonheader["content-type"] == "relay":
                to = self.jsonheader["to"]
                self.to_socket = registry.get_socket(to)
                self.to_address = registry.get_address(to)

                self.is_relayed_message = True

    def process_request(self):
        """Process the actual content of the message."""
        server_logger.debug("processing request")

        content_len = self.jsonheader["content-length"]

        if (
            not len(self._recv_buffer) >= content_len
        ):  # we haven't recieved the whole message
            return  # read will keep being called until we get past here.

        data = self._recv_buffer[:content_len]
        self._recv_buffer = self._recv_buffer[content_len:]  # clear the read buffer.

        # if a decodeable content type, decode it
        if self.jsonheader["content-type"] in ("text/json", "command", "relay"):
            encoding = self.jsonheader["content-encoding"]
            self.request = self._json_decode(data, encoding)

        if self.jsonheader["content-type"] == "text/json":
            server_logger.info(f"Received request {self.request!r} from {self.addr}")
        elif self.jsonheader["content-type"] == "command":
            server_logger.debug("Command packet recieved.")

            command = self.request["value"]

            if not command[0] == "!":  # server commands don't start with !
                # print("server command recieved")
                self._set_selector_events_mask(
                    "w"
                )  # set here because we never reach bottom of this function.
                # HACK: there has got to be a more pythonic way than raising an exception.
                raise CommandRecieved(
                    self.request.get("value")
                )  # escapes us to main loop and takes the rest of the command with it.

            command_tokens = parse(command)

            if command_tokens[0] == "!disconnect":
                self.disconnect = True

        elif self.jsonheader["content-type"] == "relay":
            # we don't need to do anything to the message content, just pass it on
            server_logger.info(
                f"Relaying message from {self.jsonheader['from']} to {self.jsonheader['to']}."
            )
        else:
            # Binary or unknown content-type
            self.request = data
            server_logger.info(
                f"Received {self.jsonheader['content-type']} "
                f"request from {self.addr}"
            )
        # Set selector to listen for write events, we're done reading.
        self._set_selector_events_mask("w")

    def create_response(self):
        """Decide which type of response we send back to the client and add it to the send buffer."""
        optional_header_parts = {}
        if self.jsonheader["content-type"] == "text/json":
            response = self._create_response_json_content()
        elif self.jsonheader["content-type"] == "command":
            response = self._create_response_json_content()
        elif self.jsonheader["content-type"] == "relay":
            optional_header_parts = {
                "to": self.jsonheader["to"],
                "from": self.jsonheader["from"],
            }
            response = self._create_response_json_content()
        else:
            response = self._create_response_binary_content()
        server_logger.debug(f"created response is {response}")
        message = self._create_message(optional_header_parts, **response)
        self.response_created = True
        self._send_buffer += message
