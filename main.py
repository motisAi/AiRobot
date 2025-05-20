# קובץ Main.py המעודכן עם שני מיקרופונים ותמיכה מקומית
import os
import time
import threading
import yaml
import random
import cv2

# ייבוא מודולים מקומיים
from gonzo_stt import GonzoSTT
from gonzo_tts import GonzoTTS
from gonzo_face import GonzoFace
from gonzo_serial import GonzoSerial

class GonzoAI:
    def __init__(self, config_file="config.yaml"):
        # טעינת קונפיגורציה
        self.config = self.load_config(config_file)
        
        # איתחול מודולים
        self.initialize_modules()
        
        # דגלים ומשתנים
        self.running = True
        self.command_mode = False
        
        # פקודות זמינות
        self.available_commands = {
            "light on": self.turn_light_on,
            "turn on the light": self.turn_light_on,
            "light off": self.turn_light_off,
            "turn off the light": self.turn_light_off,
            "hello": self.say_hello,
            "who are you": self.introduce_yourself,
            "stop": self.stop_system,
            "goodbye": self.stop_system
        }
    
    def load_config(self, config_file):
        """טעינת הגדרות מקובץ קונפיגורציה"""
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                return yaml.safe_load(f)
        else:
            print(f"Warning: Config file {config_file} not found. Using default settings.")
            return {}
    
    def initialize_modules(self):
        """איתחול כל המודולים"""
        # מודול זיהוי דיבור
        self.stt = GonzoSTT(self.config)
        self.stt.on_wake_word_detected = self.on_wake_word
        
        # מודול המרת טקסט לדיבור
        self.tts = GonzoTTS(self.config)
        
        # מודול זיהוי פנים (אם מוגדר בקונפיגורציה)
        use_face_detection = self.config.get('use_face_detection', False)
        self.face = None
        if use_face_detection:
            try:
                self.face = GonzoFace(self.config)
                print("Face detection module initialized")
            except Exception as e:
                print(f"Error initializing face detection: {e}")
        
        # מודול תקשורת סיריאלית (אם מוגדר בקונפיגורציה)
        use_serial = self.config.get('use_serial', False)
        self.serial = None
        if use_serial:
            try:
                self.serial = GonzoSerial(self.config)
                print("Serial communication module initialized")
            except Exception as e:
                print(f"Error initializing serial module: {e}")
    
    def on_wake_word(self, response):
        """מטפל בזיהוי מילת ההפעלה"""
        print(f"Wake word detected, responding with: {response}")
        
        # השמעת תגובה
        self.tts.speak(response)
        
        # האזנה לפקודה
        print("Listening for command...")
        command = self.stt.recognize_command()
        
        if command:
            self.process_command(command)
        else:
            self.tts.speak("לא הבנתי את הפקודה, אנא נסה שוב.")
    
    def process_command(self, command_text):
        """עיבוד פקודה קולית"""
        print(f"Processing command: {command_text}")
        
        # בדיקה אם הפקודה מוכרת
        command_found = False
        for key, func in self.available_commands.items():
            if key in command_text.lower():
                func()
                command_found = True
                break
        
        # אם הפקודה לא מוכרת
        if not command_found:
            # שליחה לסיריאל אם הוגדר
            if self.serial:
                self.serial.send_command(command_text)
                self.tts.speak(f"שולח פקודה: {command_text}")
            else:
                self.tts.speak("מצטער, אני לא מכיר את הפקודה הזו.")
    
    def turn_light_on(self):
        """הדלקת אור"""
        if self.serial:
            self.serial.send_command("LIGHT_ON")
        self.tts.speak("מדליק את האור.")
    
    def turn_light_off(self):
        """כיבוי אור"""
        if self.serial:
            self.serial.send_command("LIGHT_OFF")
        self.tts.speak("מכבה את האור.")
    
    def say_hello(self):
        """אמירת שלום"""
        greetings = [
            "שלום לך!",
            "היי, נעים להכיר.",
            "שלום, איך אני יכול לעזור?",
            "ברוך הבא, אני גונזו."
        ]
        self.tts.speak(random.choice(greetings))
    
    def introduce_yourself(self):
        """הצגה עצמית"""
        intro = "שמי גונזו, אני מערכת בינה מלאכותית שנועדה לסייע לך. אני יכול להפעיל מכשירים, לזהות פנים, ולענות על שאלות."
        self.tts.speak(intro)
    
    def stop_system(self):
        """עצירת המערכת"""
        self.tts.speak("מכבה את המערכת. להתראות!")
        self.running = False
    
    def start(self):
        """התחלת פעולת המערכת"""
        # התחלת האזנה למילת הפעלה
        self.stt.start_listening()
        
        # התחלת לולאה ראשית
        print("Gonzo AI system is running. Say 'gonzo' to activate.")
        self.tts.speak("מערכת גונזו מוכנה. אמור 'גונזו' כדי להפעיל אותי.")
        
        try:
            # לולאה ראשית
            while self.running:
                # אם מודול זיהוי פנים פעיל, הפעל אותו
                if self.face:
                    frame = self.face.get_frame()
                    if frame is not None:
                        # עיבוד התמונה
                        faces = self.face.detect_faces(frame)
                        if faces and not self.face.face_detected:
                            # זוהו פנים חדשות
                            self.face.face_detected = True
                            self.on_face_detected()
                        elif not faces and self.face.face_detected:
                            # הפנים נעלמו
                            self.face.face_detected = False
                        
                        # הצגת התמונה בחלון (אופציונלי)
                        if self.config.get('show_video', False):
                            cv2.imshow('Gonzo Vision', frame)
                            if cv2.waitKey(1) & 0xFF == ord('q'):
                                break
                
                # שינה קצרה כדי לא להעמיס על המעבד
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            print("\nStopping Gonzo AI...")
        finally:
            self.cleanup()
    
    def on_face_detected(self):
        """מגיב כאשר מזוהות פנים חדשות"""
        if self.config.get('greet_on_face_detection', False):
            self.tts.speak("שלום! זיהיתי אותך.", block=False)
    
    def cleanup(self):
        """ניקוי משאבים בסיום"""
        # עצירת האזנה
        if hasattr(self, 'stt'):
            self.stt.stop_listening()
        
        # סגירת מצלמה
        if self.face and hasattr(self.face, 'cap') and self.face.cap:
            self.face.cap.release()
        
        # סגירת חלונות
        cv2.destroyAllWindows()
        
        # סגירת חיבור סיריאלי
        if self.serial:
            self.serial.close()
        
        print("Gonzo AI system stopped.")

# הפעלת המערכת כאשר התסריט רץ ישירות
if __name__ == "__main__":
    gonzo = GonzoAI()
    gonzo.start()
