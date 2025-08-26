# קובץ Main.py המעודכן עם תמיכה מרובת שפות
import os
import time
import threading
import yaml
import random
import cv2

# ייבוא מודולים מקומיים
from gonzo_stt_vosk import GonzoSTT
from gonzo_tts import GonzoTTS
from gonzo_face import GonzoFace
from gonzo_serial import GonzoSerial

class GonzoAI:
    def __init__(self, config_file="config.yaml"):
        # טעינת קונפיגורציה
        self.config = self.load_config(config_file)
        
        # הגדרת שפה מועדפת
        self.language = self.config.get('language', 'en')  # ברירת מחדל: אנגלית
        
        # איתחול מודולים
        self.initialize_modules()
        
        # דגלים ומשתנים
        self.running = True
        self.command_mode = False
        
        # פקודות זמינות
        self.initialize_commands()
    
    def load_config(self, config_file):
        """טעינת הגדרות מקובץ קונפיגורציה"""
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
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
    
    def initialize_commands(self):
        """אתחול המילון של הפקודות הזמינות על פי השפה"""
        # מילון פקודות באנגלית
        self.en_commands = {
            "light on": self.turn_light_on,
            "turn on the light": self.turn_light_on,
            "lights on": self.turn_light_on,
            "light off": self.turn_light_off,
            "turn off the light": self.turn_light_off,
            "lights off": self.turn_light_off,
            "hello": self.say_hello,
            "hi": self.say_hello,
            "who are you": self.introduce_yourself,
            "introduce yourself": self.introduce_yourself,
            "what can you do": self.introduce_yourself,
            "stop": self.stop_system,
            "shutdown": self.stop_system,
            "goodbye": self.stop_system,
            "exit": self.stop_system
        }
        
        # מילון פקודות בעברית
        self.he_commands = {
            "הדלק אור": self.turn_light_on,
            "תדליק את האור": self.turn_light_on,
            "אור": self.turn_light_on,
            "כבה אור": self.turn_light_off,
            "תכבה את האור": self.turn_light_off,
            "שלום": self.say_hello,
            "היי": self.say_hello,
            "מי אתה": self.introduce_yourself,
            "תציג את עצמך": self.introduce_yourself,
            "מה אתה יודע לעשות": self.introduce_yourself,
            "עצור": self.stop_system,
            "כבה": self.stop_system,
            "להתראות": self.stop_system,
            "ביי": self.stop_system,
            "צא": self.stop_system
        }
        
        # בחירת מילון פקודות לפי שפה
        self.available_commands = self.en_commands if self.language == 'en' else self.he_commands
    
    def get_response_text(self, key, default=None):
        """קבלת טקסט תגובה לפי מפתח בשפה הנוכחית
        
        Args:
            key (str): מפתח התגובה בקובץ הקונפיגורציה
            default (str): ערך ברירת מחדל אם המפתח לא נמצא
            
        Returns:
            str: טקסט התגובה
        """
        try:
            responses = self.config.get('responses', {})
            if key in responses:
                if isinstance(responses[key], dict):
                    # אם יש מילון תגובות לפי שפה
                    if self.language in responses[key]:
                        response = responses[key][self.language]
                        if isinstance(response, list):
                            return random.choice(response)
                        return response
                return responses[key]
        except Exception as e:
            print(f"Error getting response text: {e}")
        
        return default
    
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
            # הודעת שגיאה כאשר לא מזוהה פקודה
            error_msg = self.get_response_text('command_not_understood', 
                                               "I didn't understand that command, please try again.")
            self.tts.speak(error_msg)
    
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
                self.tts.speak(f"שולח פקודה: {command_text}" if self.language == 'he' else f"Sending command: {command_text}")
            else:
                error_msg = self.get_response_text('command_not_understood', 
                                                  "I didn't understand that command, please try again.")
                self.tts.speak(error_msg)
    
    def turn_light_on(self):
        """הדלקת אור"""
        if self.serial:
            self.serial.send_command("LIGHT_ON")
        
        response = self.get_response_text('light_on', "Turning on the light.")
        self.tts.speak(response)
    
    def turn_light_off(self):
        """כיבוי אור"""
        if self.serial:
            self.serial.send_command("LIGHT_OFF")
        
        response = self.get_response_text('light_off', "Turning off the light.")
        self.tts.speak(response)
    
    def say_hello(self):
        """אמירת שלום"""
        greetings = self.get_response_text('greetings', ["Hello there!"])
        if not isinstance(greetings, list):
            greetings = [greetings]
        
        self.tts.speak(random.choice(greetings))
    
    def introduce_yourself(self):
        """הצגה עצמית"""
        intro = self.get_response_text('introduction', 
                                      "My name is Gonzo, I'm an AI system designed to assist you.")
        self.tts.speak(intro)
    
    def stop_system(self):
        """עצירת המערכת"""
        response = self.get_response_text('system_shutdown', "Shutting down the system. Goodbye!")
        self.tts.speak(response)
        self.running = False
    
    def start(self):
        """התחלת פעולת המערכת"""
        # התחלת האזנה למילת הפעלה
        self.stt.start_listening()
        
        # התחלת לולאה ראשית
        print(f"Gonzo AI system is running. Say '{self.config.get('wake_word', 'gonzo')}' to activate.")
        
        # הודעת פתיחה בשפה הנבחרת
        ready_message = self.get_response_text('system_ready', 
                                              "Gonzo AI system is ready. Say 'gonzo' to activate me.")
        self.tts.speak(ready_message)
        
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
            response = self.get_response_text('face_detected', "Hello! I've detected you.")
            self.tts.speak(response, block=False)
    
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
