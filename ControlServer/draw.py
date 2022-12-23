import cv2
import numpy as np
from shapely.geometry import Polygon

def draw_rec(image, x_from, y_from, x_to, y_to,color = (255, 255, 255),thickness=2, copy = False):
    if copy:
        image_new = np.copy(image)
    else:
        image_new = image
    image_new = cv2.rectangle(image_new, (x_from, y_from),(x_to, y_to), color,thickness)
    return image_new

def draw_circle(image, x_from, y_from, radius=5,color = (255, 255, 255),thickness=2, copy = False):
    if copy:
        image_new = np.copy(image)
    else:
        image_new = image
    image_new = cv2.circle(image_new, (x_from, y_from),radius, color,thickness)
    return image_new

def get_center(x_from, y_from, x_to, y_to):
    return int((x_from+x_to)/2), int((y_from+y_to)/2)

def get_attribute(predict):
    predict[0:4] = predict[0:4].astype(int)
    return predict[0],predict[1],predict[2],predict[3],predict[4],predict[5]

def drawStage(frame):
    
    
    # # frame = cv2.polylines(frame, [np.int32([[80, 11], [615, 11], [610, 460], [85, 462], [80, 11]])], False, (255,0, 0), thickness=1)
    # # vi tri gần 1
    # frame = cv2.polylines(frame, [np.int32([[129, 213], [218, 212], [219, 410], [149, 409], [129, 213]])], False, (255,0, 0), thickness=1)
    # # vi tri 1
    # frame = cv2.polylines(frame, [np.int32([[134, 293],[132, 245],[173, 244],[173, 293],[134, 293]])], False, (255,0, 0), thickness=1)
    
    # # vi tri gần 2 3
    # frame = cv2.polylines(frame, [np.int32([[220, 26], [221, 146], [442, 148], [439, 24], [346, 15], [220, 26]])], False, (255,0, 0), thickness=1)
    # # vi tri 2
    # frame = cv2.polylines(frame, [np.int32([[265, 9],[266, 77],[297, 78],[290, 7],[265, 9]])], False, (255,0, 0), thickness=1)
    # # vi tri gần 3
    # # vi tri 3
    # frame = cv2.polylines(frame, [np.int32([[362, 11],[361, 75],[398, 79],[400, 11],[362, 11]])], False, (255,0, 0), thickness=1)
    
    
    # # # vi trí gần đích
    # frame = cv2.polylines(frame, [np.int32([[364, 414],[367, 473],[301, 473],[300, 416],[364, 414]])], False, (255,0, 0), thickness=1)
    # # # dich
    # frame = cv2.polylines(frame, [np.int32([[301, 349], [305, 458], [513, 435], [522, 382], [445, 340], [301, 349]])], False, (255,0, 0), thickness=1)

    # frame = cv2.polylines(frame, [np.int32([[147, 351],[225, 352],[223, 454],[158, 447],[147, 351]])], False, (255,0, 0), thickness=1)
    # frame = cv2.polylines(frame, [np.int32([[441, 352],[441, 458],[504, 444],[516, 352],[441, 352]])], False, (255,0, 0), thickness=1)
    # frame = cv2.polylines(frame, [np.int32([[448, 147],[529, 149],[522, 45],[442, 31],[448, 147]])], False, (255,0, 0), thickness=1)
    # frame = cv2.polylines(frame, [np.int32([[217, 149],[141, 143],[141, 44],[218, 33],[217, 149]])], False, (255,0, 0), thickness=1)

    # frame = cv2.polylines(frame, [np.int32([[143, 41],[137, 240],[157, 443],[341, 467],[503, 445],[529, 226],[521, 43],[324, 19],[143, 41]])], False, (255,0, 0), thickness=1)

    return frame

