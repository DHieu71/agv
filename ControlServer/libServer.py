import sys
import selectors
import struct
import logging
import pickle
import time
from shapely.geometry import Point
from draw import listPosstion
import cv2
from camqr import qrCode


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
        self.case = {
            'goToStart': 0,
            'goToStorage': 1,
        }
        self.hasProduct = None
        self.firstCheckStart = None
        
        self.storagePosition = {
            'KHO 1': 'storage1',
            'KHO 2': 'storage2',
            'KHO 3': 'storage3'
        }
        self.storages = ['KHO 1', 'KHO 2', 'KHO 3']
        
        # Cam
        self.camera = None
        
        # Map
        self.heightReal = 106
        self.widthReal = 125
        self.heightCam = 450
        self.widthCam = 390

        # Jetbot
        self.xyJetbot = None
        
        # Product
        self.colorBox = None
        self.xyProducts = None
        self.hasProduct = None
        self.typeOfProduct = None
        self.location = listPosstion()       
        self.vid = cv2.VideoCapture(0, cv2.CAP_DSHOW)
               
        self.startTimeRelease = None
        self.checkRelease = None
        
        # data of jetbot in road or map
        self.startTime = None
        self.check = True

        self.__requestGET = {
            "isReady": self.__isReady,
            "checkProductsInMap": self.__checkProductsInRoad,
            "isJetbotInRoad": self.__isJetbotInRoad,
            "isStartLocation": self.__isStartLocation,
            "scanProduct": self.__scanProduct,
            "releaseProduct": self.__releaseProduct,
            "takeProduct": self.__takeProduct,
            "arrivedStorage": self.__arrivedStorage,
            "arrivedStart":self.__arrivedStart,
        }
        
        self.data = {
            'isOn': None,
            'storage': [5, 2, 3],
            'pin': None,
            "working": None,
            'target': None,
            'position': None,
            'targetPosition': None,
            'isRelease': None,
            'isWarning': None,
            'warningMessage': None,
        }

    def addInfo(self, sock, addr):
        self.sock = sock
        self.addr = addr
    
    def addData(self, xyJetbot, xyProducts, colorBox, camera):
        self.xyJetbot = xyJetbot
        self.xyProducts = xyProducts
        self.colorBox = colorBox
        if xyJetbot:
            self.data['position'] = [xyJetbot[0] - 136, xyJetbot[1] - 16]
        self.camera = camera
            
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
            print('pass')
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
            if not query.isnumeric(): 
                
            # answer = requestGET.get(query) or f"No match for '{query}'."
            # answer = random.randint(1, 20)
                answer = self.__requestGET.get(query)()
                response = {"result": answer}
            else:
                response = {"result": query}
                self.data['pin'] = query
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

    def __isTurnOnCamera(self):
        return self.camera.size != 0 and self.vid.isOpened()

    def __isReady(self):
        if self.__isTurnOnCamera():
            self.data['isWarning'] = False
            self.vid.release()
            return "YES"
        self.data['isWarning'] = True
        self.data['warningMessage'] = 'disconnectCam'
        return "NO"
    
    def __isJetbotInRoad(self):
        if self.xyJetbot:
            if self.location['squareInsideYard'].contains(Point(self.xyJetbot)):
                self.data['isWarning'] = True
                self.data['warningMessage'] = 'outOfRoad'
                return "NO"
            self.data['isWarning'] = False
            return "YES"
        self.data['isWarning'] = True
        self.data['warningMessage'] = 'outOfMap'
        self.data['position'] = None
        return "NO"
    
    def __isStartLocation(self):
        if self.xyJetbot:
            pointJetbot = Point(self.xyJetbot)
            if self.location["areaStart"].contains(pointJetbot):
                self.data['working'] = 'scanProduct'
                self.data['target'] = None
                self.data['targetPosition'] = 'start'
                self.data['position'] = None
                self.vid = cv2.VideoCapture(0, cv2.CAP_DSHOW)
                self.firstCheckStart = False
                return "YES"
            
        self.data['working'] = 'goToStart'
        self.data['target'] = 'START'
        self.data['targetPosition'] = None
        self.firstCheckStart = True
        return "NO"
    
    def __checkProductsInRoad(self, case='goToStart'):
        if self.firstCheckStart:
            self.firstCheckStart = False
            purpose = "MAP"
        else:
            purpose = self.typeOfProduct
            
        if self.xyProducts:
            if (len(self.xyProducts) > self.case[case] and self.hasProduct == None) or (sum([1 for product in self.xyProducts if self.location[case][purpose].contains(Point(product))]) > self.case[case]):
                self.data['isWarning'] = True
                self.data['warningMessage'] = 'hasProductsInRoad'
                return "YES"
        
        self.data['isWarning'] = False
        return "NO"
    
    def __scanProduct(self):
        qr = qrCode(self.vid)
        self.data['working'] = 'scanProduct'
        self.data['target'] = None
        self.data['targetPosition'] = 'start'
        self.data['position'] = None
        if qr:
            self.typeOfProduct = qr
            self.vid.release()
            return "YES" 
        return "NO"
    
    def __takeProduct(self):
        if self.xyProducts:
            pointProduct = Point(self.xyProducts[0])
            if self.location["areaJetbotAndProduct"].contains(pointProduct):
                if self.colorBox == self.typeOfProduct:
                    self.data['working'] = 'transportProduct'
                    self.data['target'] = self.typeOfProduct
                    self.data['targetPosition'] = None
                    self.data['isWarning'] = False
                    self.hasProduct = True
                    return "YES"
                self.data['isWarning'] = True
                self.data['warningMessage'] = 'wrongProduct'
                self.data['targetPosition'] = 'start'
                self.data['position'] = None    
                return "NO"
        self.data['working'] = 'waitProduct'
        self.data['target'] = None
        self.data['targetPosition'] = 'start'
        self.data['position'] = None
        return "NO"
    
    
    def __releaseProduct(self):
        hasXYProduct = None
        if self.xyProducts:
            for product in self.xyProducts:
                if self.location['areaProductRelease'][self.typeOfProduct].contains(Point(product)):
                    hasXYProduct = True
                    continue
        if not hasXYProduct and self.checkRelease:
            self.startTimeRelease = time.time()            
            self.checkRelease = False  
        if not hasXYProduct and not self.checkRelease:
            currentTime = abs(time.time() - self.startTimeRelease)
            
            if currentTime >= 2:
                self.checkRelease = None
                self.data['storage'][self.storages.index(self.typeOfProduct)] += 1
                    
                self.data['working'] = 'goToStart'
                self.data['target'] = 'START'
                self.data['targetPosition'] = None
                self.data['isRelease'] = True
                self.hasProduct = False
                return "YES"
            
        if hasXYProduct:
            self.checkRelease = True

        self.data['working'] = 'releaseProduct'
        self.data['target'] = self.typeOfProduct
        self.data['position'] = None
        return "NO"
   
    def __arrivedStorage(self):
        if not self.__isJetbotOutRoad() and self.hasProduct:
            if self.__checkProductsInRoad(case='goToStorage') == 'YES' or self.__isDropProduct(self.xyJetbot, self.xyProducts):
                return "STOP"
            if not self.xyJetbot:
                return "STOP"
            pointJetbot = Point(self.xyJetbot)
            if self.__isStopZone(pointJetbot, self.typeOfProduct):
                self.data['position'] = None
                self.data['targetPosition'] = self.storagePosition[self.typeOfProduct]
                self.checkRelease = True
                return "YES"
            if self.__isGoalZone(pointJetbot, self.typeOfProduct):
                return "GOAL"
            if self.__isTurnZone(pointJetbot):
                return "LEFT"
            return "STRAIGHT"
        if not self.hasProduct and self.__isDropProduct(self.xyJetbot, self.xyProducts):
            return "STOP"
        elif not self.hasProduct and not self.__isDropProduct(self.xyJetbot, self.xyProducts):
            return "STRAIGHT"
        return "STOP"
               
    def __arrivedStart(self):
        if not self.__isJetbotOutRoad() and not self.hasProduct:
                
            if self.__checkProductsInRoad() == 'YES':
                return "STOP"
            
            if not self.xyJetbot:
                return "STOP"
            
            pointJetbot = Point(self.xyJetbot)
            if self.location["areaStart"].contains(pointJetbot):
                self.data['working'] = 'waitProduct'
                self.data['target'] = None
                self.data['targetPosition'] = 'start'
                self.data['position'] = None
                self.vid = cv2.VideoCapture(0, cv2.CAP_DSHOW);
                return "YES"
            
            self.data['working'] = 'goToStart'
            self.data['target'] = 'START'
            self.data['targetPosition'] = None
            
            if self.location["areaNearStart"].contains(pointJetbot):
                return "GOAL"
            
            if self.__isTurnZone(pointJetbot):
                return "LEFT"
            return "STRAIGHT"
        return "STOP"
    
    def __isJetbotOutRoad(self):
        if not self.xyJetbot:
            if self.check:
                self.startTime = time.time()
                self.check = False
            else:
                currentTime = abs(time.time() - self.startTime)
                if currentTime >= 1:
                    self.data['isWarning'] = True
                    self.data['warningMessage'] = 'outOfMap'
                    self.data['position'] = None
                    return True
        else:
            self.check = True
            if self.location["squareInsideYard"].contains(Point(self.xyJetbot)):
                self.data['isWarning'] = True
                self.data['warningMessage'] = 'outOfRoad'
                return True
        self.data['isWarning'] = False
        return False

    def __isDropProduct(self, jetbot, products):
        if jetbot and products:
            for product in products:
                if self.location['goToStorage'][self.typeOfProduct].contains(Point(product)):
                    distance = int(((jetbot[0] - product[0])**2 + (jetbot[1] - product[1])**2) ** (1/2))
                    if distance > 80:
                        self.data['isWarning'] = True
                        self.data['warningMessage'] = 'dropProduct'
                        self.hasProduct = False
                        return True
        self.data['isWarning'] = False
        self.hasProduct = True
        return False
        
    def __isStopZone(self, point, type):
        if type == 'KHO 1' and self.location["area1"].contains(point):
            return True
        if type == 'KHO 2' and self.location["area2"].contains(point):
            return True
        if type == 'KHO 3' and self.location["area3"].contains(point):
            return True
        return False
    
    def __isGoalZone(self, point, type):
        if type == 'KHO 1' and self.location['areaNear1'].contains(point):
            return True
        if (type == 'KHO 2' or type == 'KHO 3') and self.location['areaNear23'].contains(point):
            return True
        return False
        
    def __isTurnZone(self, point):
        if self.location['areaLeft1'].contains(point):
            return True
        if self.location['areaLeft2'].contains(point):
            return True
        if self.location['areaLeft3'].contains(point):
            return True
        if self.location['areaLeft4'].contains(point):
            return True
        return False
                    