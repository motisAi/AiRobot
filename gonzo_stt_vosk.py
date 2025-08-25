# מודול זיהוי דיבור מקומי עם Vosk - גרסה מתוקנת עם resampling
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
        # קונפיגורציה בסיסית
        self.target_sample_rate = 16000  # Vosk requires 16kHz
        self.device_index_listening = 0  # מיקרופון להאזנה קבועה
        self.device_index_command = 0    # מיקרופון לפקודות
        self.wake_word = "gonzo"
        self.block_size = 8000
        self.running = True
        self.is_listening = False
        self.command_mode = False
        self.language = "en"  # ברירת מחדל: אנגלית
        
        # Native sample rates for each microphone
        self.listening_native_rate = 48000  # Will be detected automatically
        self.command_native_rate = 48000    # Will be detected automatically
        
        # נתיבים למודלים לפי שפה
        self.model_paths = {
            "en": "models/vosk-model-small-en-us-0.15",  # Your existing English model
            "he": "models/vosk-model-he"   # Hebrew model if you download it
        }
        
        # תורים לנתוני שמע
        self.listening_queue = queue.Queue()
        self.command_queue = queue.Queue()
        
        # טעינת קונפיגורציה אם קיימת
        if config:
            self.wake_word = config.get('wake_word', "gonzo")
            self.device_index_listening = config.get('device_index_listening', 0)
            self.device_index_command = config.get('device_index_command', 0)
            self.language = config.get('language', "en")
            
            if 'model_path' in config:
                # אם מסופק נתיב ספציפי, נשתמש בו
                self.model_paths["custom"] = config['model_path']
        
        # בחירת מודל לפי שפה
        selected_model_path = self.model_paths.get(self.language, 
                                                  self.model_paths.get("custom", 
                                                                      self.model_paths["en"]))
        
        # טעינת מודל Vosk
        if os.path.exists(selected_model_path):
            self.model = Model(selected_model_path)
            print(f"Loaded Vosk model from {selected_model_path}")
        else:
            print(f"Warning: Model path {selected_model_path} not found.")
            # Try the English model as fallback
            if os.path.exists(self.model_paths["en"]):
                self.model = Model(self.model_paths["en"])
                print(f"Using fallback English model from {self.model_paths['en']}")
            else:
                raise FileNotFoundError(f"No Vosk model found. Please download a model to {selected_model_path}")
        
        # יצירת מזהי קול
        self.wake_recognizer = KaldiRecognizer(self.model, self.target_sample_rate)
        self.command_recognizer = KaldiRecognizer(self.model, self.target_sample_rate)
        
        # Detect native sample rates for microphones
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
        
        # אם יש תגובות בקובץ הקונפיגורציה, נשתמש בהן
        if config and 'responses' in config and 'wake_responses' in config['responses']:
            self.wake_responses = config['responses']['wake_responses']
    
    def _detect_microphone_rates(self):
        """Detect the native sample rates for both microphones"""
        print("Detecting microphone sample rates...")
        
        # Test listening microphone
        self.listening_native_rate = self._get_device_native_rate(self.device_index_listening)
        print(f"Listening mic (device {self.device_index_listening}): {self.listening_native_rate} Hz")
        
        # Test command microphone  
        self.command_native_rate = self._get_device_native_rate(self.device_index_command)
        print(f"Command mic (device {self.device_index_command}): {self.command_native_rate} Hz")
    
    def _get_device_native_rate(self, device_index):
        """Get the native sample rate for a specific device"""
        try:
            device_info = sd.query_devices(device_index)
            native_rate = int(device_info['default_samplerate'])
            
            # Common sample rates to test
            test_rates = [16000, 22050, 44100, 48000, 96000]
            
            # If the default rate is already in our test list, use it
            if native_rate in test_rates:
                return native_rate
            
            # Otherwise, test which rates work
            for rate in test_rates:
                try:
                    # Try to open a stream with this rate
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
            
            # Fallback to default rate
            return native_rate
            
        except Exception as e:
            print(f"Error detecting sample rate for device {device_index}: {e}")
            return 48000  # Fallback to common rate
    
    def _resample_audio(self, audio_data, from_rate, to_rate):
        """Resample audio from one rate to another"""
        if from_rate == to_rate:
            return audio_data
        
        # Convert bytes to numpy array
        audio_np = np.frombuffer(audio_data, dtype=np.int16)
        
        # Calculate new length
        new_length = int(len(audio_np) * to_rate / from_rate)
        
        # Resample using scipy
        resampled = signal.resample(audio_np, new_length)
        
        # Convert back to int16 and bytes
        resampled_int16 = resampled.astype(np.int16)
        return resampled_int16.tobytes()
    
    def listening_callback(self, indata, frames, time, status):
        """פונקציית קולבק להאזנה למילת ההפעלה"""
        if status:
            print(f"Error in listening mic: {status}")
        
        # Resample from native rate to 16kHz
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
        
        # Resample from native rate to 16kHz
        resampled_data = self._resample_audio(
            bytes(indata), 
            self.command_native_rate, 
            self.target_sample_rate
        )
        
        self.command_queue.put(resampled_data)
    
    def listen_for_wake_word(self):
        """האזנה רציפה למילת ההפעלה"""
        try:
            with sd.RawInputStream(
                samplerate=self.listening_native_rate,  # Use native rate
                blocksize=self.block_size, 
                device=self.device_index_listening, 
                dtype="int16", 
                channels=1, 
                callback=self.listening_callback
            ):
                
                print(f"Listening for wake word '{self.wake_word}' at {self.listening_native_rate}Hz...")
                
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
            with sd.RawInputStream(
                samplerate=self.command_native_rate,  # Use native rate
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
                rate = int(device['default_samplerate'])
                print(f"Index {i}: {device['name']} ({rate} Hz)")
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


# מבחן למודול אם מריצים אותו ישירות
if __name__ == "__main__":
    # Install scipy if not already installed
    try:
        from scipy import signal
    except ImportError:
        print("scipy is required for audio resampling. Install it with:")
        print("pip install scipy")
        exit(1)
    
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
            
            # Re-detect rates for selected devices
            stt._detect_microphone_rates()
        except ValueError:
            print("Invalid input, using default device 0")
    
    # בחירת שפה
    print("\nChoose language (en/he):")
    lang = input("Enter language code (default: en): ") or "en"
    stt.set_language(lang)
    
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
        print(f"\nStarting wake word detection. Say '{stt.wake_word}' to activate...")
        stt.start_listening()
        
        # השארת התוכנית רצה
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        stt.stop_listening()
        print("Stopped")
