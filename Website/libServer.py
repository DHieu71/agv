import sys
import selectors
import struct
import logging
import random
import pickle
import cv2
import numpy as np
from pyzbar.pyzbar import decode
import time

logging.basicConfig(format='%(levelname)s - %(asctime)s.%(msecs)03d: %(message)s', datefmt='%H:%M:%S', level=logging.DEBUG)


class Message:
    def __init__(self, selector, sock, addr):
        self.selector = selector
        self.sock = sock
        self.addr = addr
        self._recvBuffer = b""
        self._sendBuffer = b""
        self._headerLength = None
        self._requestHeader = None
        self.request = None
        self.response = None
        self.isresponseCreated = False
        self.__FORMAT = 'utf-8'

        # Jetbot
        self.jetbotLocation = None

        # Product
        self.hasProduct = None
        self.typeOfProdcut = None

        self.__requestGET = {
            "isReady": self.__isReady,
            "isStartLocation": self.__isStartLocation,
            "hasProduct": self.__hasProduct,
            "releaseProduct": self.__releaseProduct,
            "takeProduct": self.__takeProduct,
            "arrivedPark": self.__arrivedPark,
            "nearPark": self.__nearPark,
            "arrivedStart":self.__arrivedStart,
            "nearStart": self.__nearStart,
        }
        
        self.data = {
            'isOn': None,
            'isFirstConnect': None,
            'storage': [0, 0, 0],
            'pin': None,
            'working': None,
            'target': None,
            'position': None,
            'targetPosition': None,
            'warning': None,
            'isRelease': None,
            'typeOfProduct': None
        }

    def addInfo(self, sock, addr):
        self.sock = sock
        self.addr = addr

    def addJetbotLocation(self, jetbotLocation):
        self.jetbotLocation = jetbotLocation

    def _resetResponse(self):
        self._recvBuffer = b""
        self._sendBuffer = b""
        self._headerLength = None
        self._requestHeader = None
        self.request = None
        self.response = None
        self.isresponseCreated = False
        self._setSelectorEventsMask('r')

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
            logging.info(f"[SENDING] Sending response {self.response} to {self.addr}")
            try:
                # Should be ready to write
                sent = self.sock.send(self._sendBuffer)
            except BlockingIOError:
                # Resource temporarily unavailable (errno EWOULDBLOCK)
                pass
            else:
                self._sendBuffer = self._sendBuffer[sent:]
                # Close when the buffer is drained. The response has been sent.
                # if sent and not self._sendBuffer:
                #     self.close()
                #     self.isresponseCreated = False
                self._resetResponse()


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

    def _createResponseJsonContent(self):
        action = self.request.get("action")
        if action == "GET":
            query = self.request.get("value")
            # answer = requestGET.get(query) or f"No match for '{query}'."
            # answer = random.randint(1, 20)
            answer = self.__requestGET.get(query)()
            response = {"result": answer}
        else:
            response = {"result": f"Error: invalid action '{action}'."}
        return response

    def processEvents(self, mask):
        if mask & selectors.EVENT_READ:
            self.read()
        if mask & selectors.EVENT_WRITE:
            self.write()
            return self.data

    def read(self):
        """
            When socket.recv() is called, all of the data that makes up a complete message may not have arrived yet. socket.recv() may need to be called again.

            => This is why there are state checks for each part of the message before the appropriate method to process it is called.
        """
        self._read()

        """
            Before a method processes its part of the message, it first checks to make sure enough bytes have been read into the receive buffer. If they have, it processes its respective bytes, removes them from the buffer and writes its output to a variable that's used by the next processing stage. Because there are three components to a message, there are three state checks and process method calls
        """

        if self._headerLength is None:
            self._processHeaderLength()
        
        if self._headerLength is not None:
            if self._requestHeader is None:
                self._processRequestHeader()
        
        if self._requestHeader is not None:
            if self.request is None:
                self.processRequest()
    
    def write(self):
        """
            Method checks first for a request. if one exists and a response hasn't been created
                => create_response() is called. create_response() method sets the state variable isresponseCreated and writes the response to sthe send buffer
        """
        if self.request:
            
            if not self.isresponseCreated:
                self.createResponse()

        self._write()

    def close(self):
        logging.info(f"[CLOSING] Closing connection to {self.addr}")
        try:
            self.selector.unregister(self.sock)
        except Exception as e:
            logging.info(f'[ERROR] '
                f"selector.unregister() exception for "
                f"{self.addr}: {e}"
            )

        try:
            self.sock.close()
        except OSError as e:
            logging.info(f"[ERROR] socket.close() exception for {self.addr}: {e}")
        finally:
            # Delete reference to socket object for garbage collection
            self.sock = None

    def _processHeaderLength(self):
        headerLength = 2
        if len(self._recvBuffer) >= headerLength:
            self._headerLength = struct.unpack(">H", self._recvBuffer[:headerLength])[0]
            self._recvBuffer = self._recvBuffer[headerLength:]

    def _processRequestHeader(self):
        if len(self._recvBuffer) >= self._headerLength:
            self._requestHeader = self._dictDecode(self._recvBuffer[:self._headerLength], self.__FORMAT)
            self._recvBuffer = self._recvBuffer[self._headerLength:]
            for requestHeader in ("byteorder", "content_length"):
                if requestHeader not in self._requestHeader:
                    raise ValueError(f'Missing required header: {requestHeader}')

    def processRequest(self):
        requestLength = self._requestHeader['content_length']
        if not len(self._recvBuffer) >= requestLength:
            return
        data = self._recvBuffer[:requestLength]
        self._recvBuffer = self._recvBuffer[requestLength:]
        self.request = self._dictDecode(data, self.__FORMAT)
        logging.info(f'[RECEIVED] Received request {self.request} from {self.addr}')
        self._setSelectorEventsMask("w")

    def createResponse(self):
        self.response = self._createResponseJsonContent()
        responseBytes = self._dictEncode(self.response)
        message = self._createMessage(responseBytes)
        self.isresponseCreated = True
        self._sendBuffer += message

    # def __isTurnOnCamera(self):
    #     return self.xy != None

    def __isReady(self):
        # if self.__isTurnOnCamera():
        randomNumber = random.randint(1, 2)
        time.sleep(1)
        if randomNumber == 2:
            return "YES"
        return "NO"

    def __isStartLocation(self):
        # point=  Point(self.xyJetbot)
        randomNumber = random.randint(1, 10)
        time.sleep(1)
        if randomNumber % 2 == 0:
            self.data['working'] = 'waitProduct'
            self.data['target'] = None
            self.data['targetPosition'] = 'start'
            self.data['position'] = None
            return "YES"
        self.data['working'] = 'goToStart'
        self.data['target'] = 'START'
        self.data['targetPosition'] = None
        return "NO"
    
    def __hasProduct(self):
        # qr = qrCode(self.vid)
        # qr = 'kho hàng 1'
        qrs = ['KHO 1', 'KHO 2', 'KHO 3']
        randomNumber = random.randint(0, 2)
        time.sleep(1)
        qr = qrs[randomNumber]
        self.data['working'] = 'waitProduct'
        self.data['target'] = None
        self.data['targetPosition'] = 'start'
        self.data['position'] = None
        if qr:
            self.hasProduct = True
            self.typeOfProdcut = qr
        else:
            self.hasProduct = False
        if self.hasProduct:
            return "YES"
        return "NO"

    def __takeProduct(self):
        # if self.xyProduct:
            # point=  Point(self.xyProduct)
        # if self.location["insideYard"].contains(point):
        randomNumber = random.randint(1, 10)
        time.sleep(1)
        if randomNumber % 2 == 0:
            self.data['working'] = 'transportProduct'
            self.data['target'] = self.typeOfProdcut
            self.data['targetPosition'] = None
            return "YES"
        self.data['working'] = 'waitProduct'
        self.data['target'] = None
        self.data['targetPosition'] = 'start'
        self.data['position'] = None
        return "NO"
    
    def __releaseProduct(self):
        # if not self.xyProduct and self.check:
        #     self.startTime = time.localtime().tm_sec
        #     self.check = False
        # if not self.xyProduct and not self.check:
        #     currentTime = time.localtime().tm_sec - self.startTime
        #     if currentTime >= 2:
        #         self.check = None
        #         if self.typeOfProdcut == "kho hàng 1":
        #             self.data['storage'][0] += 1
        #         elif self.typeOfProdcut == "kho hàng 2":
        #             self.data['storage'][1] += 1
        #         else:
        #             self.data['storage'][2] += 1
                    
        #         self.data['working'] = 'goToStart'
        #         self.data['target'] = 'START'
        #         return "YES"
        # if self.xyProduct:
        #     self.check = True
            
        randomNumber = random.randint(1, 100)
        time.sleep(1)
        if randomNumber % 2 == 0:
            if self.typeOfProdcut == "KHO 1":
                self.data['storage'][0] += 1
                self.data['typeOfProduct'] = self.typeOfProdcut
            elif self.typeOfProdcut == "KHO 2":
                self.data['storage'][1] += 1
                self.data['typeOfProduct'] = self.typeOfProdcut
            else:
                self.data['storage'][2] += 1
                self.data['typeOfProduct'] = self.typeOfProdcut
            self.data['working'] = 'goToStart'
            self.data['target'] = 'START'
            self.data['targetPosition'] = None
            self.data['isRelease'] = True
            return "YES"
        self.data['working'] = 'releaseProduct'
        self.data['target'] = self.typeOfProdcut
        self.data['position'] = None
        return "NO"
    
    
    def __nearPark(self):
        # point=  Point(self.xyJetbot)

        # if self.typeOfProdcut == "kho hàng 1" and self.location["areaNear1"].contains(point):
        #     return "YES"
        # elif self.typeOfProdcut == "kho hàng 2" and self.location["areaNear23"].contains(point):
        #     return "YES"
        # elif self.typeOfProdcut == "kho hàng 3" and self.location["areaNear23"].contains(point):
        #     return "YES"
        
        # if self.location['areaLeft1'].contains(point) or self.location['areaLeft2'].contains(point) or self.location['areaLeft3'].contains(point) or self.location['areaLeft4'].contains(point):
        #     return "LEFT"

       
        return "STRAIGHT"

    
    def __arrivedPark(self):
        # point=  Point(self.xyJetbot)
        randomNumber = random.randint(1, 3)
        time.sleep(1)
        if self.typeOfProdcut == "KHO 1" and randomNumber == 1:
            self.data['targetPosition'] = 'storage1'
            self.data['position'] = None
            return "YES"
        if self.typeOfProdcut == "KHO 2" and randomNumber == 1:
            self.data['targetPosition'] = 'storage2'
            self.data['position'] = None
            return "YES"
        if self.typeOfProdcut == "KHO 3" and randomNumber == 1:
            self.data['targetPosition'] = 'storage3'
            self.data['position'] = None
            return "YES"
        self.data['position'] = [80, 90]
        return 'NO'
    
    def __nearStart(self):
        # point=  Point(self.xyJetbot)
        # if self.location["areaNearStart"].contains(point):
        #     return "YES"
        # if self.location['areaLeft1'].contains(point) or self.location['areaLeft2'].contains(point) or self.location['areaLeft3'].contains(point) or self.location['areaLeft4'].contains(point):
        #     return "LEFT"
        return "STRAIGHT"
    
    def __arrivedStart(self):
        # point=  Point(self.xyJetbot)
        # if self.location["areaStart"].contains(point):
        self.data['isRelease'] = False
        randomNumber = random.randint(1, 10)
        time.sleep(1)
        if randomNumber % 2 == 0:
            self.data['working'] = 'waitProduct'
            self.data['target'] = None
            self.data['targetPosition'] = 'start'
            self.data['position'] = None
            return "YES"
        self.data['working'] = 'goToStart'
        self.data['target'] = 'START'
        self.data['targetPosition'] = None
        self.data['position'] = [80, 90]
        return "NO" 