import threading
import speech_recognition as sr
import time
import queue

class ContinuousVoiceListener:
    """
    Class that provides continuous voice listening in the background.
    It runs in a separate thread and can detect trigger words to activate
    full command processing.
    """
    def __init__(self, callback=None, device_index=None, trigger_words=None):
        """
        Initialize the continuous voice listener.
        
        Args:
            callback (function): Function to call when a voice command is detected.
                                The function should accept a string parameter (the command).
            device_index (int): Microphone device index to use. None for default.
            trigger_words (list): List of words that trigger the callback. If None,
                                all speech will be processed.
        """
        self.callback = callback
        self.device_index = device_index
        self.trigger_words = trigger_words or ["hey robot", "hello robot", "robot", "listen"]
        
        self.running = False
        self.thread = None
        self.command_queue = queue.Queue()
        
        # Initialize speech recognition
        self.recognizer = sr.Recognizer()
        
        # Adjust recognizer settings
        self.recognizer.energy_threshold = 4000  # Minimum audio energy to consider detection
        self.recognizer.dynamic_energy_threshold = True  # Dynamically adjust for ambient noise
        self.recognizer.pause_threshold = 0.8  # Seconds of non-speaking audio to consider end of phrase
        
        # Initialize microphone
        try:
            self.microphone = sr.Microphone(device_index=self.device_index)
            print(f"Initialized microphone{' index: '+str(device_index) if device_index is not None else ''}")
        except Exception as e:
            print(f"Error initializing microphone: {e}")
            self.microphone = None

    def start(self):
        """Start the background listening thread."""
        if self.microphone is None:
            print("Error: Microphone not initialized.")
            return False
        
        if self.thread is not None and self.thread.is_alive():
            print("Listener is already running.")
            return True
        
        self.running = True
        self.thread = threading.Thread(target=self._listen_loop)
        self.thread.daemon = True
        self.thread.start()
        print("Continuous voice listener started.")
        return True

    def stop(self):
        """Stop the background listening thread."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        print("Continuous voice listener stopped.")

    def get_command(self, block=False, timeout=None):
        """
        Get the next command from the queue.
        
        Args:
            block (bool): Whether to block until a command is available.
            timeout (float): How long to wait for a command when blocking.
            
        Returns:
            str or None: The command, or None if no command is available.
        """
        try:
            return self.command_queue.get(block=block, timeout=timeout)
        except queue.Empty:
            return None

    def _listen_loop(self):
        """Background thread that continuously listens for speech."""
        # Adjust for ambient noise first
        print("Adjusting for ambient noise...")
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
        
        print("Now listening for voice commands...")
        
        while self.running:
            try:
                with self.microphone as source:
                    # Listen for a short phrase, with a timeout to prevent blocking
                    audio = self.recognizer.listen(source, phrase_time_limit=5, timeout=None)
                
                try:
                    # Recognize speech using Google Speech Recognition
                    text = self.recognizer.recognize_google(audio)
                    print(f"Heard: {text}")
                    
                    # Check if any trigger word is in the speech
                    if self._contains_trigger(text):
                        # Extract the actual command (remove the trigger word)
                        command = self._extract_command(text)
                        print(f"Trigger detected! Command: {command}")
                        
                        # Add to command queue
                        self.command_queue.put(command)
                        
                        # Call the callback if provided
                        if self.callback:
                            self.callback(command)
                
                except sr.UnknownValueError:
                    # Speech was unintelligible
                    pass
                except sr.RequestError as e:
                    print(f"Could not request results from Google Speech Recognition service; {e}")
            
            except sr.WaitTimeoutError:
                # Timeout while waiting for phrase, just continue
                pass
            except Exception as e:
                print(f"Error in listening loop: {e}")
                # Small delay before retrying
                time.sleep(0.5)
    
    def _contains_trigger(self, text):
        """
        Check if the text contains any of the trigger words.
        
        Args:
            text (str): The text to check.
            
        Returns:
            bool: True if a trigger word is found, False otherwise.
        """
        text = text.lower()
        return any(trigger.lower() in text for trigger in self.trigger_words)
    
    def _extract_command(self, text):
        """
        Extract the actual command by removing the trigger word.
        
        Args:
            text (str): The text containing the command.
            
        Returns:
            str: The command portion of the text.
        """
        text = text.lower()
        
        # Find which trigger word was used
        used_trigger = next((trigger for trigger in self.trigger_words if trigger.lower() in text), None)
        
        if used_trigger:
            # Find the position of the trigger
            pos = text.find(used_trigger.lower())
            
            # Get everything after the trigger
            command = text[pos + len(used_trigger):].strip()
            
            # If nothing after the trigger, return the whole text
            return command if command else text
        
        # If no trigger found (shouldn't happen), return the whole text
        return text

# Example usage
if __name__ == "__main__":
    def process_command(command):
        print(f"Processing command: {command}")
    
    # List available microphones
    print("Available microphones:")
    for index, name in enumerate(sr.Microphone.list_microphone_names()):
        print(f"Microphone {index}: {name}")
    
    # Select a microphone index (or None for default)
    mic_index = 1  # Change to the desired microphone index
    
    # Create and start the listener
    listener = ContinuousVoiceListener(
        callback=process_command,
        device_index=mic_index,
        trigger_words=["hey robot", "robot", "hello", "hey system"]
    )
    
    if listener.start():
        try:
            print("Listener running. Say a trigger word followed by a command.")
            print("Press Ctrl+C to exit.")
            
            # Keep the main thread alive
            while True:
                # Check for commands in the queue
                command = listener.get_command(block=True, timeout=1.0)
                if command:
                    print(f"Got command from queue: {command}")
                
                time.sleep(0.1)  # Reduce CPU usage
        
        except KeyboardInterrupt:
            print("Stopping...")
        finally:
            listener.stop()