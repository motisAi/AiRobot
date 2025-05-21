# מודול TTS מקומי עם pyttsx3
import os
import pyttsx3
import threading
import time

class GonzoTTS:
    def __init__(self, config=None):
        # קונפיגורציה בסיסית
        self.rate = 150  # מהירות דיבור
        self.volume = 1.0  # עוצמת קול
        self.voice_id = None  # קול ספציפי (None = ברירת מחדל)
        
        # איתחול מנוע TTS
        self.engine = pyttsx3.init()
        self.engine.setProperty('rate', self.rate)
        self.engine.setProperty('volume', self.volume)
        
        # בדיקת קולות זמינים
        self.available_voices = self.engine.getProperty('voices')
        
        # טעינת קונפיגורציה אם קיימת
        if config:
            if 'tts_rate' in config:
                self.rate = config['tts_rate']
                self.engine.setProperty('rate', self.rate)
            if 'tts_volume' in config:
                self.volume = config['tts_volume']
                self.engine.setProperty('volume', self.volume)
            if 'tts_voice_id' in config and config['tts_voice_id']:
                self.set_voice(config['tts_voice_id'])
    
    def set_voice(self, voice_id):
        """הגדרת קול ספציפי לפי מזהה"""
        for voice in self.available_voices:
            if voice_id in voice.id:
                self.voice_id = voice.id
                self.engine.setProperty('voice', voice.id)
                return True
        # אם לא נמצא קול מתאים
        print(f"Warning: Voice ID '{voice_id}' not found. Using default voice.")
        return False
    
    def list_available_voices(self):
        """הצגת רשימת קולות זמינים"""
        print("\nAvailable voices:")
        for i, voice in enumerate(self.available_voices):
            print(f"{i}: ID={voice.id}, Name={voice.name}, Languages={voice.languages}")
        return self.available_voices
    
    def speak(self, text, block=True):
        """השמעת טקסט
        
        Args:
            text: הטקסט להשמעה
            block: האם לחסום את התהליך הראשי בזמן ההשמעה
        """
        if not text:
            return
        
        if block:
            # השמעה סינכרונית (חוסמת)
            self.engine.say(text)
            self.engine.runAndWait()
        else:
            # השמעה אסינכרונית (לא חוסמת)
            speech_thread = threading.Thread(target=self._speak_async, args=(text,))
            speech_thread.daemon = True
            speech_thread.start()
    
    def _speak_async(self, text):
        """פונקציה פנימית להשמעה אסינכרונית"""
        self.engine.say(text)
        self.engine.runAndWait()
    
    def set_rate(self, rate):
        """שינוי מהירות הדיבור"""
        self.rate = rate
        self.engine.setProperty('rate', rate)
    
    def set_volume(self, volume):
        """שינוי עוצמת הקול"""
        if 0.0 <= volume <= 1.0:
            self.volume = volume
            self.engine.setProperty('volume', volume)
        else:
            print("Volume should be between 0.0 and 1.0")

# מבחן למודול אם מריצים אותו ישירות
if __name__ == "__main__":
    # יצירת אובייקט TTS
    tts = GonzoTTS()
    
    # הצגת קולות זמינים
    voices = tts.list_available_voices()
    
    # בחירת קול (אופציונלי)
    if voices and len(voices) > 1:
        try:
            voice_index = int(input("\nSelect voice (number): ") or "0")
            if 0 <= voice_index < len(voices):
                tts.set_voice(voices[voice_index].id)
        except ValueError:
            print("Invalid input, using default voice")
    
    # מבחן השמעה
    print("\nTesting TTS...")
    
    # דוגמה להשמעה חוסמת
    tts.speak("שלום, אני גונזו. מערכת הבינה המלאכותית שלך.")
    
    # דוגמה להשמעה לא חוסמת
    print("Speaking asynchronously...")
    tts.speak("אני יכול לדבר גם באופן אסינכרוני, כך שהתוכנית יכולה להמשיך לרוץ במקביל.", block=False)
    
    # המתנה כדי לוודא שההשמעה האסינכרונית תסתיים
    time.sleep(5)
    
    print("TTS test completed.")
