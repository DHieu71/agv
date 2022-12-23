from imutils.video import VideoStream
import torch
import cv2
import numpy as np
from shapely.geometry import Point
from shapely.geometry import Polygon



class CamOversee:
    def __init__(self, source):
        self.video = VideoStream(src=source, framerate=12).start()
    def getFrame(self):
        return self.video.read()
    
class Yolov5:
    def __init__(self, classDetect,confident) -> None:
        self.model = None
        self.classDetect = classDetect
        self.confident = confident
        self.saveCrop = None
        self.checkColor = None
        self.insideYard = Polygon([[143, 41],[137, 240],[157, 443],[341, 467],[503, 445],[529, 226],[521, 43],[324, 19],[143, 41]])
        self.squareInsideYard = Polygon([[220, 146], [226, 351], [441, 355], [445, 148], [220, 146]])
        self.areaJetbotAndProduct = Polygon([[315, 404], [405, 405], [412, 465], [314, 466], [315, 404]])

    def loadModel(self, source, path):  
        self.model = torch.hub.load('', 'custom', source =source, path=path,force_reload=True)
        
    def optimizeModel(self):
        # self.model = self.model.eval().half()
        self.model = self.model.eval()
        
    def __getCenter(self, predict):
        x1 = predict[0]
        y1 = predict[1]
        x2 = predict[2]
        y2 = predict[3]
        xCenter = int((x1+x2)/2)
        yCenter = int((y1+y2)/2)
        return xCenter, yCenter
    
    def __drawRec(self,image, x_from, y_from, x_to, y_to,color = (0, 0, 255),thickness=2,copy = False):
        if copy:
            image_new = np.copy(image)
        else:
            image_new = image
        image_new = cv2.rectangle(image_new, (x_from, y_from),(x_to, y_to), color = color,thickness = thickness)
        
        return image_new
    def __drawCircle(self,image, x_center, y_center, radius=5,color = (255, 255, 255),thickness=2, copy = False):
        if copy:
            image_new = np.copy(image)
        else:
            image_new = image
        image_new = cv2.circle(image_new, (x_center, y_center),radius, color = color,thickness = thickness)
        return image_new
    
    def __cropProduct(self,frame, y, x, h, w):
        self.saveCrop = frame.copy()[y+5:y+h-5, x+5:x+w-5]
        
    def takeCrop(self):
        self.saveCrop[:,:,2], self.saveCrop[:,:,1], self.saveCrop[:,:,0] = np.average(self.saveCrop, axis=(0,1))
        realColor = self.saveCrop[0,0]
        if realColor[0]>100 and realColor[1]<80 and realColor[2] <80:
            result = "KHO 1"
        elif realColor[0]>80 and realColor[1]>80 and realColor[2]<80:
            result = "KHO 2"
        elif max(realColor) == realColor[2]:
            result = "KHO 3"
        else:
            result = None
        return self.saveCrop, result

    def detect(self, frame, recBox = False, circleBox = False):
        self.checkColor = None
        self.saveCrop = None
        originFrame = np.copy(frame)
        dictXY = {'80':None, '81':[]}
        distanceJetbotToBoxes = []
        predict = self.model(frame)
        classes = predict.pandas().xyxy[0].to_numpy()
        # check detect is empty
        if classes.size == 0:
            return frame, dictXY
        
        # loop detect objectes
        for cls in classes:
            # get infomation in result detect(x from, y from, x to, y to, confider, class id, class name)
            confident, idClass = cls[4], cls[5]
            # check result filter for condition
            if self.confident > confident or idClass not in self.classDetect :
                continue
            
            cls[:4] = cls[:4].astype(int)
            x1,y1,x2,y2 = cls[:4]
            xy = self.__getCenter(cls)
            if not self.insideYard.contains(Point(xy)):
                continue
             
            
            if idClass == 81:
                if self.squareInsideYard.contains(Point(xy)):
                    continue
                if self.areaJetbotAndProduct.contains(Point(xy)):
                    self.checkColor = True
                    self.__cropProduct(originFrame,y1,x1,y2-y1,x2-x1)
                dictXY[str(idClass)].append(xy)
    
            else:
                dictXY[str(idClass)] = xy


            if recBox:
                frame = self.__drawRec(frame, x1, y1, x2, y2,color = (0, 0, 255),thickness=2,copy =True)
            if circleBox:
                frame = self.__drawCircle(frame, xy[0], xy[1],radius = 5,color = (0, 0, 255),thickness=2, copy = True)
            label = cls[6]+" "+ str(round(cls[4],2)) if recBox or circleBox else ''
            frame = cv2.putText(frame, label, (cls[0] - 10, cls[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2) 
        return  frame, dictXY
        