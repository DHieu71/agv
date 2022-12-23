
import sys
import selectors
import struct
import logging
import pickle
logging.basicConfig(format='%(levelname)s - %(asctime)s.%(msecs)03d: %(message)s', datefmt='%H:%M:%S', level=logging.DEBUG)


class Message:
    def __init__(self, selector, sock, addr):
        self.selector = selector
        self.sock = sock
        self.addr = addr
        self.request = None
        self._recvBuffer = b""
        self._sendBuffer = b""
        self._isRequestQueued = False
        self._headerLength = None
        self._responseHeader = None
        self.response = None
        self.__FORMAT = 'utf-8'

    def addRequest(self, request):
        self.request = request
        self.response = None

    def _resetRequest(self):
        self.request = None
        self._recvBuffer = b""
        self._sendBuffer = b""
        self._isRequestQueued = False
        self._headerLength = None
        self._responseHeader = None

    def _setSelectorEventsMask(self, mode):
        """Set selector to listen for events: mode is 'r', 'w', or 'rw'."""
        if mode == "r":
            events = selectors.EVENT_READ
        elif mode == "w":
            events = selectors.EVENT_WRITE
        elif mode == "rw":
            events = selectors.EVENT_READ | selectors.EVENT_WRITE
        else:
            raise ValueError(f"Invalid events mask mode {mode}.")
        self.selector.modify(self.sock, events, data=self)

    def _read(self):
        try:
            # Should be ready to read
            data = self.sock.recv(4096)
        except BlockingIOError:
            # Resource temporarily unavailable (errno EWOULDBLOCK)
            pass
        else:
            if data:
                self._recvBuffer += data
            else:
                raise RuntimeError("Peer closed.")

    def _write(self):
        if self._sendBuffer:
            logging.info(f"[SENDING] Sending request {self.request} to {self.addr}")
            try:
                # Should be ready to write
                sent = self.sock.send(self._sendBuffer)
            except BlockingIOError:
                # Resource temporarily unavailable (errno EWOULDBLOCK)
                pass
            else:
                self._sendBuffer = self._sendBuffer[sent:]

    def _dictEncode(self, obj):
        return pickle.dumps(obj)

    def _dictDecode(self, json_bytes, encoding):
        return pickle.loads(json_bytes, encoding=encoding)

    def _createMessage(self, content_bytes):
        requestHeader = {
            "byteorder": sys.byteorder,
            "content_length": len(content_bytes),
        }
        requestHeader_bytes = self._dictEncode(requestHeader)
        message_hdr = struct.pack(">H", len(requestHeader_bytes))
        message = message_hdr + requestHeader_bytes + content_bytes
        return message

    def processEvents(self, mask):
        if mask & selectors.EVENT_READ:
            self.read()
        if mask & selectors.EVENT_WRITE:
            self.write()
        return self.response

    def read(self):
        self._read()

        if self._headerLength is None:
            self._processHeaderLength()

        if self._headerLength is not None:
            if self._responseHeader is None:
                self._processRequestHeader()

        if self._responseHeader:
            if self.response is None:
                self.processResponse()

        self._resetRequest()

    def write(self):
        """
            Cient initiates a connection to the server and sends a request first, the state variable self._reqeust_queued is checked
        """
        if not self._isRequestQueued:
            self.queueRequest()

        self._write()

        """
            The reason for this is to tell selector.select() to stop monitoring the socket for write events. If the request has been queued and the send buffer is empty, then you're done writing and you're only interested in read events. There's no reason to be notified that the socket is writable.
        """

        if self._isRequestQueued:
            if not self._sendBuffer:
                # Set selector to listen for read events, we're done writing.
                self._setSelectorEventsMask("r")

    def close(self):
        logging.info(f"[CLOSING] Closing connection to {self.addr}")
        try:
            self.selector.unregister(self.sock)
        except Exception as e:
            logging.info(
                f"[ERROR] selector.unregister() exception for "
                f"{self.addr}: {e}"
            )

        try:
            self.sock.close()
        except OSError as e:
            logging.info(f"[ERROR] socket.close() exception for {self.addr}: {e}")
        finally:
            # Delete reference to socket object for garbage collection
            self.sock = None

    def queueRequest(self):
        requestBytes = self._dictEncode(self.request)
        message = self._createMessage(requestBytes)
        self._sendBuffer += message
        self._isRequestQueued = True

    def _processHeaderLength(self):
        headerLength = 2
        if len(self._recvBuffer) >= headerLength:
            self._headerLength = struct.unpack(">H", self._recvBuffer[:headerLength])[0]
            self._recvBuffer = self._recvBuffer[headerLength:]

    def _processRequestHeader(self):
        if len(self._recvBuffer) >= self._headerLength:
            self._responseHeader = self._dictDecode(self._recvBuffer[:self._headerLength], self.__FORMAT)
            self._recvBuffer = self._recvBuffer[self._headerLength:]
            for header in ('byteorder', 'content_length'):
                if header not in self._responseHeader:
                    raise ValueError(f"Missing required header '{header}'.")

    def processResponse(self):
        responseLength = self._responseHeader['content_length']
        if not len(self._recvBuffer) >= responseLength:
            return
        data = self._recvBuffer[:responseLength]
        self._recvBuffer = self._recvBuffer[responseLength:]
        self.response = self._dictDecode(data, self.__FORMAT)
        logging.info(f'[RECEIVED] Received request {self.response} from {self.addr}')
        # Close when response has been processed
        # self.close()