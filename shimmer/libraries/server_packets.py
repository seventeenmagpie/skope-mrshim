import io
import json
import selectors
import struct
import sys

import libraries.registry as registry
from .parser import parse


class ClientDisconnect(Exception):
    """Raised when a client disconnects.

    Called after the socket is closed and deregistered, so the main server process can stop keeping track of it.
    """

    pass


class Message:
    def __init__(self, selector, sock, addr, server):
        self.selector = selector
        self.sock = sock
        self.addr = addr
        self.server = server

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
        try:
            # Should be ready to read
            data = self.sock.recv(4096)
        except BlockingIOError:
            self.server.logger.debug("Blocking ioerror reached")
            # Resource temporarily unavailable (errno EWOULDBLOCK)
            pass
        else:  # then
            if data:
                self._recv_buffer += data
            else:
                raise RuntimeError(self.addr)

    def _clear(self):
        """Reset the buffers and set the selector back to read, ready to recieve more data."""
        self._recv_buffer = b""
        self._send_buffer = b""
        self._jsonheader_len = None
        self.jsonheader = None
        self.request = None
        self.response_created = False

        self._set_selector_events_mask("r")

        if self.is_relayed_message:
            self.is_relayed_message = False

    def _write(self):
        """Write data to the socket."""
        if self._send_buffer:
            try:
                # Should be ready to write
                if self.is_relayed_message:
                    self.server.logger.info(
                        f"Sending {self._send_buffer!r} to {self.to_address}"
                    )
                    sent = self.to_socket.send(self._send_buffer)
                else:
                    self.server.logger.info(
                        f"Sending {self._send_buffer!r} to {self.addr}"
                    )
                    sent = self.sock.send(self._send_buffer)
            except BlockingIOError:
                # Resource temporarily unavailable (errno EWOULDBLOCK)
                pass
            else:
                self._send_buffer = self._send_buffer[sent:]
                # once whole response sent and buffer drained,
                # clear protoheader, header and request, go back to waiting for read events.
                if sent and not self._send_buffer:
                    self._clear()
                    if self.disconnect:
                        raise ClientDisconnect(self.addr)
                        # server closes packet for us, after removing this client from the registry

    def _json_encode(self, obj):
        """Encode json data into bytes (to send down the wire)."""
        return json.dumps(obj, ensure_ascii=False).encode("utf-8")

    def _json_decode(self, json_bytes):
        """Decode bytes (from the wire) into json data."""
        tiow = io.TextIOWrapper(io.BytesIO(json_bytes), encoding="utf-8", newline="")
        obj = json.load(tiow)
        tiow.close()
        return obj

    def _create_message(self, optional_header=None, *, content_bytes, content_type):
        """Assemble the bytes representing the message that we will send down the wire."""
        # assemble jsonheader
        jsonheader = {
            "byteorder": sys.byteorder,
            "content-type": content_type,
            "content-length": len(content_bytes),
        }
        jsonheader.update(optional_header)
        self.server.logger.info(f"jsonheader is {jsonheader}")
        jsonheader_bytes = self._json_encode(jsonheader)

        # get protoheader (length of jsonheader)
        message_hdr = struct.pack(">H", len(jsonheader_bytes))
        message = message_hdr + jsonheader_bytes + content_bytes
        return message

    def _create_response_json_content(self):
        """Generate the json response that we'll send back to the client."""
        if self.jsonheader["content-type"] == "command":
            command = self.request
            command_tokens = parse(command)
            content = {"result": f"Command {command_tokens[0]} recieved by server."}
            response_type = "command"

        elif self.jsonheader["content-type"] == "relay":
            content = {"result": self.request}
            response_type = "relay"
        else:
            content = {
                "result": f"Error: invalid type '{self.jsonheader['content-type']}'."
            }

        response = {
            "content_bytes": self._json_encode(content),
            "content_type": response_type,
        }

        return response

    def process_events(self, mask):
        """Read or write depending on state of socket."""
        if mask & selectors.EVENT_READ:
            self.read()
        if mask & selectors.EVENT_WRITE:
            self.write()

    def read(self):
        """Reads from socket, then processes data as it comes."""
        self.server.logger.debug("read")
        self._read()
        if self._jsonheader_len is None:
            self.process_protoheader()

        if self._jsonheader_len is not None:
            if self.jsonheader is None:
                self.process_jsonheader()

        if self.jsonheader:
            if self.request is None:
                self.process_request()

    def write(self):
        """Creates a response if neceserry then writes it to the socket."""
        self.server.logger.debug("write")

        # if we have halted, we will need to send responses to all clients, even those which haven't sent a request
        if self.request or self.disconnect:
            self.server.logger.debug(f"self.request is {self.request}")
            if not self.response_created:
                self.create_response()

        self._write()

    def close(self):
        """Unregister the socket from the selector and closes the socket."""
        print(f"Closing connection to {self.addr}")
        try:
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
            self.jsonheader = self._json_decode(self._recv_buffer[:hdrlen])
            self._recv_buffer = self._recv_buffer[
                hdrlen:
            ]  # remove from buffer so we don't read it again.
            for reqhdr in (
                "byteorder",
                "content-length",
                "content-type",
            ):  # check we have everything.
                if reqhdr not in self.jsonheader:
                    raise ValueError(f"Missing required header '{reqhdr}'.")

            if self.jsonheader["content-type"] == "relay":
                to = self.jsonheader["to"]
                self.to_socket = self.server._get_socket(to)
                self.to_address = registry.get_address(to)

                self.is_relayed_message = True

    def process_request(self):
        """Process the actual content of the message."""

        content_len = self.jsonheader["content-length"]

        if (
            not len(self._recv_buffer) >= content_len
        ):  # we haven't recieved the whole message
            return  # read will keep being called until we get past here.

        data = self._recv_buffer[:content_len]
        self._recv_buffer = self._recv_buffer[content_len:]  # clear the read buffer.

        # if a decodeable content type, decode it
        if self.jsonheader["content-type"] in ("text/json", "command", "relay"):
            self.request = self._json_decode(data)

        if self.jsonheader["content-type"] == "text/json":
            self.server.logger.info(
                f"Received request {self.request!r} from {self.addr}"
            )
        elif self.jsonheader["content-type"] == "command":

            command = self.request
            print(f"Server got command {command}")

            if not command[0] == "!":  # server commands don't start with !
                self._set_selector_events_mask(
                    "w"
                )  # set here because we never reach bottom of this function.
                self.server.handle_command(self.request)

            command_tokens = parse(command)

            if command_tokens[0] == "disconnect":
                # print disconnecting client message here.
                print(
                    f"Disconnecting client {registry.get_name_from_address(self.addr)}"
                )
                self.disconnect = True  # flag so we send the disconnect response.

        elif self.jsonheader["content-type"] == "relay":
            # we don't need to do anything to the message content, just pass it on
            self.server.logger.info(
                f"Relaying message from {self.jsonheader['from']} to {self.jsonheader['to']}."
            )
        else:
            # Binary or unknown content-type
            self.request = data
            self.server.logger.info(
                f"Received {self.jsonheader['content-type']} "
                f"request from {self.addr}"
            )
        # Set selector to listen for write events, we're done reading.
        self._set_selector_events_mask("w")

    def create_response(self):
        """Decide which type of response we send back to the client and add it to the send buffer."""
        optional_header_parts = {}
        # when a client asks to disconnect, we need to acknowledge and then tell it to.
        if self.disconnect:
            response_type = "relay"
            content = {"result": f"!server_disconnect"}

            response = {
                "content_bytes": self._json_encode(content),
                "content_type": response_type,
            }
        elif self.jsonheader["content-type"] in ("text/json", "command", "relay"):
            response = self._create_response_json_content()

            if self.jsonheader["content-type"] in ("command", "relay"):
                optional_header_parts = {
                    "to": self.jsonheader["to"],
                    "from": self.jsonheader["from"],
                }
        else:
            response = self._create_response_binary_content()

        self.server.logger.debug(f"Created response is {response}")
        message = self._create_message(optional_header_parts, **response)
        self.response_created = True
        self._send_buffer += message
