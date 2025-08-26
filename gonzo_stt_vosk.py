# מודול זיהוי דיבור מקומי עם Vosk - גרסה עם מנגנון pause/resume
import os
import json
import queue
import threading
import numpy as np
import sounddevice as sd
from vosk import Model, KaldiRecognizer
import time
import random
from scipy import signal

class GonzoSTT:
    def __init__(self, config=None):
        # טעינת קונפיגורציה קודם
        if config:
            self.wake_word = config.get('wake_word', "gonzo")
            self.device_index_listening = config.get('device_index_listening', 0)
            self.device_index_command = config.get('device_index_command', 0)
            self.language = config.get('language', "en")
            if 'model_path' in config:
                self.model_paths = {"custom": config['model_path']}
            else:
                self.model_paths = {
                    "en": "models/vosk-model-small-en-us-0.15",
                    "he": "models/vosk-model-he"
                }
        else:
            # ברירות מחדל רק אם אין קונפיגורציה
            self.wake_word = "gonzo"
            self.device_index_listening = 0
            self.device_index_command = 0
            self.language = "en"
            self.model_paths = {
                "en": "models/vosk-model-small-en-us-0.15",
                "he": "models/vosk-model-he"
            }
        
        # קונפיגורציה טכנית
        self.target_sample_rate = 16000
        self.block_size = 1024#2048#4096#8000
        self.running = True
        self.is_listening = False
        self.command_mode = False
        
        # מנגנון pause/resume
        self.wake_word_paused = False
        self.pause_lock = threading.Lock()
        
        # Native sample rates
        self.listening_native_rate = 44100
        self.command_native_rate = 44100
        
        # תורים לנתוני שמע
        self.listening_queue = queue.Queue()
        self.command_queue = queue.Queue()
        
        # בחירת מודל לפי שפה
        selected_model_path = self.model_paths.get(self.language, 
                                                  self.model_paths.get("custom", 
                                                                      self.model_paths.get("en")))
        
        # טעינת מודל Vosk
        if os.path.exists(selected_model_path):
            self.model = Model(selected_model_path)
            print(f"Loaded Vosk model from {selected_model_path}")
        else:
            print(f"Warning: Model path {selected_model_path} not found.")
            # נסיון fallback
            fallback_path = self.model_paths.get("en", "models/vosk-model-small-en-us-0.15")
            if os.path.exists(fallback_path):
                self.model = Model(fallback_path)
                print(f"Using fallback English model from {fallback_path}")
            else:
                raise FileNotFoundError(f"No Vosk model found. Please download a model to {selected_model_path}")
        
        # יצירת מזהי קול
        self.wake_recognizer = KaldiRecognizer(self.model, self.target_sample_rate)
        self.command_recognizer = KaldiRecognizer(self.model, self.target_sample_rate)
        
        # זיהוי sample rates
        self._detect_microphone_rates()
        
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
        
        # עדכון תגובות מקונפיג אם קיים
        if config and 'responses' in config and 'wake_responses' in config['responses']:
            self.wake_responses = config['responses']['wake_responses']
    
    def _detect_microphone_rates(self):
        """Detect the native sample rates for both microphones"""
        print("Detecting microphone sample rates...")
        
        self.listening_native_rate = self._get_device_native_rate(self.device_index_listening)
        print(f"Listening mic (device {self.device_index_listening}): {self.listening_native_rate} Hz")
        
        self.command_native_rate = self._get_device_native_rate(self.device_index_command)
        print(f"Command mic (device {self.device_index_command}): {self.command_native_rate} Hz")
    
    def _get_device_native_rate(self, device_index):
        """Get the native sample rate for a specific device"""
        try:
            device_info = sd.query_devices(device_index)
            native_rate = int(device_info['default_samplerate'])
            
            test_rates = [16000, 22050, 44100, 48000, 96000]
            
            if native_rate in test_rates:
                return native_rate
            
            for rate in test_rates:
                try:
                    with sd.RawInputStream(
                        samplerate=rate,
                        device=device_index,
                        dtype='int16',
                        channels=1,
                        blocksize=1024
                    ):
                        return rate
                except:
                    continue
            
            return native_rate
            
        except Exception as e:
            print(f"Error detecting sample rate for device {device_index}: {e}")
            return 48000
    
    def _resample_audio(self, audio_data, from_rate, to_rate):
        """Resample audio from one rate to another"""
        if from_rate == to_rate:
            return audio_data
        
        audio_np = np.frombuffer(audio_data, dtype=np.int16)
        new_length = int(len(audio_np) * to_rate / from_rate)
        resampled = signal.resample(audio_np, new_length)
        resampled_int16 = resampled.astype(np.int16)
        return resampled_int16.tobytes()
    
    def listening_callback(self, indata, frames, time, status):
        """פונקציית קולבק להאזנה למילת ההפעלה"""
        if status:
            print(f"Error in listening mic: {status}")
        
        # בדיקה אם מושהה
        with self.pause_lock:
            if self.wake_word_paused:
                return  # דילוג על עיבוד כשמושהה
        
        resampled_data = self._resample_audio(
            bytes(indata), 
            self.listening_native_rate, 
            self.target_sample_rate
        )
        
        self.listening_queue.put(resampled_data)
    
    def command_callback(self, indata, frames, time, status):
        """פונקציית קולבק להאזנה לפקודות"""
        if status:
            print(f"Error in command mic: {status}")
        
        resampled_data = self._resample_audio(
            bytes(indata), 
            self.command_native_rate, 
            self.target_sample_rate
        )
        
        self.command_queue.put(resampled_data)
    
    def pause_wake_word_listening(self):
        """השהיית האזנה למילת מפתח זמנית"""
        with self.pause_lock:
            self.wake_word_paused = True
            print("Wake word listening paused")
    
    def resume_wake_word_listening(self):
        """המשך האזנה למילת מפתח"""
        with self.pause_lock:
            self.wake_word_paused = False
            # ניקוי תור ישן
            while not self.listening_queue.empty():
                try:
                    self.listening_queue.get_nowait()
                except:
                    break
            print("Wake word listening resumed")
    
    def listen_for_wake_word(self):
        """האזנה רציפה למילת ההפעלה ב-thread נפרד עם מנגנון pause"""
        try:
            with sd.RawInputStream(
                samplerate=self.listening_native_rate,
                blocksize=self.block_size, 
                device=self.device_index_listening, 
                dtype="int16", 
                channels=1, 
                callback=self.listening_callback
            ):
                
                print(f"Listening for wake word '{self.wake_word}' at {self.listening_native_rate}Hz...")
                
                while self.running:
                    # בדיקה אם מושהה
                    with self.pause_lock:
                        if self.wake_word_paused:
                            time.sleep(0.1)  # המתנה קצרה
                            continue
                    
                    try:
                        data = self.listening_queue.get(timeout=0.5)
                        if self.wake_recognizer.AcceptWaveform(data):
                            result = json.loads(self.wake_recognizer.Result())
                            text = result.get("text", "").lower()
                            
                            if self.wake_word in text:
                                print(f"Wake word detected: {text}")
                                
                                # בחירת תגובה אקראית לפי השפה
                                responses = self.wake_responses.get(self.language, self.wake_responses["en"])
                                response = random.choice(responses)
                                print(f"Response: {response}")
                                
                                # השהיית האזנה למילת מפתח
                                self.pause_wake_word_listening()
                                
                                # הפעלת callback
                                self.on_wake_word_detected(response)
                                
                    except queue.Empty:
                        # timeout בתור - ממשיכים
                        continue
                        
        except Exception as e:
            print(f"Error in wake word detection: {e}")
    
    def listen_for_commands(self):
        """האזנה לפקודות לאחר זיהוי מילת ההפעלה - רץ על thread ראשי"""
        try:
            with sd.RawInputStream(
                samplerate=self.command_native_rate,
                blocksize=self.block_size, 
                device=self.device_index_command, 
                dtype="int16", 
                channels=1, 
                callback=self.command_callback
            ):
                
                print(f"Listening for commands at {self.command_native_rate}Hz...")
                command_timeout = time.time() + 10  # 10 שניות לקבלת פקודה
                
                while self.running and time.time() < command_timeout:
                    try:
                        data = self.command_queue.get(timeout=1)
                        if self.command_recognizer.AcceptWaveform(data):
                            result = json.loads(self.command_recognizer.Result())
                            command_text = result.get("text", "").lower()
                            
                            if command_text:
                                print(f"Command detected: {command_text}")
                                # המשך האזנה למילת מפתח
                                self.resume_wake_word_listening()
                                return command_text
                    except queue.Empty:
                        # טיימאאוט בתור - זה בסדר, ממשיכים
                        pass
                
                # אם הגענו לכאן, חלף זמן ההמתנה ללא פקודה
                print("Command timeout reached")
                # המשך האזנה למילת מפתח
                self.resume_wake_word_listening()
                return None
                
        except Exception as e:
            print(f"Error in command detection: {e}")
            # המשך האזנה למילת מפתח גם במקרה של שגיאה
            self.resume_wake_word_listening()
            return None
    
    def listen_for_face_interaction(self):
        """האזנה לתשובה באינטראקציה של זיהוי פנים - רץ על thread ראשי"""
        print("Listening for face interaction response...")
        
        # השהיית האזנה למילת מפתח
        self.pause_wake_word_listening()
        
        try:
            with sd.RawInputStream(
                samplerate=self.command_native_rate,
                blocksize=self.block_size, 
                device=self.device_index_command, 
                dtype="int16", 
                channels=1, 
                callback=self.command_callback
            ):
                
                interaction_timeout = time.time() + 5  # 5 שניות לתשובה
                
                while self.running and time.time() < interaction_timeout:
                    try:
                        data = self.command_queue.get(timeout=1)
                        if self.command_recognizer.AcceptWaveform(data):
                            result = json.loads(self.command_recognizer.Result())
                            response_text = result.get("text", "").lower()
                            
                            if response_text:
                                print(f"Face interaction response: {response_text}")
                                # המשך האזנה למילת מפתח
                                self.resume_wake_word_listening()
                                return response_text
                    except queue.Empty:
                        pass
                
                print("Face interaction timeout reached")
                # המשך האזנה למילת מפתח
                self.resume_wake_word_listening()
                return None
                
        except Exception as e:
            print(f"Error in face interaction: {e}")
            # המשך האזנה למילת מפתח גם במקרה של שגיאה
            self.resume_wake_word_listening()
            return None
    
    def on_wake_word_detected(self, response):
        """פונקציה שתוחלף על-ידי המודול הראשי"""
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
                rate = int(device['default_samplerate'])
                channels = device['max_input_channels']
                print(f"Input Device {i}: {device['name']} ({rate} Hz) - {channels} channels")
                input_devices.append((i, device['name'], rate))
        
        return input_devices
    
    def set_language(self, language_code):
        """שינוי שפת המערכת"""
        if language_code in self.model_paths:
            self.language = language_code
            print(f"Language changed to {language_code}")
            return True
        
        print(f"Language {language_code} is not supported")
        return False


if __name__ == "__main__":
    # דוגמה לשימוש במודול
    stt = GonzoSTT()
    
    # הצגת התקני שמע
    stt.list_audio_devices()
    
  