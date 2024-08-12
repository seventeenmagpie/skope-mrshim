import io
import json
import selectors
import struct
import sys
import logging
import pdb

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
        self.request = None
        self._recv_buffer = b""
        self._send_buffer = b""
        self._request_queued = False
        self._jsonheader_len = None
        self.jsonheader = None
        self.response = None

        if self.is_relay:
            self.is_relay = False
            self._set_selector_events_mask("w")
        else:
            # NOTE: *_client.py sets this back to write once a command is recieved.
            self._set_selector_events_mask("r")

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

    def _json_encode(self, obj):
        """Encodes json into bytes."""
        return json.dumps(obj, ensure_ascii=False).encode("utf-8")

    def _json_decode(self, json_bytes):
        """Decodes bytes into a json object."""
        tiow = io.TextIOWrapper(io.BytesIO(json_bytes), encoding="utf-8", newline="")
        obj = json.load(tiow)
        tiow.close()
        return obj

    def _create_message(self, optional_header=None, *, content_bytes, content_type):
        """Create the bytes of message that are sent down the wire."""
        jsonheader = {
            "byteorder": sys.byteorder,
            "content-type": content_type,
            "content-length": len(content_bytes),
        }

        jsonheader.update(optional_header)

        jsonheader_bytes = self._json_encode(jsonheader)
        message_hdr = struct.pack(">H", len(jsonheader_bytes))
        message = message_hdr + jsonheader_bytes + content_bytes
        return message

    def _process_response_json_content(self):
        """Process a json response."""
        content = self.response
        result = content.get("result")
        self.client.logger.info(f"Got result: {result}")
        print(result)

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
            self.client.logger.debug("client is doing something before packet write")
            mask = self.client.process_events(mask)
        if mask & selectors.EVENT_WRITE:
            self.client.logger.debug("packet is writing")
            self.write()

    def read(self):
        """Read and sequence processing of message."""
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
        optional_header_parts = {}

        if content_type == "text/json":
            req = {
                "content_bytes": self._json_encode(content),
                "content_type": content_type,
            }
        elif content_type in ("command", "relay"):
            req = {
                "content_bytes": self._json_encode(content["content"]),
                "content_type": content_type,
            }

            optional_header_parts = {
                "to": content["to"],
                "from": content["from"],
            }

            if content_type == "relay":
                self.is_relay = True
        else:
            server.logger.warn(f"Invalid request type {content_type} recieved.")
            return  # do not attempt to create a message.

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
            self.jsonheader = self._json_decode(self._recv_buffer[:hdrlen])
            self._recv_buffer = self._recv_buffer[hdrlen:]  # remove from buffer.
            for reqhdr in (
                "byteorder",
                "content-length",
                "content-type",
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
            self.response = self._json_decode(data)
            self.client.logger.debug(f"Decoded response from server is {self.response}")
            self._process_response_json_content()

        if self.jsonheader["content-type"] == "relay":
            # a relay command is a command sent from another client.
            if self.response["result"][0] == "!":  # client commands start with a bang!
                self.client.handle_command(self.response["result"][1:])
            else:
                # it's a server command, we know how to send those!
                # implemented manually because not all clients have a command_send method
                action = "command"
                packet = {
                    "to": "server",
                    "from": self.client.name,
                    "content": self.response["result"],
                }
                request = self.client.create_request(
                    action,
                    packet,
                )
                self.client.send_request(request)
                # skip reading a command in.
                self.write()
                return
        elif self.jsonheader["content-type"] in ("text/json", "command"):
            self.client.logger.info(
                f"Received response {self.response!r} from {self.addr}"
            )
        else:
            # Binary or unknown content-type
            self.response = data
            self.client.logger.info(
                f"Received {self.jsonheader['content-type']} "
                f"response from {self.addr}"
            )
            self.client.logger.warn(f"Recieved packet with unknown type.")

        self._clear()
