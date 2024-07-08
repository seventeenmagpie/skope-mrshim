from asyncio import DatagramProtocol
import io
import json
from pdb import runctx
import selectors
import struct
from pathlib import PureWindowsPath
import sys

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
        # path to shim current file, ensure is in the same directory as shimplugin.dll
        self.shimming_filepath = PureWindowsPath("./sinope_mimic/bin/shimsph.txt")  

      
    def _sete_selector_events_mask(self, mode):
        """Set selector to listen for events."""
        if mode == "r":
            events = selectors.EVENT_READ
        elif mode == "w":
            events = selectors.EVENT_WRITE
        elif mode == "rw" or mode == "wr":
            events = selectors.EVENT_READ | selectors.EVENT_WRITE
        else:
            raise ValueError(f"Invalid events mask mode {mode!r}.")
        self.selector.modify(self.sock, events, data = self)
        
    def _read(self):
        try:
            # should be ready to read
            data = self.sock.recv(4096)
        except BlockingIOError:
            pass
        else:
            if data:
                self._recv_buffer += data
            else:
                raise RuntimeError("Peer closed.")
            
    def _write(self):
        if self._send_buffer:
            print(f"Sending {self._send_buffer!r} to {self.addr}")
            try:
                # should be ready to write
                sent = self.sock.send(self._send_buffer)
            except BlockingIOError:
                pass
            else:
                self._send_buffer = self._send_buffer[sent:]
                # close when the buffer is drained.
                if sent and not self._send_buffer:
                    self.close()
                    
    def _json_encode(self, obj, encoding):
        return json.dumps(obj, ensure_ascii=True).encode(encoding)
    
    def _json_decode(self, json_bytes, encoding):
        tiow = io.TextIOWrapper(
            io.BytesIO(json_bytes), encoding=encoding, newline=""
            )
        obj = json.load(tiow)
        tiow.close()
        return obj
    
    def _create_message(
            self, *, content_bytes, content_type, content_encoding
    ):
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
        action = self.rquest.get("action")
        if action == "shimming":
            answer = self.request.get("value")
            print(answer)
            content = {"result": answer}
        else:
            content = {"result": f"Error: invalid action '{action}'."}
        content_encoding = "ascii"
        response = {
            "content_bytes": self._json_encode(content, content_encoding),
            "content_type": "text/json",
            "content_encoding": content_encoding,
            }
        return response
    
    def _create_response_binary_content(self):
        response = {
            "content_bytes": b"First 10 bytes of request: " + self.request[:10],
            "content_type": "binary/custom-server-binary-type",
            "content_encoding": "binary",
            }
        return response
        
    def process_events(self, mask):
        if mask & selectors.EVENT_READ:
            self.read()
        if mask & selectors.EVENT_WRITE:
            self.write()
            
    def read(self):
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
        if self.request:
            if not self.response_created:
                self.create_response()
                
        self._write()
        
    def close(self):
        print(f"Closing connection to {self.addr}")
        try:
            self.selector.unregister(self.sock)
        except Exception as e:
            print(
                f"Error: selector.unregister() exception for "
                f"{self.addr}: {e!r}")
            
        try:
            self.sock.close()
        except OSError as e:
            print(f"Error: socket.close() exception for {self.addr}: {e!r}")
        finally:
            # delete reference to socket object for garbage collection
            self.sock = None
            
    def process_protoheader(self):
        hdrlen = 2
        if len(self._recv_buffer) >= hdrlen:
            self._jsonheader_len = struct.unpack(">H", self._recv_buffer[:hdrlen])

    def process_jsonheader(self):
        hdrlen = self._jsonheader_len
        if len(self._recv_buffer) >= hdrlen:
            self.jsonheader = self._json_decode(
                self._recv_buffer[:hdrlen], "ascii")
            self._recv_buffer = self._recv_buffer[hdrlen:]
            for reqhdr in (
                "byteorder",
                "content-length",
                "content-type",
                "content-encoding",):
                if reqhdr not in self.jsonheader:
                    raise ValueError(f"missing required header '{reqhdr}'.")
                
    def process_request(self):
        content_len = self.jsonheader["content-length"]
        if not len(self._recv_buffer) >= content_len:
            return
        data = self._recv_buffer[:content_len]
        self._recv_buffer = self._recv_buffer[content_len:]
        if self.jsonheader["content-type"] == "text/json":
            encoding = self.jsonheader["content-encoding"]
            self.request = self._json_decode(data, encoding)
            print(f"Recieved requst {self.request!r} from {self.addr}")
        else:
            self.request = data 
            print(
                f"Recieved {self.jsonheader['content-type']} "
                f"request from {self.addr}"
            )
            
        # we're done reading.
        self._sete_selector_events_mask("w")
        
    def create_response(self):
        if self.jsonheader["content-type"] == "text/json":
            response = self._create_response_json_content()
        else:
            # binary or unknown content-type
            response = self._create_response_binary_content()
        
        message = self._create_message(**response)
        self.response_created = True
        self._send_buffer += message
            
            
            
        

    def _write_currents_to_file(self, shim_currents: list[int]):
        with open(self.filepath, 'w', encoding='ascii') as f:
                # overwrite rest of file
            f.seek(0)
    
            # write currents to file
            for current in shim_currents:
                f.write(str(current))
                f.write("\n")

            # flush buffer to actually put currents in file.
            f.flush()