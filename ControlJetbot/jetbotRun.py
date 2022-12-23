
import sys
import socket
import selectors
import types
import logging
from urllib import request, response
import libClient
import traceback
import time
import cv2
import torch
from torch2trt import TRTModule
from IPython.display import display
import ipywidgets
import traitlets
from jetbot import Camera, bgr8_to_jpeg, Robot
import torchvision.transforms as transforms
import torch.nn.functional as F
import cv2
import PIL.Image
import numpy as np
import subprocess
from ina219 import INA219
import os



device = torch.device('cuda')
model_trt_s = TRTModule()
model_trt_s.load_state_dict(torch.load('best_steering_model_xy_dithang4_trt.pth'))
model_trt_l = TRTModule()
model_trt_l.load_state_dict(torch.load('best_steering_model_xy_dithang4_trt.pth'))
model_trt_t = TRTModule()
model_trt_t.load_state_dict(torch.load('best_steering_model_xy_turn_2_trt.pth'))

adress = os.popen("i2cdetect -y -r 1 0x41 0x41 | egrep '41' | awk '{print $2}'").read()
if(adress=='41\n'):
    ina = INA219(addr=0x41)
else:
    ina = None


# mean = torch.Tensor([0.485, 0.456, 0.406]).cuda().half()
# std = torch.Tensor([0.229, 0.224, 0.225]).cuda().half()

def preprocess(image):
    mean = torch.Tensor([0.485, 0.456, 0.406]).cuda().half()
    std = torch.Tensor([0.229, 0.224, 0.225]).cuda().half()
    image = PIL.Image.fromarray(image)
    image = transforms.functional.to_tensor(image).to(device).half()
    image.sub_(mean[:, None, None]).div_(std[:, None, None])
    return image[None, ...]

robot = Robot()
# robot.motor_driver._pwm.setPWMFreq(100)
camera = cv2.VideoCapture('nvarguscamerasrc sensor-mode=3 ! video/x-raw(memory:NVMM), width=%d, height=%d, format=(string)NV12, framerate=(fraction)%d/1 ! nvvidconv ! video/x-raw, width=(int)%d, height=(int)%d, format=(string)BGRx ! videoconvert ! appsink' % (
                224, 224, 4, 224, 224))


# logging.basicConfig(format='%(levelname)s - %(asctime)s.%(msecs)03d: %(message)s', datefmt='%H:%M:%S', level=logging.DEBUG)

HOST = '192.168.43.70'
# HOST = '192.168.43.36'

# HOST = '192.168.1.146'

PORT = 1255
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
    
def checkJetbotInRoad():
    isOK = False
    logging.info(f'[NOTIFICATION] Waiting ready from server')
    while not isOK:
        request = createRequest('GET', 'isJetbotInRoad')
        response = sendRequestToServer(message, sock, events, request)
        if response['result'] == 'YES':
            isOK = True
    logging.info(f'[NOTIFICATION] Jetbot is ready')
    
def checkProductsInMap():
    isOK = False
    logging.info(f'[CHECKING] Checking product')
    while not isOK:
        request = createRequest('GET', 'checkProductsInMap')    
        response = sendRequestToServer(message, sock, events, request)
        if response['result'] == 'NO':
            isOK = True
    logging.info(f'[NOTIFICATION] Road is free now')

def scanProduct():
    isScan = False
    logging.info(f'[CHECKING] Checking product')
    while not isScan:
        request = createRequest('GET', 'scanProduct')    
        response = sendRequestToServer(message, sock, events, request)
        if response['result'] == 'YES':
            isScan = True
        logging.info(f'[NOTIFICATION] Product is ready for loading to Jetbot')

def takeProduct():
    takeProduct = False
    logging.info(f'[CHECKING] Checking product')
    while not takeProduct:
        request = createRequest('GET', 'takeProduct')    
        response = sendRequestToServer(message, sock, events, request)
        if response['result'] == 'YES':
            takeProduct = True
        logging.info(f'[NOTIFICATION] Product is ready for transport')
    time.sleep(2)
        
def checkStartLocation():
    isStartLocation = False
    request = createRequest('GET', 'isStartLocation')    
    response = sendRequestToServer(message, sock, events, request)
    if response['result'] == 'YES':
        isStartLocation = True
    if not isStartLocation:
        goToStartLocation()

