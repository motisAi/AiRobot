import os
import time
import threading
import yaml
import random
import cv2
import numpy as np
import face_recognition
import pickle
from datetime import datetime

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
        self.language = self.config.get('language', 'en')
        
        # הגדרות מאגר פנים
        self.face_database_file = 'known_faces.pkl'
        self.faces_dir = 'face_images'
        self.known_face_encodings = []
        self.known_face_names = []
        
        # יצירת תיקיות נדרשות
        if not os.path.exists(self.faces_dir):
            os.makedirs(self.faces_dir)
        
        # טעינת מאגר פנים
        self.load_face_database()
        
        # איתחול מודולים
        self.initialize_modules()
        
        # דגלים ומשתנים
        self.running = True
        self.command_mode = False
        
        # מצב זיהוי פנים
        self.asking_for_name = False
        self.unknown_face_data = None
        self.last_greeting_time = {}
        self.greeting_interval = 60  # שנייה בין ברכות לאותו אדם
        
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
    
    def load_face_database(self):
        """טעינת מאגר פנים קיים"""
        if os.path.exists(self.face_database_file):
            print(f"Loading face database from {self.face_database_file}")
            with open(self.face_database_file, "rb") as f:
                data = pickle.load(f)
                self.known_face_encodings = data.get("encodings", [])
                self.known_face_names = data.get("names", [])
            print(f"Loaded {len(self.known_face_names)} faces from database")
        else:
            print("No existing face database found. Creating new database.")
            self.known_face_encodings = []
            self.known_face_names = []
    
    def save_face_database(self):
        """שמירת מאגר פנים"""
        print(f"Saving {len(self.known_face_names)} faces to database")
        with open(self.face_database_file, "wb") as f:
            pickle.dump({
                "encodings": self.known_face_encodings,
                "names": self.known_face_names
            }, f)
        print("Face database saved successfully")
    
    def add_new_face_to_database(self, frame, name):
        """הוספת פנים חדשות למאגר"""
        # המרה ל-RGB עבור face_recognition
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # איתור פנים בתמונה
        face_locations = face_recognition.face_locations(rgb_frame)
        
        if not face_locations:
            return False, "No faces found in the image"
        
        # אם יש כמה פנים, לקחת את הגדולות ביותר
        if len(face_locations) > 1:
            face_areas = [(right - left) * (bottom - top) for (top, right, bottom, left) in face_locations]
            largest_face_idx = face_areas.index(max(face_areas))
            face_locations = [face_locations[largest_face_idx]]
        
        # יצירת encoding לפנים - חשוב! השתמש ב-rgb_frame
        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
        
        if not face_encodings:
            return False, "Failed to encode face"
        
        face_encoding = face_encodings[0]
        
        # בדיקה אם הפנים כבר קיימות במאגר
        if self.known_face_encodings:
            matches = face_recognition.compare_faces(self.known_face_encodings, face_encoding)
            if True in matches:
                match_index = matches.index(True)
                existing_name = self.known_face_names[match_index]
                
                if existing_name == name:
                    return False, f"{name} is already in the database"
                else:
                    return False, f"This face is already in the database as {existing_name}"
        
        # הוספת הפנים למאגר
        self.known_face_encodings.append(face_encoding)
        self.known_face_names.append(name)
        
        # שמירת תמונה של הפנים
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        face_img_path = os.path.join(self.faces_dir, f"{name}_{timestamp}.jpg")
        
        # חילוץ אזור הפנים ושמירה - השתמש בתמונה המקורית BGR
        (top, right, bottom, left) = face_locations[0]
        face_img = frame[top:bottom, left:right]
        cv2.imwrite(face_img_path, face_img)
        
        # שמירת המאגר המעודכן
        self.save_face_database()
        
        return True, f"Added {name} to the database"
    
    def identify_faces_in_frame(self, frame):
        """זיהוי פנים בתמונה"""
        if not self.known_face_encodings:
            return [], []
        
        # המרה ל-RGB עבור face_recognition
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # איתור פנים בתמונה
        face_locations = face_recognition.face_locations(rgb_frame)
        
        if not face_locations:
            return [], []
        
        # יצירת encodings לפנים שנמצאו - חשוב! השתמש ב-rgb_frame
        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
        
        face_names = []
        for face_encoding in face_encodings:
            # השוואה עם פנים ידועות
            matches = face_recognition.compare_faces(self.known_face_encodings, face_encoding, tolerance=0.6)
            name = "Unknown"
            
            # אם נמצאה התאמה
            if True in matches:
                match_index = matches.index(True)
                name = self.known_face_names[match_index]
            else:
                # שימוש במרחק הקטן ביותר
                face_distances = face_recognition.face_distance(self.known_face_encodings, face_encoding)
                if len(face_distances) > 0:
                    best_match_index = np.argmin(face_distances)
                    if face_distances[best_match_index] < 0.7:
                        name = self.known_face_names[best_match_index]
            
            face_names.append(name)
        
        return face_locations, face_names
    
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
        """קבלת טקסט תגובה לפי מפתח בשפה הנוכחית"""
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
    
    def process_face_interaction(self, frame, face_locations, face_names):
        """עיבוד אינטראקציה של זיהוי פנים"""
        current_time = time.time()
        
        for (top, right, bottom, left), name in zip(face_locations, face_names):
            print(f"Processing face: {name} at location ({left}, {top}, {right}, {bottom})")
            
            if name != "Unknown":
                # אדם מוכר - בדיקה אם לא בירכנו לאחרונה
                if name not in self.last_greeting_time or (current_time - self.last_greeting_time[name]) > self.greeting_interval:
                    greeting_hour = datetime.now().hour
                    
                    if greeting_hour >= 5 and greeting_hour < 12:
                        greeting = f"Good morning {name}, nice to see you again"
                    elif greeting_hour >= 12 and greeting_hour < 18:
                        greeting = f"Good afternoon {name}, nice to see you again"
                    elif greeting_hour >= 18 and greeting_hour < 22:
                        greeting = f"Good evening {name}, nice to see you again"
                    else:
                        greeting = f"Good night {name}, nice to see you again"
                    
                    print(f"Greeting known person: {greeting}")
                    self.tts.speak(greeting)
                    self.last_greeting_time[name] = current_time
                    
            elif not self.asking_for_name:
                # אדם לא מוכר - שאלה לשם
                print("Unknown person detected - asking for name")
                self.unknown_face_data = {
                    'location': (top, right, bottom, left),
                    'frame': frame.copy()
                }
                
                self.asking_for_name = True
                self.tts.speak("I see a new face, what is your name please?")
                
                # שימוש במיקרופון B לקבלת תשובה
                print("Waiting for name response...")
                name_response = self.stt.listen_for_face_interaction()
                
                if name_response:
                    print(f"Person said their name is: {name_response}")
                    
                    # הוספת הפנים למאגר
                    success, message = self.add_new_face_to_database(
                        self.unknown_face_data['frame'], 
                        name_response
                    )
                    
                    print(f"Add face result: {success}, {message}")
                    
                    if success:
                        self.tts.speak(f"Thank you {name_response}, I'll remember you")
                        # עדכון רשימת הפנים הידועות
                        self.last_greeting_time[name_response] = current_time
                    else:
                        self.tts.speak(message)
                else:
                    print("No name response received")
                    self.tts.speak("I didn't catch your name, but nice to meet you anyway")
                
                # איפוס משתני האינטראקציה
                self.asking_for_name = False
                self.unknown_face_data = None
                print("Face interaction completed")
    
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
        
        frame_count = 0
        
        try:
            # לולאה ראשית
            while self.running:
                face_locations = []
                face_names = []
                # אם מודול זיהוי פנים פעיל, הפעל אותו
                if self.face:
                    frame = self.face.get_frame()
                    if frame is not None:
                        # עיבוד כל התמונה השלישית כדי לחסוך במעבד
                        frame_count += 1
                        process_this_frame = (frame_count % 3 == 0)
                        
                        if process_this_frame and not self.asking_for_name:
                            # זיהוי פנים בתמונה באמצעות face_recognition
                            face_locations, face_names = self.identify_faces_in_frame(frame)
                            
                            if face_locations:
                                # עיבוד אינטראקציית זיהוי פנים
                                self.process_face_interaction(frame, face_locations, face_names)
                            
                        # ציור מסגרות סביב פנים (אם מוצג וידאו)
                        if self.config.get('show_video', False): #and face_locations:
                            for (top, right, bottom, left), name in zip(face_locations, face_names):
                                # ציור מלבן סביב הפנים
                                cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
                                
                                # ציור מלבן מלא מתחת לפנים עבור השם
                                cv2.rectangle(frame, (left, bottom - 35), (right, bottom), (0, 255, 0), cv2.FILLED)
                                
                                # ציור הטקסט של השם
                                cv2.putText(frame, name, (left + 6, bottom - 6), cv2.FONT_HERSHEY_DUPLEX, 
                                           0.8, (255, 255, 255), 1)
                        
                        # הצגת הוידאו אם מוגדר
                        if self.config.get('show_video', False):
                            if self.asking_for_name:
                                cv2.putText(frame, "Please say your name", (10, 30), 
                                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                            
                            cv2.imshow('Gonzo Vision', frame)
                            if cv2.waitKey(1) & 0xFF == ord('q'):
                                break
                
                # שינה קצרה כדי לא להעמיס על המעבד
                time.sleep(0.1)
        
        except KeyboardInterrupt:
            print("\nStopping Gonzo AI...")
        finally:
            self.cleanup()
    
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
