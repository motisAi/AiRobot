import serial
import struct
import time
import cv2
import numpy as np

ser = serial.Serial('COM4', 115200, timeout=2)  # התאם את הפורט

print("Waiting for image...")
while True:
    # חיפוש התחלת התמונה
    line = ser.read_until(b'END_IMAGE').decode('utf-8').strip()
    try:
        #text = line.decode('utf-8').strip()
        print(line)
        
        if line == "START_IMAGE":
            print("Image start detected!")
            
            # קריאת 4 בייטים לגודל התמונה
            size_bytes = ser.read(4)
            if len(size_bytes) < 4:
                print("Failed to read image size")
                continue
                
            image_size = struct.unpack('<L', size_bytes)[0]
            print(f"Image size: {image_size} bytes")
            
            # קריאת נתוני התמונה הבינאריים
            image_data = bytearray()
            bytes_read = 0
            
            while bytes_read < image_size:
                chunk = ser.read(min(1024, image_size - bytes_read))
                if not chunk:
                    break
                bytes_read += len(chunk)
                image_data.extend(chunk)
                
            print(f"Read {bytes_read} bytes out of {image_size}")
            
            # בדיקה אם קיבלנו את כל התמונה
            if bytes_read == image_size:
                # המרה לתמונה
                try:
                    nparr = np.frombuffer(image_data, np.uint8)
                    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    
                    if img is not None:
                        print("Image decoded successfully!")
                        cv2.imshow('Image', img)
                        cv2.waitKey(1)  # רענון חלון התצוגה
                    else:
                        print("Failed to decode image")
                except Exception as e:
                    print(f"Error decoding image: {e}")
            
            # חיפוש סיום התמונה
            end_line = ser.readline().decode('ascii').strip()
            try:
              #  end_text = end_line.decode('utf-8').strip()
                if "END_IMAGE" in end_line:
                    print("Image end detected!")
            except:
                pass
    except:
        # דילוג על בייטים שאינם UTF-8 תקפים
        pass