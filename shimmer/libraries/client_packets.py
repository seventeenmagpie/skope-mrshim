import io
import json
import selectors
import struct
import sys
import logging

from libraries.exceptions import ClientDisconnect, CommandRecieved
from libraries.parser import parse


class Message:
    def __init__(self, selector, sock, addr, request, client):
        self.selector = selector
        self.sock = sock
        self.addr = addr
        self.request = request
        self.client = client

        self._recv_buffer = b""
        self._send_buffer = b""
        self._request_queued = False
        self._jsonheader_len = None
        self.jsonheader = None
        self.response = None
        self.is_relay = False

    def _clear(self):
        """Clear the buffers and sentinels ready to do the next thing."""
        self.client.logger.debug(f"_clear called. self.is_relay is {self.is_relay}")
        self.request = None
        self._recv_buffer = b""
        self._send_buffer = b""
        self._request_queued = False
        self._jsonheader_len = None
        self.jsonheader = None
        self.response = None

        if self.is_relay:
            self.is_relay = False
            # console_object = self.selector.get_key(self.client.descriptor_socket).data
            # if relay, won't get a response, so we can recieve another command immediately
            # self.selector.modify(self.client.descriptor_socket, selectors.EVENT_WRITE, data=console_object)
            self._set_selector_events_mask("w")
        else:
            # NOTE: *_client.py sets this back to write once a command is recieved.
            self._set_selector_events_mask("r")
        self.client.logger.debug(
            f"After _clear, mask is {self.selector.get_key(self.sock).events}"
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
        """Read from the socket and add to the read buffer.

        Called repeatedly by .read()"""
        self.client.logger.debug("_read")
        try:
            # Should be ready to read
            data = self.sock.recv(4096)
        except BlockingIOError:
            # Resource temporarily unavailable (errno EWOULDBLOCK)
            pass
        else:
            if data:
                self._recv_buffer += data
            else:
                raise RuntimeError("Peer closed.")

    def _write(self):
        """Write to the socket fom the send buffer.

        Called repeatedly by .write()"""
        if self._send_buffer:
            self.client.logger.info(f"Sending {self._send_buffer!r} to {self.addr}")
            try:
                # Should be ready to write
                sent = self.sock.send(self._send_buffer)
            except BlockingIOError:
                # Resource temporarily unavailable (errno EWOULDBLOCK)
                pass
            else:
                self._send_buffer = self._send_buffer[sent:]

    def _json_encode(self, obj, encoding):
        """Encodes json into bytes."""
        return json.dumps(obj, ensure_ascii=False).encode(encoding)

    def _json_decode(self, json_bytes, encoding):
        """Decodes bytes into a json object."""
        tiow = io.TextIOWrapper(io.BytesIO(json_bytes), encoding=encoding, newline="")
        obj = json.load(tiow)
        tiow.close()
        return obj

    def _create_message(
        self, optional_header=None, *, content_bytes, content_type, content_encoding
    ):
        """Create the bytes of message that are sent down the wire."""
        jsonheader = {
            "byteorder": sys.byteorder,
            "content-type": content_type,
            "content-encoding": content_encoding,
            "content-length": len(content_bytes),
        }

        jsonheader.update(optional_header)

        self.client.logger.info(f"jsonheader is: {jsonheader}")
        jsonheader_bytes = self._json_encode(jsonheader, "utf-8")
        message_hdr = struct.pack(">H", len(jsonheader_bytes))
        message = message_hdr + jsonheader_bytes + content_bytes
        return message

    def _process_response_json_content(self):
        """Process a json response."""
        content = self.response
        result = content.get("result")
        self.client.logger.info(f"Got result: {result}")
        print(result)

        if result == "disconnect":  # special case for the disconnect command.
            self.client.logger.debug("raising client disconnect")
            raise ClientDisconnect

    def _process_response_binary_content(self):
        """Process a binary response."""
        content = self.response
        self.client.logger.info(f"Got response: {content!r}")

    def process_events(self, mask):
        """Use selector state to start read or write.

        Usual pattern is packet reads -> client does something with that data, or client gets some data -> packet writes it.
        """

        # if statements are repeated many times because clients may change these variables duing their own processing of events.
        if mask & selectors.EVENT_READ:
            self.client.logger.debug("packet is reading")
            self.read()
        if mask & selectors.EVENT_READ:
            self.client.logger.debug("client is doing something after packet read")
            mask = self.client.process_events(mask)
        if mask & selectors.EVENT_WRITE:
            # self.client.logger.debug("client is doing something before packet write")
            mask = self.client.process_events(mask)
        if mask & selectors.EVENT_WRITE:
            self.client.logger.debug("packet is writing")
            self.write()

    def read(self):
        """Read and start processing of message."""
        self._read()

        if self._jsonheader_len is None:
            self.process_protoheader()

        if self._jsonheader_len is not None:
            if self.jsonheader is None:
                self.process_jsonheader()

        if self.jsonheader:
            if self.response is None:
                self.process_response()
                self._set_selector_events_mask("w")

    def write(self):
        """Write request if queued, generate it if not."""
        if not self._request_queued:
            self.queue_request()

        self._write()

        if self._request_queued:  # if we have been sending a packet
            if not self._send_buffer:  # but we've sent all of it.
                self._clear()

    def close(self):
        """Unregister from the selector and close the connection."""
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

    def queue_request(self):
        """Create a request to put in the buffer, ready to be sent next time the selector mask is 'r'."""
        content = self.request["content"]
        content_type = self.request["type"]
        content_encoding = self.request["encoding"]
        optional_header_parts = {}
        if content_type == "text/json":
            req = {
                "content_bytes": self._json_encode(content, content_encoding),
                "content_type": content_type,
                "content_encoding": content_encoding,
            }
        elif content_type == "command":
            req = {
                "content_bytes": self._json_encode(
                    content["content"], content_encoding
                ),
                "content_type": content_type,
                "content_encoding": content_encoding,
            }

            optional_header_parts = {
                "to": content["to"],
                "from": content["from"],
            }

            if content["content"] == "!reader":
                # if reader is called we need to read from the socket
                # rather than send something
                self._set_selector_events_mask("r")
                return
        elif content_type == "relay":
            req = {
                "content_bytes": self._json_encode(
                    content["content"], content_encoding
                ),
                "content_type": content_type,
                "content_encoding": content_encoding,
            }

            optional_header_parts = {
                "to": content["to"],
                "from": content["from"],
            }

            self.is_relay = True
        else:
            req = {
                "content_bytes": content,
                "content_type": content_type,
                "content_encoding": content_encoding,
            }
        message = self._create_message(optional_header_parts, **req)
        self._send_buffer += message
        self._request_queued = True

    def process_protoheader(self):
        """Process the protoheader that says how long the jsonheader is."""
        hdrlen = 2
        if len(self._recv_buffer) >= hdrlen:
            self._jsonheader_len = struct.unpack(">H", self._recv_buffer[:hdrlen])[0]
            self._recv_buffer = self._recv_buffer[
                hdrlen:
            ]  # remove protoheader from buffer, we don't need it again.

    def process_jsonheader(self):
        """Process the jsonheader that contains metadata about the contents."""
        hdrlen = self._jsonheader_len

        if len(self._recv_buffer) >= hdrlen:  # if we have recieved enough data
            self.jsonheader = self._json_decode(self._recv_buffer[:hdrlen], "utf-8")
            self._recv_buffer = self._recv_buffer[hdrlen:]  # remove from buffer.
            for reqhdr in (
                "byteorder",
                "content-length",
                "content-type",
                "content-encoding",
            ):  # check we have all the neccessary parts.
                if reqhdr not in self.jsonheader:
                    raise ValueError(f"Missing required header '{reqhdr}'.")

    def process_response(self):
        """Process the actual response from the server."""
        content_len = self.jsonheader["content-length"]

        if not len(self._recv_buffer) >= content_len:  # if we have recieved enough data
            return

        data = self._recv_buffer[:content_len]
        self._recv_buffer = self._recv_buffer[content_len:]  # remove from buffer

        if self.jsonheader["content-type"] in ("command", "text/json", "relay"):
            encoding = self.jsonheader["content-encoding"]
            self.response = self._json_decode(data, encoding)
            self.client.logger.debug(f"Decoded response from server is {self.response}")

        if self.jsonheader["content-type"] == "relay":
            # a relay command is a command sent from another client.
            if self.response["result"][0] == "!":  # client commands start with a bang!
                self.client.handle_command(self.response["result"][1:])
            else:
                self._process_response_json_content()
        elif self.jsonheader["content-type"] == "command":
            self._process_response_json_content()
        elif self.jsonheader["content-type"] == "text/json":
            self.client.logger.info(
                f"Received response {self.response!r} from {self.addr}"
            )
            self._process_response_json_content()
        else:
            # Binary or unknown content-type
            self.response = data
            self.client.logger.info(
                f"Received {self.jsonheader['content-type']} "
                f"response from {self.addr}"
            )
            self._process_response_binary_content()

        self._clear()
        # client_object = self.selector.get_key(self.client.descriptor_socket).data
        # self.selector.modify(
        # self.client.descriptor_socket, selectors.EVENT_WRITE, data=client_object
        # )  # can recieve another request from client
