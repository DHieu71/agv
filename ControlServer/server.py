#!/usr/bin/env python3

import socket
import selectors
import logging
import libServer
import traceback    
import threading
import cv2
import time
from model import Yolov5, CamOversee
from draw import drawStage
import socketio

sio = socketio.Client()
lock = threading.Lock()

def run():
    while True:
        try:
            sio.connect('http://192.168.43.36:3000', namespaces=['/jetbot'])
        except:
            pass
        sio.sleep(2)
        sio.wait()
    
@sio.event
def connect():
    print('connection established')

@sio.event
def disconnect():
    print('disconnected from server')

yolo = Yolov5(classDetect =[80, 81],confident = 0.7)
yolo.loadModel(source = "local", path= 'best_4h00_1511\\best.pt')
logging.basicConfig(format='%(levelname)s - %(asctime)s.%(msecs)03d: %(message)s', datefmt='%H:%M:%S', level=logging.DEBUG)

HOST = '192.168.43.36'
PORT = 1255
ADDR = (HOST, PORT)
FORMAT = 'utf-8'
xyJetbot, xyProducts,colorBox, frame = [None]*4
sel = selectors.DefaultSelector()

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(ADDR)
logging.info(f'[STARTING] Server is starting....')
server.listen()
logging.info(f"[LISTENING] Server is listening on {ADDR}")
server.setblocking(False)
sel.register(server, selectors.EVENT_READ, data=None)

def acceptWrapper(sock):
    client, addr = sock.accept()  # Should be ready to read
    logging.info(f"[NEW CONNECTION] Accepted connection from {addr}")
    client.setblocking(False)
    message = libServer.Message(sel, client, addr)
    message.data['isOn'] = True
    with lock:                    
        sio.emit('jetbot', message.data, namespace='/jetbot')
    sel.register(client, selectors.EVENT_READ, data=message)

def runServer():
    global isFirstConnectToJetbot, maxDistance, frame
    try:
        while True:
            events = sel.select(timeout=None)
            for key, mask in events:
                if key.data is None:
                    acceptWrapper(key.fileobj)
                else:
                    message = key.data
                    message.addData(xyJetbot, xyProducts, colorBox, frame)
                    try:
                        data = message.processEvents(mask)
                        if data:
                            with lock:
                                sio.emit('jetbot', data, namespace='/jetbot')
                    except Exception:
                        logging.info(f'[ERROR] '
                            f"Main: Error: Exception for {message.addr}:\n"
                            f"{traceback.format_exc()}"
                        )
                        message.data['isOn'] = False
                        message.vid.release()
                        with lock:
                            sio.emit('jetbot', message.data, namespace='/jetbot')
                        message.close()
                        
    except KeyboardInterrupt:
        logging.info("[ERROR] Caught keyboard interrupt, exiting")
    finally:
        sel.close()

def observeJetbot():
    global xyJetbot, xyProducts,colorBox, frame
    yolo.optimizeModel()
    camera = CamOversee("rtsp://admin:L2054960@192.168.43.7:554/cam/realmonitor?channel=1&subtype=1&latency=0")
    while True:
        frame = camera.getFrame()
        frame,dicXY = yolo.detect(frame=frame,recBox = True, circleBox = True)
        if dicXY:
            xyJetbot = dicXY['80']
            xyProducts =  dicXY['81']
            if dicXY['81'] and yolo.checkColor:
                saveCrop, colorBox = yolo.takeCrop()
        frame = drawStage(frame)
        cv2.imshow("anh", frame)
        key = cv2.waitKey(1)
        if key == ord("/"):
            break
    cv2.destroyAllWindows()

serverThread = threading.Thread(target=runServer)
serverThread.start()

observeJetbotThread = threading.Thread(target=observeJetbot)
print("/////////////////////////////////////////////")
observeJetbotThread.start()

socketThread = threading.Thread(target=run)
socketThread.start()
