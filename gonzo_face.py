# מודול זיהוי פנים עם OpenCV
import cv2
import threading
import time
import numpy as np
import os

class GonzoFace:
    def __init__(self, config=None):
        # קונפיגורציה בסיסית
        self.camera_index = 0
        self.face_detection_scale = 0.5
        self.show_video = True
        self.face_detected = False
        self.running = True
        self.language = "en"  # ברירת מחדל: אנגלית
        
        # טעינת קונפיגורציה אם קיימת
        if config:
            if 'camera_index' in config:
                self.camera_index = config['camera_index']
            if 'face_detection_scale' in config:
                self.face_detection_scale = config['face_detection_scale']
            if 'show_video' in config:
                self.show_video = config['show_video']
            if 'language' in config:
                self.language = config['language']
        
        # איתחול מצלמה
        try:
            self.cap = cv2.VideoCapture(self.camera_index)
            if not self.cap.isOpened():
                raise Exception(f"Could not open camera {self.camera_index}")
            print(f"Camera initialized on index {self.camera_index}")
        except Exception as e:
            print(f"Error initializing camera: {e}")
            self.cap = None
        
        # טעינת מודל זיהוי פנים
        try:
            # שימוש במזהה פנים מובנה של OpenCV
            cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            if not os.path.exists(cascade_path):
                raise Exception(f"Cascade file not found: {cascade_path}")
                
            self.face_cascade = cv2.CascadeClassifier(cascade_path)
            if self.face_cascade.empty():
                raise Exception("Failed to load face detection cascade")
            print("Face detection model loaded")
        except Exception as e:
            print(f"Error loading face detection model: {e}")
            self.face_cascade = None
        
        # מאגר תמונות (אם רוצים לזהות אנשים ספציפיים)
        self.face_database = {}
        
        # טקסטים בריבוי שפות
        self.text_labels = {
            "en": {
                "person_detected": "Person Detected",
                "face_detection": "Face Detection"
            },
            "he": {
                "person_detected": "זוהה אדם",
                "face_detection": "זיהוי פנים"
            }
        }
        
        # מונה תמונות (למטרות דיבוג)
        self.frame_counter = 0
    
    def get_frame(self):
        """קבלת תמונה נוכחית מהמצלמה
        Returns:
            numpy.ndarray or None: מערך תמונה או None אם המצלמה לא זמינה
        """
        if self.cap is None or not self.cap.isOpened():
            return None
        
        ret, frame = self.cap.read()
        if not ret:
            return None
        
        # הגדלת מונה תמונות
        self.frame_counter += 1
        
        return frame
    
    def detect_faces(self, frame):
        """זיהוי פנים בתמונה
        Args:
            frame (numpy.ndarray): תמונה לניתוח
        Returns:
            list: רשימת מלבנים המייצגים פנים שזוהו [(x, y, w, h), ...]
        """
        if frame is None or self.face_cascade is None:
            return []
        
        # שינוי גודל לביצועים טובים יותר
        small_frame = cv2.resize(frame, (0, 0), fx=self.face_detection_scale, fy=self.face_detection_scale)
        
        # המרה לתמונת שחור-לבן לזיהוי טוב יותר
        gray = cv2.cvtColor(small_frame, cv2.COLOR_BGR2GRAY)
        
        # איתור פנים בתמונה
        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(30, 30)
        )
        
        # ציור מלבן סביב הפנים אם הוידאו מוצג
        if self.show_video and len(faces) > 0:
            # טקסט להצגה
            text = self.text_labels.get(self.language, self.text_labels["en"])
            
            for (x, y, w, h) in faces:
                # התאמת הגדלים לתמונה המקורית
                x = int(x / self.face_detection_scale)
                y = int(y / self.face_detection_scale)
                w = int(w / self.face_detection_scale)
                h = int(h / self.face_detection_scale)
                
                # ציור מלבן סביב הפנים
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                
                # הוספת טקסט "אדם זוהה" בשפה המתאימה
                cv2.putText(frame, text["person_detected"], (x, y-10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        return faces
    
    def recognize_face(self, frame, face_rect):
        """ניסיון לזהות פנים ספציפיות (למטרות עתידיות)
        Args:
            frame (numpy.ndarray): התמונה המלאה
            face_rect (tuple): מלבן המייצג את הפנים (x, y, w, h)
        Returns:
            str or None: שם האדם אם זוהה, אחרת None
        """
        # פונקציית קוד עמדת כרגע, יש להוסיף כאן קוד לזיהוי פנים ספציפיות
        # למשל באמצעות face_recognition או dlib
        return None
    
    def save_face(self, frame, face_rect, name):
        """שמירת פנים למאגר לשימוש עתידי
        Args:
            frame (numpy.ndarray): התמונה המלאה
            face_rect (tuple): מלבן המייצג את הפנים (x, y, w, h)
            name (str): שם האדם לשמירה
        Returns:
            bool: האם השמירה הצליחה
        """
        if frame is None or face_rect is None:
            return False
        
        try:
            x, y, w, h = face_rect
            face_img = frame[y:y+h, x:x+w]
            
            # כאן אפשר לבצע עיבוד נוסף כמו שינוי גודל, נרמול וכדומה
            
            self.face_database[name] = face_img
            print(f"Saved face for {name}")
            return True
        except Exception as e:
            print(f"Error saving face: {e}")
            return False
    
    def set_language(self, language_code):
        """הגדרת שפה למודול
        
        Args:
            language_code (str): קוד השפה ('en', 'he')
        """
        if language_code in self.text_labels:
            self.language = language_code
            print(f"Face detection language set to {language_code}")
    
    def continuous_detection(self, callback=None):
        """ביצוע זיהוי פנים רציף בתהליך נפרד
        Args:
            callback (function): פונקציה שתופעל כאשר מזוהות פנים
                                צריכה לקבל פרמטר אחד (רשימת מלבנים)
        """
        if self.cap is None or not self.cap.isOpened():
            print("Camera not available for continuous detection")
            return False
        
        def detection_thread():
            # טקסט להצגה
            text = self.text_labels.get(self.language, self.text_labels["en"])
            
            print("Starting continuous face detection")
            while self.running:
                frame = self.get_frame()
                if frame is not None:
                    faces = self.detect_faces(frame)
                    
                    # בדיקה אם זוהו פנים חדשות
                    if len(faces) > 0 and not self.face_detected:
                        self.face_detected = True
                        if callback:
                            callback(faces)
                    elif len(faces) == 0 and self.face_detected:
                        self.face_detected = False
                    
                    # הצגת התמונה אם מוגדר להציג
                    if self.show_video:
                        # הוספת כותרת בשפה המתאימה
                        cv2.putText(frame, text["face_detection"], (10, 30), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                        
                        cv2.imshow('Face Detection', frame)
                        if cv2.waitKey(1) & 0xFF == ord('q'):
                            break
                
                # השהייה קצרה
                time.sleep(0.03)  # כ-30 תמונות בשנייה
            
            # סגירת החלון
            cv2.destroyAllWindows()
            print("Continuous face detection stopped")
        
        # הפעלת התהליך
        self.running = True
        thread = threading.Thread(target=detection_thread)
        thread.daemon = True
        thread.start()
        return True
    
    def stop_detection(self):
        """עצירת זיהוי פנים רציף"""
        self.running = False
        
        # סגירת חלונות
        cv2.destroyAllWindows()
    
    def close(self):
        """שחרור משאבים ותצוגה"""
        self.stop_detection()
        
        if self.cap and self.cap.isOpened():
            self.cap.release()
            print("Camera released")

# מבחן למודול אם מריצים אותו ישירות
if __name__ == "__main__":
    # טעינת קונפיגורציה למבחן
    config = {
        'camera_index': 0,
        'face_detection_scale': 0.5,
        'show_video': True
    }
    
    # בחירת שפה
    print("Choose language (en/he):")
    lang = input("Enter language code (default: en): ") or "en"
    config['language'] = lang
    
    # יצירת אובייקט זיהוי פנים
    face_detector = GonzoFace(config)
    
    # פונקציית קולבק לזיהוי פנים
    def on_face_detected(faces):
        print(f"Face detected! Found {len(faces)} face(s)")
    
    # הפעלת זיהוי רציף
    try:
        print("Starting face detection, press 'q' in the video window or Ctrl+C to exit.")
        face_detector.continuous_detection(callback=on_face_detected)
        
        # השארת התוכנית רצה
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        face_detector.close()
        print("Test completed")