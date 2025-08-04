import cv2
import numpy as np
from pyzbar.pyzbar import decode
import pyotp
import time

#image = cv2.imread('qr2.jpeg')

#decoded_objects = decode(image)

#otpauth://totp/Digitain%203:ivan@fenomenbet.com?secret=GA3DCYLDMI2DSZDDHE2GIYZY&issuer=Digitain%203
#for obj in decoded_objects:
#    print("Decoded Data: ", obj.data)
#    secret_key = obj.data.decode('utf-8').split('secret=')[1].split('&issuer')[0]
#
#print(f"Secret Key: {secret_key}")

totp = pyotp.TOTP("GRTDGMLEGBSGMZBXMM2DEMBZ")

while True:
    otp_code = totp.now()
    print(f"{otp_code}")
    time.sleep(30)