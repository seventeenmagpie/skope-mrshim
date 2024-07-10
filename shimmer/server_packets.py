import io
import json
import selectors
import struct
import sys
import logging

request_search = {
    "morpheus": "Follow the white rabbit. \U0001f430",
    "ring": "In the caves beneath the Misty Mountains. \U0001f48d",
    "\U0001f436": "\U0001f43e Playing ball! \U0001f3d0",
}

server_logger = logging.getLogger(__name__)
logging.basicConfig(filename = "./logs/shimmer_server.log",
                    encoding = "utf-8",
                    level=logging.DEBUG)

class CommandRecieved(Exception):
    """An exception for taking execution back to the main loop when a command is executed that affects server state."""
    pass

class ClientDisconnect(Exception):
    """Raised when a client disconnects, after the socket is closed and deregistered, so the main server process can stop keeping track of it."""
    pass

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
        self.disconnect = False  # if true and no response queued then will close.

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
        server_logger.debug("_read was called")
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

        self._set_selector_events_mask("r")


    def _write(self):
        """Write data to the socket."""
        if self._send_buffer:
            server_logger.info(f"Sending {self._send_buffer!r} to {self.addr}")
            try:
                # Should be ready to write
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
                        print("server is disconnecting client")
                        self.close()
                        raise ClientDisconnect(self.addr)



    def _json_encode(self, obj, encoding):
        """Encode json data into bytes (to send down the wire)."""
        return json.dumps(obj, ensure_ascii=False).encode(encoding)

    def _json_decode(self, json_bytes, encoding):
        """Decode bytes (from the wire) into json data."""
        tiow = io.TextIOWrapper(
            io.BytesIO(json_bytes), encoding=encoding, newline=""
        )
        obj = json.load(tiow)
        tiow.close()
        return obj

    def _create_message(
        self, *, content_bytes, content_type, content_encoding
    ):
        """Assemble the bytes representing the message that we will send down the wire."""
        jsonheader = {
            "byteorder": sys.byteorder,
            "content-type": content_type,
            "content-encoding": content_encoding,
            "content-length": len(content_bytes),
        }
        jsonheader_bytes = self._json_encode(jsonheader, "utf-8")
        message_hdr = struct.pack(">H", len(jsonheader_bytes))
        message = message_hdr + jsonheader_bytes + content_bytes
        return message

    def _create_response_json_content(self):
        """Generate the json response that we'll send back to the client."""
        action = self.request.get("action")
        if action == "search":
            query = self.request.get("value")
            answer = request_search.get(query) or f"No match for '{query}'."
            content = {"result": answer}
        elif action == "command":
            command = self.request.get("value")
            content = {"result": f"Command {command} recieved by server."}

            if self.disconnect:
                server_logger.debug("creating disconnect response")
                content = {"result": f"disconnect"}

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
            "content_bytes": b"First 10 bytes of request: "
            + self.request[:10],
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
        server_logger.debug("read was called")
        self._read()
        server_logger.debug("came out of _read")
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
            if not self.response_created:
                self.create_response()

        self._write()

    def close(self):
        print(f"Closing connection to {self.addr}")
        try:
            server_logger.debug("unregistering socket.")
            self.selector.unregister(self.sock)
        except Exception as e:
            print(
                f"Error: selector.unregister() exception for "
                f"{self.addr}: {e!r}"
            )
        
        try:
            self.sock.close()
        except OSError as e:
            print(f"Error: socket.close() exception for {self.addr}: {e!r}")
        finally:
            # Delete reference to socket object for garbage collection
            self.sock = None

    def process_protoheader(self):
        hdrlen = 2
        if len(self._recv_buffer) >= hdrlen:
            self._jsonheader_len = struct.unpack(
                ">H", self._recv_buffer[:hdrlen]
            )[0]
            self._recv_buffer = self._recv_buffer[hdrlen:]

    def process_jsonheader(self):
        hdrlen = self._jsonheader_len
        if len(self._recv_buffer) >= hdrlen:
            self.jsonheader = self._json_decode(
                self._recv_buffer[:hdrlen], "utf-8"
            )
            self._recv_buffer = self._recv_buffer[hdrlen:]
            for reqhdr in (
                "byteorder",
                "content-length",
                "content-type",
                "content-encoding",
            ):
                if reqhdr not in self.jsonheader:
                    raise ValueError(f"Missing required header '{reqhdr}'.")

    def process_request(self):
        content_len = self.jsonheader["content-length"]
        if not len(self._recv_buffer) >= content_len:
            return
        data = self._recv_buffer[:content_len]
        self._recv_buffer = self._recv_buffer[content_len:]
        if self.jsonheader["content-type"] == "text/json":
            encoding = self.jsonheader["content-encoding"]
            self.request = self._json_decode(data, encoding)
            server_logger.info(f"Received request {self.request!r} from {self.addr}")
        elif self.jsonheader["content-type"] == "command":
            # escape to main loop.
            server_logger.debug("Command packet recieved. Attempting to escape.")
            encoding = self.jsonheader["content-encoding"]
            self.request = self._json_decode(data, encoding)
            self._set_selector_events_mask("w")  # so that a response will be created.

            if not self.request["value"] == "disconnect":
                raise CommandRecieved(self.request.get("value"))
            elif self.request["value"] == "disconnect":
                self.disconnect = True  # sentinel variable to start disconnect process
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
        if self.jsonheader["content-type"] == "text/json":
            response = self._create_response_json_content()
        elif self.jsonheader["content-type"] == "command":
            response = self._create_response_json_content()
        else:
            # Binary or unknown content-type
            response = self._create_response_binary_content()
        message = self._create_message(**response)
        self.response_created = True
        self._send_buffer += message