def listPosstion():
    # vi tri gần 1
    # locateNear1 =       [[249, 347], [207, 450], [163, 447], [134, 213], [222, 206], [249, 347]]
    locateNear1 = [[131, 214], [219, 215], [223, 348], [257, 352], [159, 446], [131, 214]]
    
    
    # vi tri 1
    locate1 = [[134, 293],[132, 245],[173, 244],[173, 293],[134, 293]]
    # vi tri gần 2 3
    locateNear23 = [[220, 26], [221, 146], [442, 148], [439, 24], [346, 15], [220, 26]]
    # vi tri 2
    locate2 = [[248, 10], [249, 70], [294, 69], [294, 10], [248, 10]]
    # vi tri 3
    locate3 = [[362, 11],[361, 75],[398, 79],[400, 11],[362, 11]]
    # # vi trí gần đích
    locateNearStart = [[295, 359],[293, 465],[504, 447],[414, 358],[295, 359]]
    # # dich
    locateStart = [[364, 414],[367, 473],[301, 473],[300, 416],[364, 414]]
    locateJetbotAndProduct = [[315, 404], [405, 405], [412, 465], [314, 466], [315, 404]]

    locateLeft1 = [[147, 351],[225, 352],[223, 454],[158, 447],[147, 351]]
    locateLeft2 =[[441, 352],[441, 458],[504, 444],[516, 352],[441, 352]]
    locateLeft3 =[[448, 147],[529, 149],[522, 45],[442, 31],[448, 147]]
    locateLeft4 =[[217, 149],[141, 143],[141, 44],[218, 33],[217, 149]]
    
    locateInsideYard = [[143, 41],[137, 240],[157, 443],[341, 467],[503, 445],[529, 226],[521, 43],[324, 19],[143, 41]]
    locateSquareInsideYard = [[220, 146], [226, 351], [441, 355], [445, 148], [220, 146]]
    
    locateGoToStorage1= [[406, 462],[407, 354], [224, 350], [221, 213], [129, 214], [156, 448], [406, 462]] 
    locateGoToStorage2= [[156, 448], [406, 462],[407, 354], [224, 350], [221, 148], [314, 142], [310, 12], [146, 38], [134, 217], [156, 448]]
    locateGoToStorage3= [[156, 448], [406, 462],[407, 354], [224, 350], [221, 148], [431, 147],[427, 26],[310, 12], [146, 38], [134, 217], [156, 448]]
    locateGoToStart1 = [[136, 218], [141, 38], [256, 19], [353, 18], [453, 26], [521, 42], [527, 249], [505, 446], [297, 468], [294, 354], [441, 351], [445, 146], [221, 146], [220, 214], [136, 218]]
    locateGoToStart2 = [[310, 17], [428, 22], [522, 44], [526, 248], [505, 448], [299, 464], [296, 355], [440, 352], [446, 147], [310, 144], [310, 17]]
    locateGoToStart3 = [[428, 24],[522, 42],[528, 248],[508, 448],[299, 466],[298, 354],[441, 353],[446, 145],[429, 148],[428, 24]]
    
    locateCheckStorage1 = [[124, 257],[183, 258],[181, 332],[129, 329],[124, 257]]
    locateCheckStorage2 = [[203, 22], [293, 19], [296, 88], [208, 93], [203, 22]]
    locateCheckStorage3 = [[338, 18], [409, 22], [407, 92], [336, 90], [338, 18]]

    area1 = Polygon(locate1)
    area2 = Polygon(locate2)
    area3 = Polygon(locate3)
    areaStart = Polygon(locateStart)
    areaNear1 = Polygon(locateNear1)
    areaNear23 = Polygon(locateNear23)
    areaNearStart = Polygon(locateNearStart)
    areaJetbotAndProduct = Polygon(locateJetbotAndProduct)
    areaLeft1 = Polygon(locateLeft1)
    areaLeft2 = Polygon(locateLeft2)
    areaLeft3 = Polygon(locateLeft3)
    areaLeft4 = Polygon(locateLeft4)
    areaInsideYard = Polygon(locateInsideYard)
    areaSquareInsideYard = Polygon(locateSquareInsideYard)
    areaGoToStorage1 = Polygon(locateGoToStorage1)
    areaGoToStorage2 = Polygon(locateGoToStorage2)
    areaGoToStorage3 = Polygon(locateGoToStorage3)
    areaGoToStart1= Polygon(locateGoToStart1)
    areaGoToStart2 = Polygon(locateGoToStart2)
    areaGoToStart3 = Polygon(locateGoToStart3)
    areaCheckStorage1 = Polygon(locateCheckStorage1)
    areaCheckStorage2 = Polygon(locateCheckStorage2)
    areaCheckStorage3 = Polygon(locateCheckStorage3)
    
    
    
    
    
    
    locattionJetbot = {}
    
    locattionJetbot["area1"] = area1
    locattionJetbot["area2"] = area2
    locattionJetbot["area3"] = area3
    locattionJetbot["areaStart"] = areaStart
    locattionJetbot["areaNear1"] = areaNear1
    locattionJetbot["areaNear23"] = areaNear23
    locattionJetbot["areaNearStart"] = areaNearStart
    locattionJetbot["areaJetbotAndProduct"] = areaJetbotAndProduct
    locattionJetbot["areaLeft1"] = areaLeft1
    locattionJetbot["areaLeft2"] = areaLeft2
    locattionJetbot["areaLeft3"] = areaLeft3
    locattionJetbot["areaLeft4"] = areaLeft4
    locattionJetbot["insideYard"] = areaInsideYard
    locattionJetbot["squareInsideYard"] = areaSquareInsideYard
    
    locattionJetbot["goToStorage"] = {"KHO 1": areaGoToStorage1, "KHO 2": areaGoToStorage2,"KHO 3": areaGoToStorage3}
    locattionJetbot["goToStart"] = {"KHO 1": areaGoToStart1, "KHO 2": areaGoToStart2,"KHO 3": areaGoToStart3}
    locattionJetbot["areaProductRelease"] = {"KHO 1": areaCheckStorage1, "KHO 2": areaCheckStorage2,"KHO 3": areaCheckStorage3}
    
    
    
    return locattionJetbot    
    

    