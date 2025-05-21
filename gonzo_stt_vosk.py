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
        self.model_path = "models/vosk-model-en"  # נתיב למודל Vosk
        
        # תורים לנתוני שמע
        self.listening_queue = queue.Queue()
        self.command_queue = queue.Queue()
        
        # טעינת קונפיגורציה אם קיימת
        if config:
            if 'wake_word' in config:
                self.wake_word = config['wake_word']
            if 'device_index_listening' in config:
                self.device_index_listening = config['device_index_listening']
            if 'device_index_command' in config:
                self.device_index_command = config['device_index_command']
            if 'model_path' in config:
                self.model_path = config['model_path']
        
        # טעינת מודל Vosk
        if os.path.exists(self.model_path):
            self.model = Model(self.model_path)
            print(f"Loaded Vosk model from {self.model_path}")
        else:
            print(f"Warning: Model path {self.model_path} not found. Please download a Vosk model.")
            # שימוש במודל קטן כברירת מחדל אם הוא קיים במערכת
            system_model = "/usr/share/vosk"
            if os.path.exists(system_model):
                self.model = Model(system_model)
                print(f"Using system model from {system_model}")
            else:
                raise FileNotFoundError(f"No Vosk model found. Please download a model to {self.model_path}")
        
        # יצירת מזהי קול
        self.wake_recognizer = KaldiRecognizer(self.model, self.sample_rate)
        self.command_recognizer = KaldiRecognizer(self.model, self.sample_rate)
        
        # משפטי תגובה לזיהוי מילת ההפעלה
        self.wake_responses = [
            "כן, איך אני יכול לעזור?",
            "אני כאן, במה אוכל לסייע לך?",
            "שומע אותך, מה תרצה?",
            "גונזו לשירותך, מה הבקשה שלך?",
            "הנה אני, איך אוכל לעזור היום?"
        ]
    
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
                            # בחירת תגובה אקראית
                            response = random.choice(self.wake_responses)
                            print(f"Response: {response}")
                            
                            # כאן נחזיר את התגובה למודול הראשי
                            self.on_wake_word_detected(response)
                            
                            # מעבר למצב פקודה - אם רוצים להשתמש באותו מיקרופון
                            # אם משתמשים במיקרופון נפרד, הפונקציה listen_for_commands
                            # צריכה לרוץ במקביל בתהליך נפרד
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
                    data = self.command_queue.get(timeout=1)
                    if self.command_recognizer.AcceptWaveform(data):
                        result = json.loads(self.command_recognizer.Result())
                        command_text = result.get("text", "").lower()
                        
                        if command_text:
                            print(f"Command detected: {command_text}")
                            return command_text
                
                # אם הגענו לכאן, חלף זמן ההמתנה ללא פקודה
                print("Command timeout reached")
                return None
        except queue.Empty:
            # טיימאאוט בתור - זה בסדר, ממשיכים
            pass
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

# מבחן למודול אם מריצים אותו ישירות
if __name__ == "__main__":
    # יצירת אובייקט עם הגדרות ברירת מחדל
    stt = GonzoSTT()
    
    # הצגת התקני שמע זמינים
    input_devices = stt.list_audio_devices()
    
    # בחירת התקן
    if input_devices:
        print("\nChoose microphone for wake word detection (default: 0):")
        try:
            device_index = int(input("Enter device index: ") or "0")
            stt.device_index_listening = device_index
            stt.device_index_command = device_index  # שימוש באותו מיקרופון לפשטות
        except ValueError:
            print("Invalid input, using default device 0")
    
    # הגדרת פונקציית קולבק
    def on_wake(response):
        print(f"\nWake word detected! Responding with: {response}")
        print("Listening for command...")
        command = stt.recognize_command()
        if command:
            print(f"Command received: {command}")
            # כאן אפשר להוסיף לוגיקה למה לעשות עם הפקודה
            if "light" in command and "on" in command:
                print("Action: Turning on the light")
            elif "light" in command and "off" in command:
                print("Action: Turning off the light")
        else:
            print("No command received or not understood")
    
    # הגדרת פונקציית הקולבק
    stt.on_wake_word_detected = on_wake
    
    # התחלת האזנה
    try:
        print("\nStarting wake word detection. Say 'gonzo' to activate...")
        stt.start_listening()
        
        # השארת התוכנית רצה
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        stt.stop_listening()
        print("Stopped")
