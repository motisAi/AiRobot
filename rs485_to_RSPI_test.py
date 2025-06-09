#!/usr/bin/env python3
"""
Simple RS485 Motor Controller Communication
==========================================

Basic script for controlling motor controllers via RS485 using Raspberry Pi
and Xiao RS485 Breakout Board.

Hardware Connections:
- GPIO14 (Pin 8)  -> RS485 RX  
- GPIO15 (Pin 10) -> RS485 TX
- GPIO18 (Pin 12) -> RS485 Enable
- 5V & GND to power connectors

Usage:
1. Import this module
2. Create RS485Motor instance
3. Send register commands to motor controller

Example:
    motor = RS485Motor()
    motor.send_command("01 06 0001 1000")  # Example register write
    response = motor.read_response()
"""

import time
import serial
import RPi.GPIO as GPIO

class RS485Motor:
    def __init__(self, enable_pin=18, tx_pin=14, rx_pin=15, baudrate=9600):
        """
        Initialize RS485 connection for motor controller.
        
        Args:
            enable_pin: GPIO pin for TX/RX control (default: 18)
            tx_pin: GPIO pin for TX (default: 14)
            rx_pin: GPIO pin for RX (default: 15)
            baudrate: Communication speed (default: 9600)
        """
        self.enable_pin = enable_pin
        self.tx_pin = tx_pin
        self.rx_pin = rx_pin
        
        # Setup GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.enable_pin, GPIO.OUT)
        
        # Configure UART pins
        GPIO.setup(self.tx_pin, GPIO.ALT0)  # Set GPIO14 as UART TX
        GPIO.setup(self.rx_pin, GPIO.ALT0)  # Set GPIO15 as UART RX
        
        # Setup Serial
        self.ser = serial.Serial(
            port='/dev/ttyAMA0',  # Use hardware UART
            baudrate=baudrate,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS,
            timeout=1
        )
        
        # Start in receive mode
        self.receive_mode()
        print(f"RS485 Motor Controller initialized on /dev/ttyAMA0")
        print(f"Using TX: GPIO{self.tx_pin}, RX: GPIO{self.rx_pin}, Enable: GPIO{self.enable_pin}")
    
    def transmit_mode(self):
        """Switch to transmit mode (send data)"""
        GPIO.output(self.enable_pin, GPIO.HIGH)  # DE high for TX, RE high (disabled)
    
    def receive_mode(self):
        """Switch to receive mode (listen for data)"""
        GPIO.output(self.enable_pin, GPIO.LOW)   # DE low (disabled), RE low for RX
    
    def send_command(self, command):
        """
        Send command to motor controller.
        
        Args:
            command: Command string or bytes to send
        """
        try:
            # Switch to transmit
            self.transmit_mode()
            
            # Send command
            if isinstance(command, str):
                self.ser.write(command.encode())
            else:
                self.ser.write(command)
            
            # Wait for transmission to complete
            time.sleep(0.01)
            
            # Switch back to receive
            self.receive_mode()
            
            print(f"Sent: {command}")
            
        except Exception as e:
            print(f"Error sending command: {e}")
            self.receive_mode()  # Ensure we're in receive mode
    
    def send_hex_command(self, hex_string):
        """
        Send hex command to motor controller.
        
        Args:
            hex_string: Hex string like "01 06 00 01 10 00"
        """
        try:
            # Convert hex string to bytes
            hex_bytes = bytes.fromhex(hex_string.replace(' ', ''))
            self.send_command(hex_bytes)
            
        except Exception as e:
            print(f"Error sending hex command: {e}")
    
    def read_response(self, timeout=1.0):
        """
        Read response from motor controller.
        
        Args:
            timeout: Maximum time to wait for response
            
        Returns:
            Received data as bytes, or None if no response
        """
        try:
            # Make sure we're in receive mode
            self.receive_mode()
            
            # Wait for data
            start_time = time.time()
            while (time.time() - start_time) < timeout:
                if self.ser.in_waiting > 0:
                    response = self.ser.read(self.ser.in_waiting)
                    print(f"Received: {response.hex(' ')}")
                    return response
                time.sleep(0.01)
            
            print("No response received")
            return None
            
        except Exception as e:
            print(f"Error reading response: {e}")
            return None
    
    def send_and_read(self, command, timeout=1.0):
        """
        Send command and wait for response.
        
        Args:
            command: Command to send
            timeout: Time to wait for response
            
        Returns:
            Response data or None
        """
        self.send_command(command)
        time.sleep(0.1)  # Small delay before reading
        return self.read_response(timeout)
    
    def close(self):
        """Close connection and cleanup GPIO"""
        try:
            self.ser.close()
            GPIO.cleanup()
            print("RS485 connection closed")
        except:
            pass

# Example usage functions
def example_basic_commands():
    """Example of basic motor controller commands"""
    motor = RS485Motor()
    
    try:
        print("\n=== Basic Motor Commands Example ===")
        
        # Example 1: Read motor status (adjust for your controller)
        print("\n1. Reading motor status...")
        motor.send_hex_command("01 03 00 00 00 01")  # Example read command
        response = motor.read_response()
        
        # Example 2: Set motor speed (adjust for your controller) 
        print("\n2. Setting motor speed...")
        motor.send_hex_command("01 06 00 01 03 E8")  # Example write command
        response = motor.read_response()
        
        # Example 3: Start motor (adjust for your controller)
        print("\n3. Starting motor...")
        motor.send_hex_command("01 06 00 02 00 01")  # Example start command
        response = motor.read_response()
        
        time.sleep(2)
        
        # Example 4: Stop motor (adjust for your controller)
        print("\n4. Stopping motor...")
        motor.send_hex_command("01 06 00 02 00 00")  # Example stop command
        response = motor.read_response()
        
    except KeyboardInterrupt:
        print("\nStopped by user")
    finally:
        motor.close()

def interactive_mode():
    """Interactive mode for sending custom commands"""
    motor = RS485Motor()
    
    try:
        print("\n=== Interactive Motor Control ===")
        print("Enter hex commands (e.g., '01 03 00 00 00 01')")
        print("Type 'quit' to exit")
        
        while True:
            command = input("\nEnter command: ").strip()
            
            if command.lower() == 'quit':
                break
            
            if command:
                motor.send_hex_command(command)
                time.sleep(0.1)
                motor.read_response()
                
    except KeyboardInterrupt:
        print("\nStopped by user")
    finally:
        motor.close()

if __name__ == "__main__":
    print("RS485 Motor Controller - Simple Version")
    print("======================================")
    
    choice = input("Choose mode:\n1. Example commands\n2. Interactive mode\nEnter (1 or 2): ")
    
    if choice == "1":
        example_basic_commands()
    elif choice == "2":
        interactive_mode()
    else:
        print("Invalid choice")
