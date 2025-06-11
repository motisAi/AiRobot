"""
import RPi.GPIO as GPIO
import time

# define pins
PWM_PIN = 13    # EN/ENABLE - speed control with PWM
DIR_PIN = 6    # PHASE - direction control

# derfine GPIO mode and setup
GPIO.setmode(GPIO.BCM)
GPIO.setup(PWM_PIN, GPIO.OUT)
GPIO.setup(DIR_PIN, GPIO.OUT)

# create PWM object with frequency of 1kHz
pwm = GPIO.PWM(PWM_PIN, 1000)

try:
    # start PWM with 0% duty cycle
    pwm.start(0)
    
    # direction: clockwise (LOW) - set DIR_PIN to LOW (0) for clockwise & HIGH (1) for counter-clockwise
    GPIO.output(DIR_PIN, GPIO.LOW)
    print("clockwise direction")
    
    # gradual acceleration
    for speed in range(0, 101, 10):
        pwm.ChangeDutyCycle(speed)
        print(f"speed: {speed}%")
        time.sleep(0.5)
    
    # gradual deceleration
    for speed in range(100, -1, -10):
        pwm.ChangeDutyCycle(speed)
        print(f"speed: {speed}%")
        time.sleep(0.5)
    
    # direction: counter-clockwise (HIGH)
 #   GPIO.output(DIR_PIN, GPIO.HIGH)
   # print("direction: counter-clockwise")
    
    # steady speed
   # pwm.ChangeDutyCycle(50)  # 50% 
  # 
  #   time.sleep(3)
    
    # stop motor
    pwm.ChangeDutyCycle(0)

except KeyboardInterrupt:
    pass

finally:
    # stop PWM and cleanup GPIO
    pwm.stop()
    GPIO.cleanup()
    print("end of program")
    """
    
import serial
import time
import struct
import RPi.GPIO as GPIO

class StepperController:
    MAX_SPEED = 3000
    FUNCTION_CODE_WRITE = 0x06
    FUNCTION_CODE_READ = 0x03

    def __init__(self, port: str = "/dev/serial0", baudrate: int = 9600, enable_pin: int = 18):
        """
        Initialize the stepper controller for Raspberry Pi RS485
        Args:
            port (str): Serial port name (default: '/dev/serial0')
            baudrate (int): Communication speed (default: 9600)
            enable_pin (int): GPIO pin for RS485 DE/RE (default: 18)
        """
        self.enable_pin = enable_pin
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.enable_pin, GPIO.OUT)
        GPIO.output(self.enable_pin, GPIO.LOW)  # Start in receive mode

        self.ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=1
        )
        time.sleep(2)  # Allow time for serial connection to stabilize

    def speed_to_hex(self, percent_speed: float) -> str:
        """
        Convert speed percentage to hexadecimal value
        Args:
            percent_speed (float): Speed in percentage (-100 to 100)
        Returns:
            str: Hexadecimal value with '0x' prefix and 4 digits
        """
        percent_speed = max(min(percent_speed, 100), -100)
        value = int(percent_speed / 100 * 10000)
        if value < 0:
            value = (1 << 16) + value
        return f"0x{value:04x}"

    def calc_crc(self, data: bytes) -> int:
        """
        Calculate CRC16 (Modbus) for the given data
        """
        crc = 0xFFFF
        for pos in data:
            crc ^= pos
            for _ in range(8):
                if crc & 0x0001:
                    crc >>= 1
                    crc ^= 0xA001
                else:
                    crc >>= 1
        return crc & 0xFFFF

    def send_command(self, device_id: int, register_address: int, value: float) -> None:
        """
        Send a command to the controller
        """
        hex_string = self.speed_to_hex(value)
        hex_value = int(hex_string, 16)
        data = struct.pack('>BBHH', device_id, self.FUNCTION_CODE_WRITE, register_address, hex_value)
        crc = self.calc_crc(data)
        packet = data + struct.pack('<H', crc)

        GPIO.output(self.enable_pin, GPIO.HIGH)  # Enable transmit
        time.sleep(0.001)
        self.ser.write(packet)
        self.ser.flush()
        time.sleep(0.001)
        GPIO.output(self.enable_pin, GPIO.LOW)   # Back to receive

    def read_register(self, device_id: int, register_address: int, num_registers: int = 1) -> int:
        """
        Read registers from the controller
        """
        data = struct.pack('>BBHH', device_id, self.FUNCTION_CODE_READ, register_address, num_registers)
        crc = self.calc_crc(data)
        packet = data + struct.pack('<H', crc)

        GPIO.output(self.enable_pin, GPIO.HIGH)  # Enable transmit
        time.sleep(0.001)
        self.ser.write(packet)
        self.ser.flush()
        time.sleep(0.001)
        GPIO.output(self.enable_pin, GPIO.LOW)   # Back to receive

        time.sleep(0.05)
        response = self.ser.read(7)  # Adjust length as needed
        if not response or len(response) < 5:
            raise serial.SerialException("No response or incomplete response received")
        value = struct.unpack('>H', response[3:5])[0]
        return value

    def cleanup(self):
        self.ser.close()
        GPIO.cleanup()
    def send_raw_packet(self, data: bytes):
        crc = self.calc_crc(data)
        packet = data + struct.pack('<H', crc)
        GPIO.output(self.enable_pin, GPIO.HIGH)
        time.sleep(0.001)
        self.ser.write(packet)
        self.ser.flush()
        time.sleep(0.001)
        GPIO.output(self.enable_pin, GPIO.LOW)
        time.sleep(0.05)
    def write_register(self, device_id: int, register_address: int, value: int):
        data = struct.pack('>BBHH', device_id, self.FUNCTION_CODE_WRITE, register_address, value)
        crc = self.calc_crc(data)
        packet = data + struct.pack('<H', crc)
        print(packet)
        GPIO.output(self.enable_pin, GPIO.HIGH)
        time.sleep(0.001)
        self.ser.write(packet)
        self.ser.flush()
        time.sleep(0.001)
        GPIO.output(self.enable_pin, GPIO.LOW)

if __name__ == "__main__":
    controller = StepperController(port="/dev/serial0", enable_pin=18)
    try:
        # Set controller address (example: 0x00 0x06 0x01 0x00 0x00 0x01 + CRC)
        raw_data = bytes([0x00, 0x06, 0x01, 0x00, 0x00, 0x01])
        controller.send_raw_packet(raw_data)
    finally:
        controller.cleanup()     
"""
if __name__ == "__main__":
    controller = StepperController(port="/dev/serial0", enable_pin=18)
    try:
        controller.send_command(1, 0x0000, -35)
        time.sleep(2)
        voltage = controller.read_register(1, 0x0200, 1)
        current = controller.read_register(1, 0x0201, 1)
        speed = controller.read_register(1, 0x0203, 1)
        print(f"Voltage reading: {voltage}")
        print(f"Current reading: {current}")
        print(f"Speed reading: {speed}")
        controller.send_command(1, 0x0000, 0)
    finally:
        controller.cleanup()    
"""
