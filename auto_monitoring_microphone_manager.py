import pyaudio
import audioop
import time

class MicrophoneManager:
    """
    Simplified microphone manager class that handles microphone detection and selection.
    """
    
    def __init__(self, default_index=0, rms_threshold=500, test_duration=1.0):
        """
        Initialize the MicrophoneManager.
        
        Args:
            default_index (int): Default microphone index
            rms_threshold (int): Threshold for considering a microphone active
            test_duration (float): Duration for testing microphone activity
        """
        print("Initializing Microphone Manager...")
        self.default_index = default_index
        self.rms_threshold = rms_threshold
        self.test_duration = test_duration
        self.current_index = default_index
        print("Microphone Manager Initialized")
        # Initialize microphone lists
        self.active_mics = []
        self.all_mics = []
        
        # Scan available microphones
        self.scan_microphones()
    
    def scan_microphones(self):
        """Scan for available microphones and test their activity."""
        self.all_mics = self._find_all_input_devices()
        self.active_mics = []
        
        for device in self.all_mics:
            is_active, rms = self._check_mic_activity(device['index'])
            device['is_active'] = is_active
            device['rms'] = rms
            
            if is_active:
                self.active_mics.append(device)
        
        # Auto-select a microphone if none is selected yet
        if self.active_mics and not self._is_current_mic_active():
            self.current_index = self.active_mics[0]['index']
        
        return self.active_mics
    
    def get_mic_list(self, active_only=False):
        """
        Get list of all microphones or only active ones.
        
        Args:
            active_only (bool): If True, return only active microphones
        
        Returns:
            list: List of microphone dictionaries
        """
        return self.active_mics if active_only else self.all_mics
    
    def auto_select_best_microphone(self):
        """
        Automatically select the best available microphone.
        
        Returns:
            int: Selected microphone index
        """
        # Update our list of active microphones
        self.scan_microphones()
        
        # If no active microphones, use default
        if not self.active_mics:
            self.current_index = self.default_index
            return self.current_index
        
        # Find mic with highest RMS (most sensitive)
        sorted_mics = sorted(self.active_mics, key=lambda x: x.get('rms', 0), reverse=True)
        self.current_index = sorted_mics[0]['index']
        
        return self.current_index
    
    def get_current_mic_index(self):
        """Get the currently selected microphone index."""
        return self.current_index
    
    def select_microphone(self, index):
        """
        Manually select a specific microphone.
        
        Args:
            index (int): Index of the microphone to select
        
        Returns:
            bool: True if selection was successful
        """
        # Check if the microphone exists
        found = False
        for device in self.all_mics:
            if device['index'] == index:
                found = True
                break
        
        if found:
            self.current_index = index
            return True
        
        return False
    
    def check_current_mic_active(self):
        """
        Check if the current microphone is still active.
        
        Returns:
            bool: True if current mic is active
        """
        return self._is_current_mic_active()
    
    def _find_all_input_devices(self):
        """Find all devices with input channels."""
        p = pyaudio.PyAudio()
        
        input_devices = []
        for i in range(p.get_device_count()):
            try:
                dev_info = p.get_device_info_by_index(i)
                if dev_info['maxInputChannels'] > 0:
                    input_devices.append({
                        'index': i,
                        'name': dev_info['name'],
                        'channels': dev_info['maxInputChannels'],
                        'rate': int(dev_info['defaultSampleRate']),
                        'is_active': False,
                        'rms': 0
                    })
            except Exception as e:
                print(f"Error getting device info for {i}: {e}")
        
        p.terminate()
        return input_devices
    
    def _check_mic_activity(self, device_index):
        """Test if a microphone is active by measuring audio levels."""
        p = pyaudio.PyAudio()
        
        try:
            # Get device info
            dev_info = p.get_device_info_by_index(device_index)
            channels = dev_info['maxInputChannels']
            rate = int(dev_info['defaultSampleRate'])
            
            # Open stream
            stream = p.open(
                format=pyaudio.paInt16,
                channels=min(channels, 1),  # Use mono
                rate=rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=1024
            )
            
            # Read audio data
            frames = []
            start_time = time.time()
            while time.time() - start_time < self.test_duration:
                try:
                    data = stream.read(1024, exception_on_overflow=False)
                    frames.append(data)
                except:
                    p.terminate()
                    return False, 0
            
            # Close stream
            stream.stop_stream()
            stream.close()
            
            # Calculate RMS value
            audio_data = b''.join(frames)
            rms = audioop.rms(audio_data, 2)  # 2 bytes per sample for paInt16
            
            is_active = rms > self.rms_threshold
            
            return is_active, rms
        
        except Exception as e:
            return False, 0
        
        finally:
            p.terminate()
    
    def _is_current_mic_active(self):
        """Check if the currently selected microphone is active."""
        is_active, _ = self._check_mic_activity(self.current_index)
        return is_active


# Example usage
if __name__ == "__main__":
    # Create the microphone manager
    mic_manager = MicrophoneManager()
    
    # Scan for microphones
    print("Scanning for microphones...")
    mics = mic_manager.get_mic_list()
    
    print("All detected microphones:")
    for i, mic in enumerate(mics):
        status = "ACTIVE" if mic['is_active'] else "INACTIVE"
        print(f"Device #{mic['index']}: {mic['name']} - {status} (RMS: {mic['rms']})")
    
    # Select the best microphone
    best_mic = mic_manager.auto_select_best_microphone()
    print(f"\nSelected best microphone: Device #{best_mic}")