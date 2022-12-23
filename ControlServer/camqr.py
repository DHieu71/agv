import cv2
from pyzbar.pyzbar import decode

def qrCode(vid):
    myData = None
    ret, frame = vid.read()
    decodeBarcode = decode(frame)
    if decodeBarcode:
        for barcode in decodeBarcode:
            myData = barcode.data.decode('utf-8')
            if myData:
                return myData
