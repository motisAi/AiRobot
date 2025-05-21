# מודול תקשורת סיריאלית עם רכיבי ESP32
import serial
import threading
import time
import queue

class GonzoSerial:
    def __init__(self, config=None):
        # קונפיגורציה בסיסית
        self.port = "/dev/ttyUSB0"
        self.baudrate = 115200
        self.timeout = 1.0
        self.connected = False
        self.serial = None
        self.running = False
        self.thread = None
        self.language = "en"  # ברירת מחדל: אנגלית
        
        # תורים לתקשורת
        self.command_queue = queue.Queue()
        self.response_queue = queue.Queue()
        
        # פונקציית קולבק לתגובות
        self.response_callback = None
        
        # טעינת קונפיגורציה אם קיימת
        if config:
            if 'serial_port' in config:
                self.port = config['serial_port']
            if 'serial_baudrate' in config:
                self.baudrate = config['serial_baudrate']
            if 'language' in config:
                self.language = config['language']
        
        # פקודות בריבוי שפות
        self.command_translations = {
            # פקודות תאורה
            "light_on": {
                "en": ["LIGHT_ON", "ON", "LIGHT ON"],
                "he": ["LIGHT_ON", "ON", "LIGHT ON"]  # לרוב פקודות סיריאל נשארות באנגלית
            },
            "light_off": {
                "en": ["LIGHT_OFF", "OFF", "LIGHT OFF"],
                "he": ["LIGHT_OFF", "OFF", "LIGHT OFF"]
            },
            "get_temperature": {
                "en": ["GET_TEMP", "TEMPERATURE"],
                "he": ["GET_TEMP", "TEMPERATURE"]
            },
            "get_status": {
                "en": ["STATUS", "GET_STATUS"],
                "he": ["STATUS", "GET_STATUS"]
            }
        }
        
        # ניסיון לחיבור אוטומטי
        if config and config.get('use_serial', False):
            self.connect()
    
    def connect(self):
        """התחברות לפורט סיריאלי והתחלת תהליך תקשורת"""
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout
            )
            print(f"Connected to {self.port} at {self.baudrate} baud")
            
            # התחלת תהליך תקשורת
            self.running = True
            self.connected = True
            self.thread = threading.Thread(target=self._communication_thread)
            self.thread.daemon = True
            self.thread.start()
            
            return True
        except serial.SerialException as e:
            print(f"Error connecting to serial port: {e}")
            return False
    
    def close(self):
        """סגירת חיבור סיריאלי ועצירת תהליך התקשורת"""
        self.running = False
        
        if self.thread:
            self.thread.join(timeout=2.0)
        
        if self.serial and self.serial.is_open:
            self.serial.close()
            self.connected = False
            print(f"Disconnected from {self.port}")
    
    def send_command(self, command):
        """שליחת פקודה למערכת החיצונית
        Args:
            command (str): הפקודה לשליחה
        Returns:
            bool: האם הפקודה נוספה לתור בהצלחה
        """
        if not self.running or not self.serial:
            print("Serial connection not established")
            return False
        
        self.command_queue.put(command)
        print(f"Command queued: {command}")
        return True
    
    def get_response(self, block=False, timeout=1.0):
        """קבלת התגובה הבאה מהמערכת
        Args:
            block (bool): האם לחסום את התהליך עד לקבלת תגובה
            timeout (float): זמן המתנה לתגובה (במקרה של חסימה)
        Returns:
            str or None: התגובה שהתקבלה, או None אם אין תגובה זמינה
        """
        try:
            return self.response_queue.get(block=block, timeout=timeout)
        except queue.Empty:
            return None
    
    def set_response_callback(self, callback_function):
        """הגדרת פונקציית קולבק שתופעל כאשר מתקבלת תגובה חדשה
        פונקציית הקולבק צריכה לקבל פרמטר אחד שהוא מחרוזת התגובה
        Args:
            callback_function: פונקציה שתופעל עם כל תגובה חדשה
        """
        self.response_callback = callback_function
    
    def set_language(self, language_code):
        """הגדרת שפה למודול
        
        Args:
            language_code (str): קוד השפה ('en', 'he')
        """
        if language_code in ["en", "he"]:
            self.language = language_code
            print(f"Serial communication language set to {language_code}")
    
    def _communication_thread(self):
        """פונקציית תהליך שמטפלת בשליחת פקודות וקבלת תגובות"""
        print("Communication thread started")
        
        while self.running:
            # שליחת פקודות מהתור
            self._send_queued_commands()
            
            # בדיקת נתונים נכנסים
            self._read_serial_data()
            
            # שינה קצרה כדי למנוע עומס על המעבד
            time.sleep(0.01)
        
        print("Communication thread stopped")
    
    def _send_queued_commands(self):
        """שליחת פקודות מהתור למערכת החיצונית"""
        while not self.command_queue.empty():
            try:
                command = self.command_queue.get()
                if self.serial and self.serial.is_open:
                    # הוספת שורה חדשה לפקודה עבור ניתוח תקין במערכת החיצונית
                    full_command = f"{command}\n"
                    self.serial.write(full_command.encode('utf-8'))
                    self.serial.flush()
                    print(f"Sent to external system: {command}")
                    
                    # השהייה קצרה כדי לוודא שהפקודה מעובדת
                    time.sleep(0.1)
            except Exception as e:
                print(f"Error sending command: {e}")
    
    def _read_serial_data(self):
        """קריאה ועיבוד כל נתון זמין מהפורט הסיריאלי"""
        if not self.serial or not self.serial.is_open:
            return
        
        try:
            # בדיקה אם יש נתונים זמינים
            if self.serial.in_waiting > 0:
                # קריאת שורת נתונים
                line = self.serial.readline().decode('utf-8', errors='ignore').strip()
                
                if line:
                    print(f"Received from external system: {line}")
                    
                    # הוספה לתור התגובות
                    self.response_queue.put(line)
                    
                    # קריאה לפונקציית קולבק אם הוגדרה
                    if self.response_callback:
                        self.response_callback(line)
        except Exception as e:
            print(f"Error reading serial data: {e}")
    
    def translate_voice_command(self, command):
        """
        תרגום פקודה קולית לפקודה סיריאלית מתאימה.
        מספק מיפוי בין שפה טבעית לפקודות מערכת
        Args:
            command (str): פקודה קולית מהמשתמש
        Returns:
            str or None: פקודה סיריאלית לשליחה, או None אם אין פקודה תואמת
        """
        command = command.lower()
        
        # פקודות תאורה
        if any(phrase in command for phrase in ["turn on the light", "light on", "lights on", 
                                               "הדלק אור", "תדליק את האור"]):
            return self.command_translations["light_on"][self.language][0]
        
        elif any(phrase in command for phrase in ["turn off the light", "light off", "lights off",
                                                 "כבה אור", "תכבה את האור"]):
            return self.command_translations["light_off"][self.language][0]
        
        # בקשת טמפרטורה
        elif any(phrase in command for phrase in ["temperature", "how hot", "how cold",
                                                "טמפרטורה", "כמה חם", "מה הטמפרטורה"]):
            return self.command_translations["get_temperature"][self.language][0]
        
        # בקשת סטטוס
        elif any(phrase in command for phrase in ["status", "system status",
                                                "סטטוס", "מצב המערכת"]):
            return self.command_translations["get_status"][self.language][0]
        
        # אין פקודה תואמת
        return None


