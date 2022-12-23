#!/usr/bin/env python3
import socket
import selectors
import logging
import libServer
import traceback
import threading
import socketio
import asyncio

logging.basicConfig(format='%(levelname)s - %(asctime)s.%(msecs)03d: %(message)s',
                    datefmt='%H:%M:%S', level=logging.DEBUG)

sio = socketio.Client()


@sio.event
def connect():
    print('connection established')


@sio.event
def disconnect():
    print('disconnected from server')


def run():
    sio.connect('http://localhost:3000', namespaces=['/jetbot'])
    sio.sleep(1)
    sio.wait()


# HOST = '192.168.0.107'
# HOST = '192.168.1.130'
HOST = '192.168.43.70'
PORT = 1233
ADDR = (HOST, PORT)
FORMAT = 'utf-8'

isFirstConnectToJetbot = False

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
    global isFirstConnectToJetbot
    client, addr = sock.accept()  # Should be ready to read
    logging.info(f"[NEW CONNECTION] Accepted connection from {addr}")
    client.setblocking(False)
    message = libServer.Message(sel, client, addr)
    message.data['isOn'] = True
    if not isFirstConnectToJetbot: 
        message.data['isFirstConnect'] = True
    sio.emit('jetbot', message.data, namespace='/jetbot')
    sel.register(client, selectors.EVENT_READ, data=message)

def runServer():
    global isFirstConnectToJetbot
    try:
        while True:
            events = sel.select(timeout=None)
            for key, mask in events:
                if key.data is None:
                    acceptWrapper(key.fileobj)
                else:
                    message = key.data
                    # message.addJetbotLocation(jetbotPosition)
                    try:
                        data = message.processEvents(mask)
                        if data:
                            sio.emit('jetbot', data, namespace='/jetbot')
                    except Exception:
                        logging.info(f'[ERROR] '
                                     f"Main: Error: Exception for {message.addr}:\n"
                                     f"{traceback.format_exc()}"
                                     )
                        message.data['isOn'] = False
                        if not isFirstConnectToJetbot: 
                            message.data['isFirstConnect'] = False
                            isFirstConnectToJetbot = True 
                        sio.emit('jetbot', message.data, namespace='/jetbot')
                        message.close()
    except KeyboardInterrupt:
        logging.info("[ERROR] Caught keyboard interrupt, exiting")
    finally:
        sel.close()


serverThread = threading.Thread(target=runServer)
serverThread.start()

socketThread = threading.Thread(target=run)
socketThread.start()