def getPin():
    global ina
    pin = 0
    for i in range(5):
        pin += int(readVoltage(ina))
    pinAvg = int(pin/5)
    if pinAvg in range(81,90):
        return {
            "STRAIGHT":{"speed_slider":0.24,"steering_gain_slider":0.03, "steering_dgain_slider":0.06, "steering_bias_slider":0.0},
            "LEFT":{"speed_slider":0.24,"steering_gain_slider":0.03, "steering_dgain_slider":0.06, "steering_bias_slider":0.00},
             "GOAL":{"speed_slider":0.23,"steering_gain_slider":0.01, "steering_dgain_slider":0.02, "steering_bias_slider":0.00}}
    elif pinAvg in range(76,82):
        return {
            "STRAIGHT":{"speed_slider":0.24,"steering_gain_slider":0.03, "steering_dgain_slider":0.06, "steering_bias_slider":0.0},
            "LEFT":{"speed_slider":0.24,"steering_gain_slider":0.03, "steering_dgain_slider":0.06, "steering_bias_slider":0.00},
             "GOAL":{"speed_slider":0.23,"steering_gain_slider":0.01, "steering_dgain_slider":0.02, "steering_bias_slider":0.00}}
    elif pinAvg in range(72,76):
        return {
            "STRAIGHT":{"speed_slider":0.24,"steering_gain_slider":0.03, "steering_dgain_slider":0.06, "steering_bias_slider":0.0},
            "LEFT":{"speed_slider":0.24,"steering_gain_slider":0.03, "steering_dgain_slider":0.06, "steering_bias_slider":0.00},
            "GOAL":{"speed_slider":0.24,"steering_gain_slider":0.01, "steering_dgain_slider":0.03, "steering_bias_slider":0.00}}
    elif pinAvg in range(65,73):
        return {
            "STRAIGHT":{"speed_slider":0.25,"steering_gain_slider":0.03, "steering_dgain_slider":0.06, "steering_bias_slider":0.0},
            "LEFT":{"speed_slider":0.24,"steering_gain_slider":0.03, "steering_dgain_slider":0.06, "steering_bias_slider":0.00},
            "GOAL":{"speed_slider":0.25,"steering_gain_slider":0.01, "steering_dgain_slider":0.02, "steering_bias_slider":0.00}}
    elif pinAvg in range(60,66):
        return {
            "STRAIGHT":{"speed_slider":0.25,"steering_gain_slider":0.03, "steering_dgain_slider":0.06, "steering_bias_slider":0.0},
            "LEFT":{"speed_slider":0.24,"steering_gain_slider":0.03, "steering_dgain_slider":0.06, "steering_bias_slider":0.00},
            "GOAL":{"speed_slider":0.24,"steering_gain_slider":0.01, "steering_dgain_slider":0.02, "steering_bias_slider":0.00}}
def goTo(model_1, model_2, model_3, nameRequest):
    global robot, camera
    goTarget = False
    angle = 0.0
    angle_last = 0.0
    isReady = True
    commands = getPin()
    temp = 0
    while not goTarget:
        request = createRequest('GET', nameRequest)
        response = sendRequestToServer(message, sock, events, request)
        result = response['result']
        ret,frame = camera.read()
        if result == "STOP": 
            robot.left_motor.value = 0.0
            robot.right_motor.value = 0.0
            isReady = True
            continue
        elif result == "GOAL":
            xy = model_3(preprocess(frame)).detach().float().cpu().numpy().flatten()
        elif result == "STRAIGHT":
            xy = model_1(preprocess(frame)).detach().float().cpu().numpy().flatten()
        elif result == "LEFT":
            xy = model_2(preprocess(frame)).detach().float().cpu().numpy().flatten()
        elif result == 'YES':
            goTarget = True
            continue
        parameters = commands[result]
        speed_slider = parameters["speed_slider"]
        steering_gain_slider = parameters["steering_gain_slider"]
        steering_dgain_slider = parameters["steering_dgain_slider"]
        steering_bias_slider = parameters["steering_bias_slider"]
        x = xy[0]
        y = (0.5 - xy[1]) / 2.0
        angle = np.arctan2(x, y)
        pid = angle * steering_gain_slider + (angle - angle_last) * steering_dgain_slider
        angle_last = angle
        steering_slider = pid + steering_bias_slider
        
        if isReady:
            robot.left_motor.value = 0.38
            robot.right_motor.value = 0.38
            time.sleep(0.03)
            isReady = False
        if not isReady:
            robot.left_motor.value = max(min(speed_slider + steering_slider, 1.0), 0.0)
            robot.right_motor.value = max(min(speed_slider - steering_slider, 1.0), 0.0)

def goToStorageLocation():
    global model_trt_s,model_trt_l,model_trt_t,robot
    goTo(model_1 = model_trt_s,model_2 = model_trt_l,model_3 = model_trt_t, nameRequest = 'arrivedStorage')
    robot.stop()


def goToStartLocation():
    global model_trt_s,model_trt_l,model_trt_t,robot
    goTo(model_1 = model_trt_s,model_2 = model_trt_l,model_3 = model_trt_t, nameRequest = 'arrivedStart')
    robot.stop()

def releaseProduct():
    global robot
    robot.stop()
    noProduct = False
    while not noProduct:
        request = createRequest('GET', 'releaseProduct')
        response = sendRequestToServer(message, sock, events, request)
        if response["result"] == "YES":
            noProduct = True
    time.sleep(2)
    
def readVoltage(ina):
    bus_voltage = ina.getBusVoltage_V()        # voltage on V- (load side)
    return str(round((bus_voltage-9)/3.6*100))

def sentPower():
#     logging.info(f'[CHECKING] Checking product')
    voltage = readVoltage(ina)
    request = createRequest('GET', voltage)    
    response = sendRequestToServer(message, sock, events, request)
#     logging.info(f'[NOTIFICATION] Product is ready for transport')


    
def run():
    checkReadyFromServer()
    sentPower()
    checkJetbotInRoad()
    checkStartLocation()
    while True:
        sentPower()
        scanProduct()
        takeProduct()
        goToStorageLocation()
        releaseProduct()
        goToStartLocation()

def check():
    isReady = False
    count = 0
    logging.info(f'[NOTIFICATION] Waiting ready from server')
    while count != 10:
        request = createRequest('GET', 'isReady')
        response = sendRequestToServer(message, sock, events, request)
        if response['result'] == 'YES':
            isReady = True
        count += 1
    logging.info(f'[NOTIFICATION] Ready for reading/writing to server') 
        
def run1():
    check()
        
if __name__ == '__main__':
    run()