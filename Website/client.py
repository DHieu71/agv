#!/usr/bin/env python3

import sys
import socket
import selectors
import types
import logging
from urllib import request, response
import libClient
import traceback
import time

logging.basicConfig(format='%(levelname)s - %(asctime)s.%(msecs)03d: %(message)s', datefmt='%H:%M:%S', level=logging.DEBUG)

# HOST = '192.168.0.107'
# HOST = '192.168.1.130'
HOST = '192.168.43.36'

PORT = 1233
ADDR = (HOST, PORT)


sel = selectors.DefaultSelector()

def createRequest(action, value):
    return dict(
        action=action,
        value=value
    )

def startConnection(host, port):
    server_addr = (host, port)
    logging.info(f"[STARTING] Starting connection to {server_addr}")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setblocking(False)
    sock.connect_ex(server_addr)
    events = selectors.EVENT_READ | selectors.EVENT_WRITE
    message = libClient.Message(sel, sock, server_addr)
    sel.register(sock, events, data=message)
    return message, sock, events

def sendRequestToServer(msg, sock, events, request):
    sel.modify(sock, events, msg)
    messageResponse = ""
    try:
        while True:
            objs = sel.select(timeout=0.01)
            if not objs and messageResponse:
                return messageResponse
            if objs:
                for key, mask in objs:
                    message = key.data
                    message.addRequest(request)
                    try:
                        messageResponse = message.processEvents(mask)
                    except Exception:
                        logging.info(f'[ERROR] '
                            f"Main: Error: Exception for {message.addr}:\n"
                            f"{traceback.format_exc()}"
                        )
                        message.close()
            # Check for a socket being monitored to continue.
            if not sel.get_map():
                break
    except KeyboardInterrupt:
        logging.info("Caught keyboard interrupt, exiting")
        sel.close()

message, sock, events = startConnection(HOST, PORT)


def checkReadyFromServer():
    isReady = False
    logging.info(f'[NOTIFICATION] Waiting ready from server')
    while not isReady:
        request = createRequest('GET', 'isReady')
        response = sendRequestToServer(message, sock, events, request)
        if response['result'] == 'YES':
            isReady = True
    logging.info(f'[NOTIFICATION] Ready for reading/writing to server')

def checkProduct():
    hasProduct = False
    logging.info(f'[CHECKING] Checking product')
    while not hasProduct:
        request = createRequest('GET', 'hasProduct')
        response = sendRequestToServer(message, sock, events, request)
        if response['result'] == 'YES':
            hasProduct = True
    logging.info(f'[NOTIFICATION] Product is ready for transport')

def checkStartLocation():
    isStartLocation = False
    logging.info(f'[CHECKING] Checking product')
    while not isStartLocation:
        request = createRequest('GET', 'isStartLocation')
        response = sendRequestToServer(message, sock, events, request)
        if response['result'] == 'YES':
            isStartLocation = True
        else:
            goToStartLocation()
    logging.info(f'[NOTIFICATION] Product is ready for transport')

def goToStartLocation():
    isDone = False
    logging.info(f'[CHECKING] Checking product')
    while not isDone:
        request = createRequest('GET', 'arrivedStart')
        response = sendRequestToServer(message, sock, events, request)
        if response['result'] == 'YES':
            isDone = True
    logging.info(f'[NOTIFICATION] Product is ready for transport')

def goToLocation():
    isDone = False
    logging.info(f'[CHECKING] Checking product')
    while not isDone:
        request = createRequest('GET', 'arrivedPark')
        response = sendRequestToServer(message, sock, events, request)
        if response['result'] == 'YES':
            isDone = True
    logging.info(f'[NOTIFICATION] Product is ready for transport')

def takeProduct():
    isDone = False
    logging.info(f'[CHECKING] Checking product')
    while not isDone:
        request = createRequest('GET', 'takeProduct')
        response = sendRequestToServer(message, sock, events, request)
        if response['result'] == 'YES':
            isDone = True
    logging.info(f'[NOTIFICATION] Product is ready for transport')

def releaseProduct():
    isDone = False
    logging.info(f'[CHECKING] Checking product')
    while not isDone:
        request = createRequest('GET', 'releaseProduct')
        response = sendRequestToServer(message, sock, events, request)
        if response['result'] == 'YES':
            isDone = True
    logging.info(f'[NOTIFICATION] Product is ready for transport')

def run():
    checkReadyFromServer()
    checkStartLocation()
    while True:
        checkProduct()
        takeProduct()
        goToLocation()
        releaseProduct() 
        goToStartLocation()

if __name__ == '__main__':
    run()