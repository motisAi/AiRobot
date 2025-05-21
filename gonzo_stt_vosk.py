# מודול זיהוי דיבור מקומי עם Vosk
import os
import json
import queue
import threading
import numpy as np
import sounddevice as sd
from vosk import Model, KaldiRecognizer
import time
import random

class GonzoSTT:
    def __init__(self, config=None):
        # קונפיגורציה בסיסית
        self.sample_rate = 16000
        self.device_index_listening = 0  # מיקרופון להאזנה קבועה
        self.device_index_command = 0    # מיקרופון לפקודות
        self.wake_word = "gonzo"
        self.block_size = 8000
        self.running = True
        self.is_listening = False
        self.command_mode = False
        self.language = "en"  # ברירת מחדל: אנגלית
        
        # נתיבים למודלים לפי שפה
        self.model_paths = {
            "en": "models/vosk-model-en",  # מודל אנגלית
            "he": "models/vosk-model-he"   # מודל עברית
        }
        
        # תורים לנתוני שמע
        self.listening_queue = queue.Queue()
        self.command_queue = queue.Queue()
        
        # טעינת קונפיגורציה אם קיימת
        if config:
            if 'wake_word' in config:
                self.wake_word = config.get('wake_word', "gonzo")
            if 'device_index_listening' in config:
                self.device_index_listening = config.get('device_index_listening', 0)
            if 'device_index_command' in config:
                self.device_index_command = config.get('device_index_command', 0)
            if 'model_path' in config:
                # אם מסופק נתיב ספציפי, נשתמש בו
                self.model_paths["custom"] = config['model_path']
            if 'language' in config:
                self.language = config.get('language', "en")
        
        # בחירת מודל לפי שפה
        selected_model_path = self.model_paths.get(self.language, self.model_paths.get("custom", self.model_paths["en"]))
        
        # טעינת מודל Vosk
        if os.path.exists(selected_model_path):
            self.model = Model(selected_model_path)
            print(f"Loaded Vosk model from {selected_model_path}")
        else:
            print(f"Warning: Model path {selected_model_path} not found. Please download a Vosk model.")
            
            # שימוש במודל קטן כברירת מחדל אם הוא קיים במערכת
            system_model = "/usr/share/vosk"
            if os.path.exists(system_model):
                self.model = Model(system_model)
                print(f"Using system model from {system_model}")
            else:
                raise FileNotFoundError(f"No Vosk model found. Please download a model to {selected_model_path}")
        
        # יצירת מזהי קול
        self.wake_recognizer = KaldiRecognizer(self.model, self.sample_rate)
        self.command_recognizer = KaldiRecognizer(self.model, self.sample_rate)
        
        # משפטי תגובה לזיהוי מילת ההפעלה
        self.wake_responses = {
            "en": [
                "Yes, how can I help you?",
                "I'm here, how can I assist you?",
                "I'm listening, what would you like?",
                "Gonzo at your service, what's your request?", 
                "Here I am, how can I help today?"
            ],
            "he": [
                "כן, איך אני יכול לעזור?",
                "אני כאן, במה אוכל לסייע לך?",
                "שומע אותך, מה תרצה?",
                "גונזו לשירותך, מה הבקשה שלך?",
                "הנה אני, איך אוכל לעזור היום?"
            ]
        }
        
        # אם יש תגובות בקובץ הקונפיגורציה, נשתמש בהן
        if config and 'responses' in config and 'wake_responses' in config['responses']:
            self.wake_responses = config['responses']['wake_responses']
    
    def listening_callback(self, indata, frames, time, status):
        """פונקציית קולבק להאזנה למילת ההפעלה"""
        if status:
            print(f"Error in listening mic: {status}")
        self.listening_queue.put(bytes(indata))
    
    def command_callback(self, indata, frames, time, status):
        """פונקציית קולבק להאזנה לפקודות"""
        if status:
            print(f"Error in command mic: {status}")
        self.command_queue.put(bytes(indata))
    
    def listen_for_wake_word(self):
        """האזנה רציפה למילת ההפעלה"""
        try:
            with sd.RawInputStream(samplerate=self.sample_rate, blocksize=self.block_size, 
                                  device=self.device_index_listening, dtype="int16", 
                                  channels=1, callback=self.listening_callback):
                
                print(f"Listening for wake word '{self.wake_word}'...")
                
                while self.running:
                    data = self.listening_queue.get()
                    if self.wake_recognizer.AcceptWaveform(data):
                        result = json.loads(self.wake_recognizer.Result())
                        text = result.get("text", "").lower()
                        
                        if self.wake_word in text:
                            print(f"Wake word detected: {text}")
                            
                            # בחירת תגובה אקראית לפי השפה
                            responses = self.wake_responses.get(self.language, self.wake_responses["en"])
                            response = random.choice(responses)
                            print(f"Response: {response}")
                            
                            # כאן נחזיר את התגובה למודול הראשי
                            self.on_wake_word_detected(response)
        except Exception as e:
            print(f"Error in wake word detection: {e}")
    
    def listen_for_commands(self):
        """האזנה לפקודות לאחר זיהוי מילת ההפעלה"""
        try:
            with sd.RawInputStream(samplerate=self.sample_rate, blocksize=self.block_size, 
                                  device=self.device_index_command, dtype="int16", 
                                  channels=1, callback=self.command_callback):
                
                print("Listening for commands...")
                command_timeout = time.time() + 10  # 10 שניות לקבלת פקודה
                
                while self.running and time.time() < command_timeout:
                    try:
                        data = self.command_queue.get(timeout=1)
                        if self.command_recognizer.AcceptWaveform(data):
                            result = json.loads(self.command_recognizer.Result())
                            command_text = result.get("text", "").lower()
                            
                            if command_text:
                                print(f"Command detected: {command_text}")
                                return command_text
                    except queue.Empty:
                        # טיימאאוט בתור - זה בסדר, ממשיכים
                        pass
                
                # אם הגענו לכאן, חלף זמן ההמתנה ללא פקודה
                print("Command timeout reached")
                return None
                
        except Exception as e:
            print(f"Error in command detection: {e}")
            return None
    
    def on_wake_word_detected(self, response):
        """פונקציה שתופעל כאשר מזוהה מילת ההפעלה"""
        # פונקציה זו תוחלף על-ידי המודול הראשי
        pass
    
    def start_listening(self):
        """התחלת האזנה בתהליך נפרד"""
        self.running = True
        self.listening_thread = threading.Thread(target=self.listen_for_wake_word)
        self.listening_thread.daemon = True
        self.listening_thread.start()
    
    def stop_listening(self):
        """עצירת האזנה"""
        self.running = False
        if hasattr(self, 'listening_thread') and self.listening_thread.is_alive():
            self.listening_thread.join(timeout=2)
    
    def recognize_command(self, timeout=10):
        """האזנה לפקודה ספציפית עם הגבלת זמן"""
        return self.listen_for_commands()
    
    def list_audio_devices(self):
        """הצגת רשימת התקני שמע זמינים"""
        devices = sd.query_devices()
        input_devices = []
        
        print("\nAvailable audio input devices:")
        for i, device in enumerate(devices):
            if device['max_input_channels'] > 0:
                print(f"Index {i}: {device['name']}")
                input_devices.append((i, device['name']))
        
        return input_devices
    
    def set_language(self, language_code):
        """שינוי שפת המערכת
        
        Args:
            language_code (str): קוד השפה ('en', 'he')
            
        Returns:
            bool: האם השינוי הצליח
        """
        if language_code in self.model_paths:
            self.language = language_code
            
            # לשקול טעינה מחדש של המודל אם השפה השתנתה
            # זה דורש אתחול מחדש של המזהים
