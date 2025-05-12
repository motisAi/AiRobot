import serial
import threading
import time
import queue

class SerialCommunication:
    """
    A simplified class to handle serial communication with ESP32 in a separate thread.
    Simply sends commands and receives responses without hardcoded command-response mappings.
    """
    def _init_(self, port, baudrate=115200, timeout=1):
        """
        Initialize the SerialCommunication class.
        
        Args:
            port (str): Serial port name (e.g., 'COM3' on Windows, '/dev/ttyUSB0' on Linux)
            baudrate (int): Communication speed, default 115200
            timeout (int): Serial read timeout in seconds
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial = None
        self.running = False
        self.thread = None
        
        # Queues for communication between threads
        self.command_queue = queue.Queue()  # Commands to be sent to ESP32
        self.response_queue = queue.Queue()  # Responses received from ESP32
        
        # Callback for new responses
        self.response_callback = None

    def connect(self):
        """Connect to the serial port and start the communication thread."""
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout
            )
            print(f"Connected to {self.port} at {self.baudrate} baud")
            
            # Start the communication thread
            self.running = True
            self.thread = threading.Thread(target=self._communication_thread)
            self.thread.daemon = True  # Thread will close when the main program exits
            self.thread.start()
            return True
            
        except serial.SerialException as e:
            print(f"Error connecting to serial port: {e}")
            return False

    def disconnect(self):
        """Disconnect from the serial port and stop the communication thread."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)  # Wait for the thread to finish
        if self.serial and self.serial.is_open:
            self.serial.close()
            print(f"Disconnected from {self.port}")

    def send_command(self, command):
        """
        Send a command to the ESP32.
        
        Args:
            command (str): Command to send
            
        Returns:
            bool: True if command was queued successfully
        """
        if not self.running or not self.serial:
            print("Serial connection not established")
            return False
            
        self.command_queue.put(command)
        print(f"Command queued: {command}")
        return True
    
    def get_response(self, block=False, timeout=1.0):
        """
        Get the next response from the ESP32.
        
        Args:
            block (bool): If True, block until a response is available or timeout
            timeout (float): How long to wait for a response when blocking
            
        Returns:
            str or None: The response, or None if no response is available
        """
        try:
            return self.response_queue.get(block=block, timeout=timeout)
        except queue.Empty:
            return None
    
    def set_response_callback(self, callback_function):
        """
        Set a callback function to be called whenever a new response is received.
        The callback function should take a single parameter, which is the response string.
        
        Args:
            callback_function: Function to call with each new response
        """
        self.response_callback = callback_function
    
    def _communication_thread(self):
        """Thread function that handles sending commands and receiving responses."""
        print("Communication thread started")
        
        while self.running:
            # This thread stays alive as long as self.running is True
            
            # Send any queued commands
            self._send_queued_commands()
            
            # Check for incoming data
            self._read_serial_data()
            
            # Small sleep to prevent CPU overuse
            time.sleep(0.01)
        
        print("Communication thread stopped")
    
    def _send_queued_commands(self):
        """Send any commands in the queue to the ESP32."""
        while not self.command_queue.empty():
            try:
                command = self.command_queue.get()
                if self.serial and self.serial.is_open:
                    # Add newline to command for proper parsing on ESP32
                    full_command = f"{command}\n"
                    self.serial.write(full_command.encode('utf-8'))
                    self.serial.flush()
                    print(f"Sent to ESP32: {command}")
                    
                    # Small delay to ensure command is processed
                    time.sleep(0.1)
            except Exception as e:
                print(f"Error sending command: {e}")
    
    def _read_serial_data(self):
        """Read and process any available data from the serial port."""
        if not self.serial or not self.serial.is_open:
            return
            
        try:
            # Check if data is available
            if self.serial.in_waiting > 0:
                # Read a line of data
                line = self.serial.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    print(f"Received from ESP32: {line}")
                    
                    # Add to response queue
                    self.response_queue.put(line)
                    
                    # Call the callback function if set
                    if self.response_callback:
                        self.response_callback(line)
                    
        except Exception as e:
            print(f"Error reading serial data: {e}")
    
    def translate_voice_command(self, command):
        """
        Translate a voice command to the appropriate serial command.
        This provides a mapping between natural language and ESP commands.
        
        Args:
            command (str): Voice command from user
            
        Returns:
            str or None: Serial command to send, or None if no matching command
        """
        command = command.lower()
        
        # Light controls
        if any(phrase in command for phrase in ["turn on the light", "light on", "lights on"]):
            return "lightOn"
        elif any(phrase in command for phrase in ["turn off the light", "light off", "lights off"]):
            return "lightOff"
            
        # Temperature request
        elif any(phrase in command for phrase in ["temperature", "how hot", "how cold"]):
            return "getTemp"
            
        # Status request
        elif any(phrase in command for phrase in ["status", "system status"]):
            return "status"
            
        # No matching command
        return None