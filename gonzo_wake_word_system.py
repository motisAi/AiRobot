import speech_recognition as sr
import threading
import time
import os
import sounddevice as sd
import soundfile as sf

# Import our simple microphone manager
from auto_monitoring_microphone_manager import MicrophoneManager

class WakeWordDetector:
    """
    A system that continuously listens for a wake word ("gonzo") and then
    triggers a callback for further command processing.
    """
    
    def __init__(self, wake_word="gonzo", mic_index=None, sensitivity=0.5, 
                 callback=None, timeout=5):
        """
        Initialize the wake word detector.
        
        Args:
            wake_word (str): Word to listen for (default: "gonzo")
            mic_index (int): Microphone device index (None = default mic)
            sensitivity (float): Detection sensitivity (0.0-1.0)
            callback (function): Function to call when wake word is detected
            timeout (int): How long to listen for a command after wake word
        """
     
        self.wake_word = wake_word.lower()
        self.mic_index = mic_index
        self.sensitivity = sensitivity
        self.command_callback = callback
        self.timeout = timeout
        
        # Initialize speech recognition
        self.recognizer = sr.Recognizer()
        
        # Set up microphone monitoring
        self.mic_manager = MicrophoneManager(
            default_index=mic_index or 0
        )
        
        # Thread control
        self.running = False
        self.listening_thread = None
        self.in_command_mode = False
        
        # Try to load audio feedback sounds if available
        self.activation_sound = None
        self.end_sound = None
        self._load_audio_feedback()
    
    def _load_audio_feedback(self):
        """Load audio feedback sounds if available."""
        try:
            # You can replace these with actual paths to your sound files
            activation_file = "activation.wav"
            end_file = "end_listening.wav"
            
            if os.path.exists(activation_file):
                self.activation_sound, self.activation_sr = sf.read(activation_file)
            
            if os.path.exists(end_file):
                self.end_sound, self.end_sr = sf.read(end_file)
        
        except Exception as e:
            print(f"Note: Could not load audio feedback: {e}")
    
    def play_sound(self, sound_data, sample_rate):
        """Play a sound if available."""
        if sound_data is not None:
            try:
                sd.play(sound_data, sample_rate)
                sd.wait()
            except Exception as e:
                print(f"Error playing sound: {e}")
    
    def start(self):
        """Start listening for the wake word in background."""
        if self.running:
            print("Already listening for wake word")
            return False
        
        # Select best microphone if none specified
        if self.mic_index is None:
            self.mic_index = self.mic_manager.auto_select_best_microphone()
            print(f"Using microphone #{self.mic_index}")
        
        self.running = True
        self.listening_thread = threading.Thread(target=self._listening_loop)
        self.listening_thread.daemon = True
        self.listening_thread.start()
        print(f"Started listening for wake word: '{self.wake_word}'")
        return True
    
    def stop(self):
        """Stop listening for the wake word."""
        if not self.running:
            return False
            
        self.running = False
        if self.listening_thread:
            self.listening_thread.join(timeout=2.0)
        print("Stopped listening for wake word")
        return True
    
    def _listening_loop(self):
        """Main listening loop that runs in background thread."""
        microphone = sr.Microphone(device_index=self.mic_index)
        
        # Start loop
        while self.running:
            # Check if the microphone is still active
            if not self.mic_manager.check_current_mic_active():
                # Try to find new microphone
                new_mic = self.mic_manager.auto_select_best_microphone()
                if new_mic != self.mic_index:
                    print(f"Switching to microphone #{new_mic}")
                    
                    self.mic_index = new_mic
                    microphone = sr.Microphone(device_index=self.mic_index)
            
            try:
                # Listen for wake word using speech recognition
                with microphone as source:
                    print("Listening for wake word...")
                    
                    # Adjust for ambient noise briefly
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    
                    try:
                        # Listen with a short timeout to allow for checking mic status
                        audio = self.recognizer.listen(source, timeout=2, phrase_time_limit=2)
                        
                        try:
                            # Try to recognize the speech
                            text=self.recognizer.recognize_azure(audio, subscription_key="your_subscription_key", region="your_region")
                            text = self.recognizer.recognize_google(audio).lower()
                            print(f"Heard: {text}")
                            
                            # Check if the wake word is in the recognized text
                            if self.wake_word in text:
                                print(f"Wake word '{self.wake_word}' detected!")
                                
                                # Play activation sound
                                self.play_sound(self.activation_sound, 44100)
                                
                                # Enter command mode
                                self.in_command_mode = True
                                
                                # Listen for command
                                print("Listening for command...")
                                try:
                                    with microphone as cmd_source:
                                        # Briefly adjust for ambient noise again
                                        self.recognizer.adjust_for_ambient_noise(cmd_source, duration=0.2)
                                        
                                        # Listen for the command
                                        command_audio = self.recognizer.listen(
                                            cmd_source, 
                                            timeout=self.timeout,
                                            phrase_time_limit=5
                                        )
                                        
                                        # Play end sound
                                        self.play_sound(self.end_sound, 44100)
                                        
                                        # Process the command
                                        try:
                                            command = self.recognizer.recognize_google(command_audio)
                                            print(f"Command: {command}")
                                            
                                            # Call the callback function
                                            if self.command_callback:
                                                self.command_callback(command)
                                        
                                        except sr.UnknownValueError:
                                            print("Could not understand command")
                                        
                                        except sr.RequestError as e:
                                            print(f"Could not request results: {e}")
                                
                                except Exception as cmd_err:
                                    print(f"Error during command listening: {cmd_err}")
                                
                                finally:
                                    self.in_command_mode = False
                        
                        except sr.UnknownValueError:
                            # Speech wasn't understood, just continue listening
                            pass
                        
                        except sr.RequestError as e:
                            print(f"Could not request results: {e}")
                            # Sleep a bit longer on API errors to avoid rapid retries
                            time.sleep(1)
                    
                    except sr.WaitTimeoutError:
                        # Timeout waiting for speech, just continue
                        pass
            
            except Exception as e:
                print(f"Error in listening loop: {e}")
                time.sleep(1)  # Wait before retrying
            
            # Small delay to prevent CPU overuse
            time.sleep(0.1)


# Example usage
if __name__ == "__main__":
    # Callback function that will be called when a command is detected
    def process_command(command):
        print(f"Processing command: '{command}'")
        # Here you would implement your command processing logic
    
    # List available microphones
    print("Available microphones:")
    mic_manager = MicrophoneManager()
    mics = mic_manager.get_mic_list()
    for i, mic in enumerate(mics):
        status = "ACTIVE" if mic['is_active'] else "INACTIVE"
        print(f"{i+1}. {mic['name']} (Device #{mic['index']}) - {status}")
    
    # Create wake word detector with the selected microphone
    detector = WakeWordDetector(
        wake_word="gonzo",
        mic_index=mic_manager.auto_select_best_microphone(),
        callback=process_command
    )
    
    # Start listening for the wake word
    detector.start()
    
    print("\nSystem is listening for the wake word 'gonzo'...")
    print("Say 'gonzo' followed by your command")
    print("Press Ctrl+C to exit")
    
    try:
        # Keep the main thread alive
        while True:
            time.sleep(1)
    
    except KeyboardInterrupt:
        print("\nExiting...")
    
    finally:
        # Stop the detector
        detector.stop()