# מבחן למודול אם מריצים אותו ישירות
if __name__ == "__main__":
    # הגדרות למבחן
    config = {
        'serial_port': "",  # ייקבע על ידי קלט המשתמש
        'serial_baudrate': 115200,
        'use_serial': True
    }
    
    # בחירת שפה
    print("\nChoose language (en/he):")
    lang = input("Enter language code (default: en): ") or "en"
    config['language'] = lang
    
    # בחירת פורט סיריאלי
    print("\nEnter serial port (e.g. COM3 on Windows or /dev/ttyUSB0 on Linux):")
    port = input("Serial port: ")
    if port:
        config['serial_port'] = port
    else:
        # ברירת מחדל לפי מערכת ההפעלה
        import platform
        if platform.system() == "Windows":
            config['serial_port'] = "COM3"
        else:
            config['serial_port'] = "/dev/ttyUSB0"
    
    # יצירת אובייקט תקשורת
    serial_comm = GonzoSerial(config)
    
    # הגדרת פונקציית קולבק לתגובות
    def on_response(response):
        print(f"Response callback: {response}")
    
    serial_comm.set_response_callback(on_response)
    
    # לולאת מבחן
    try:
        print("\nTesting serial communication. Enter commands or 'exit' to quit.")
        
        while True:
            cmd = input("> ")
            if cmd.lower() == 'exit':
                break
            
            # בדיקה אם זו פקודה "מוכרת" מהמיפוי
            translated_cmd = serial_comm.translate_voice_command(cmd)
            if translated_cmd:
                print(f"Translating '{cmd}' to command: {translated_cmd}")
                cmd = translated_cmd
            
            # שליחת פקודה
            serial_comm.send_command(cmd)
            
            # קבלת תגובה (אופציונלי, כיוון שיש לנו קולבק)
            response = serial_comm.get_response(block=True, timeout=2.0)
            if response:
                print(f"Got response: {response}")
    
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        serial_comm.close()
        print("Test completed")