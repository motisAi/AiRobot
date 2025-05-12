""""
"import cv2
import numpy as np
import face_recognition
import pickle
import os
import time
from datetime import datetime
import pyttsx3  # For text-to-speech
import speech_recognition as sr  # For speech recognition

# Configuration
CAMERA_ID = 2  # Usually 0 for the first USB camera
FACE_DATABASE_FILE = 'known_faces.pkl'
FACES_DIR = 'face_images'
ADMIN_USERS = []  # Add admin usernames here if needed
# Create faces directory if not exists
if not os.path.exists(FACES_DIR):
    os.makedirs(FACES_DIR)

# Initialize text-to-speech engine
def init_tts():
    engine = pyttsx3.init()
    
    # Optional: Set properties (rate, volume, voice)
    engine.setProperty('rate', 150)  # Speed of speech
    engine.setProperty('volume', 0.9)  # Volume (0.0 to 1.0)
    
    # Optional: Set a specific voice
    voices = engine.getProperty('voices')
    # Uncomment to select a specific voice (index may vary by system)
    # engine.setProperty('voice', voices[1].id)  # Usually index 1 is a female voice
    
    return engine

# Initialize speech recognition
def init_speech_recognition():
    return sr.Recognizer()

# Function to speak text
def speak(engine, text):
    print(f"Speaking: {text}")
    engine.say(text)
    engine.runAndWait()

# Function to listen for speech and convert to text
def listen_for_name(recognizer, source, timeout=5):
    print("Listening for name...")
    try:
        audio = recognizer.listen(source, timeout=timeout)
        print("Converting speech to text...")
        text = recognizer.recognize_google(audio)
        print(f"Heard: {text}")
        return text
    except sr.WaitTimeoutError:
        print("Timeout waiting for speech")
        return None
    except sr.UnknownValueError:
        print("Could not understand audio")
        return None
    except sr.RequestError as e:
        print(f"Could not request results; {e}")
        return None

# Load known faces database
def load_known_faces():
    if os.path.exists(FACE_DATABASE_FILE):
        print(f"Loading face database from {FACE_DATABASE_FILE}")
        with open(FACE_DATABASE_FILE, "rb") as f:
            data = pickle.load(f)
            return data.get("encodings", []), data.get("names", [])
    
    print("No existing face database found. Creating new database.")
    return [], []

# Save known faces database
def save_known_faces(known_face_encodings, known_face_names):
    print(f"Saving {len(known_face_names)} faces to database")
    with open(FACE_DATABASE_FILE, "wb") as f:
        pickle.dump({
            "encodings": known_face_encodings,
            "names": known_face_names
        }, f)
    print("Face database saved successfully")

# Add a new face to the database
def add_new_face(frame, name, known_face_encodings, known_face_names):
    # Find all faces in the image
    face_locations = face_recognition.face_locations(frame)
    
    if not face_locations:
        return False, "No faces found in the image", known_face_encodings, known_face_names
    
    # If multiple faces found, use the largest face (assumed to be closest)
    if len(face_locations) > 1:
        # Calculate face area for each detected face
        face_areas = [(right - left) * (bottom - top) for (top, right, bottom, left) in face_locations]
        # Find the index of the largest face
        largest_face_idx = face_areas.index(max(face_areas))
        # Use only the largest face
        face_locations = [face_locations[largest_face_idx]]
    
    # Compute face encoding
    face_encodings = face_recognition.face_encodings(frame, face_locations)
    
    if not face_encodings:
        return False, "Failed to encode face", known_face_encodings, known_face_names
    
    face_encoding = face_encodings[0]
    
    # Check if this face is already in the database
    if known_face_encodings:
        matches = face_recognition.compare_faces(known_face_encodings, face_encoding)
        if True in matches:
            match_index = matches.index(True)
            existing_name = known_face_names[match_index]
            
            if existing_name == name:
                return False, f"{name} is already in the database", known_face_encodings, known_face_names
            else:
                return False, f"This face is already in the database as {existing_name}", known_face_encodings, known_face_names
    
    # Add the new face to the database
    known_face_encodings.append(face_encoding)
    known_face_names.append(name)
    
    # Save an image of the face for reference
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    face_img_path = os.path.join(FACES_DIR, f"{name}_{timestamp}.jpg")
    
    # Extract the face region and save it
    (top, right, bottom, left) = face_locations[0]
    face_img = frame[top:bottom, left:right]
    cv2.imwrite(face_img_path, face_img)
    
    # Save the updated database
    save_known_faces(known_face_encodings, known_face_names)
    
    return True, f"Added {name} to the database", known_face_encodings, known_face_names

# Identify faces in a frame
def identify_faces(frame, known_face_encodings, known_face_names):
    # If we have no faces in the database, return empty results
    if not known_face_encodings:
        return [], []
    
    # Find all faces in the image
    face_locations = face_recognition.face_locations(frame)
    
    # If no faces found, return empty results
    if not face_locations:
        return [], []
    
    # Compute face encodings for all detected faces
    face_encodings = face_recognition.face_encodings(frame, face_locations)
    
    face_names = []
    for face_encoding in face_encodings:
        # Compare with known faces
        matches = face_recognition.compare_faces(known_face_encodings, face_encoding, tolerance=0.6)
        name = "Unknown"
        
        # If we found a match
        if True in matches:
            # Find the index of the first match
            match_index = matches.index(True)
            name = known_face_names[match_index]
        
        # Or use the face with smallest distance
        else:
            face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)
            if len(face_distances) > 0:
                best_match_index = np.argmin(face_distances)
                # Only use this match if the distance is below a threshold
                if face_distances[best_match_index] < 0.7:
                    name = known_face_names[best_match_index]
        
        face_names.append(name)
    
    return face_locations, face_names

def main():
    # Load known faces database
    known_face_encodings, known_face_names = load_known_faces()
    print(f"Loaded {len(known_face_names)} faces from database")
    
    # Initialize text-to-speech
    tts_engine = init_tts()
    
    # Initialize speech recognition
    recognizer = init_speech_recognition()
    
    # Initialize microphone
    #mic = sr.Microphone()
    mic = sr.Microphone(device_index=1)
    
    # Adjust for ambient noise
    print("Adjusting for ambient noise...")
    with mic as source:
        
        recognizer.adjust_for_ambient_noise(source, duration=1)
    
    # Initialize camera
    try:
        cap = cv2.VideoCapture(CAMERA_ID)
        
        # Check if camera opened successfully
        if not cap.isOpened():
            print("Error: Could not open camera.")
            return
        
        # Set resolution (optional)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        print(f"Camera initialized with resolution: {cap.get(cv2.CAP_PROP_FRAME_WIDTH)}x{cap.get(cv2.CAP_PROP_FRAME_HEIGHT)}")
    except Exception as e:
        print(f"Error initializing camera: {e}")
        return
    
    # Create window for display
    cv2.namedWindow('Face Recognition', cv2.WINDOW_NORMAL)
    
    # Variables for program control
    running = True
    learning_mode = False
    new_face_name = ""
    frame_count = 0
    
    # Variables for greeting control
    last_greeting_time = {}  # Dictionary to store last greeting time for each person
    greeting_interval = 60   # Only greet the same person once per minute
    
    # Variable to track if we're currently asking "Who are you?"
    asking_for_name = False
    unknown_face_location = None
    
    print("System ready. Press:")
    print("  'q' to quit")
    print("  'l' to enter learning mode manually")
    print("  'a' to add the current face with the specified name")
    
    speak(tts_engine, "Face recognition system is ready")
    
    while running:
        # Read a frame from the camera
        ret, frame = cap.read()
        
        if not ret:
            print("Error: Failed to capture image from camera")
            break
        
        # Store current frame for learning
        current_frame = frame.copy()
        
        # Process every 3rd frame to reduce CPU load
        frame_count += 1
        process_this_frame = (frame_count % 3 == 0)
        
        if process_this_frame:
            # Identify faces in the frame
            face_locations, face_names = identify_faces(frame, known_face_encodings, known_face_names)
            
            # Process each identified face
            current_time = time.time()
            for (top, right, bottom, left), name in zip(face_locations, face_names):
                # Draw a box around the face
                cv2.rectangle(frame, (left, top), (right, bottom), (0, 0, 255), 2)
                
                # Draw a filled rectangle below the face for the name label
                cv2.rectangle(frame, (left, bottom - 35), (right, bottom), (0, 0, 255), cv2.FILLED)
                
                # Draw the name text
                cv2.putText(frame, name, (left + 6, bottom - 6), cv2.FONT_HERSHEY_DUPLEX, 
                            0.8, (255, 255, 255), 1)
                
                # Greeting logic
                if not asking_for_name:  # Don't greet if we're in the middle of asking for a name
                    if name != "Unknown":
                        # Check if we haven't greeted this person recently
                        if name not in last_greeting_time or (current_time - last_greeting_time[name]) > greeting_interval:
                            greeting_hour = datetime.now().hour
                            if greeting_hour>=5 and greeting_hour<12:
                                speak(tts_engine, f"Good morning {name} nice to see you again")
                            elif greeting_hour>=12 and greeting_hour<18:
                                speak(tts_engine, f"Good afternoon {name} nice to see you again")
                            elif greeting_hour>=18 and greeting_hour<22:
                                speak(tts_engine, f"Good evening {name} nice to see you again")
                            else: speak(tts_engine, f"good night {name} nice to see you again")        
                           
                            last_greeting_time[name] = current_time
                    elif not learning_mode and not asking_for_name:
                        # Save this unknown face location for the "Who are you?" question
                        if unknown_face_location is None:
                            unknown_face_location = (top, right, bottom, left)
                            # Ask who they are, but don't try to listen yet
                            speak(tts_engine, "i see a new face, what is your name please? ")
                            asking_for_name = True
            
            # If we're asking for a name and no interaction has started yet
            if asking_for_name and not learning_mode:
                cv2.putText(frame, "Please say your name", (10, 30), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                
                # Show the image with the instruction before listening
                cv2.imshow('Face Recognition', frame)
                cv2.waitKey(1)
                
                # Now listen for the name
                with mic as source:
                    name = listen_for_name(recognizer, source)
                
                if name:
                    # Extract the face for the database (using saved location)
                    if unknown_face_location:
                        top, right, bottom, left = unknown_face_location
                        # Capture a new frame to ensure it's current
                        ret, learning_frame = cap.read()
                        if ret:
                            # Add the face to the database
                            success, message, known_face_encodings, known_face_names = add_new_face(
                                learning_frame, name, known_face_encodings, known_face_names
                            )
                            print(message)
                            if success:
                                speak(tts_engine, f"Thank you {name}, I'll remember you")
                            else:
                                speak(tts_engine, message)
                
                # Reset the asking state
                asking_for_name = False
                unknown_face_location = None
        
        # If in manual learning mode, display instruction
        if learning_mode:
            cv2.putText(frame, f"Learning: {new_face_name}", (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            cv2.putText(frame, "Press 'a' to add face", (10, 60), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        
        # Show the image
        cv2.imshow('Face Recognition', frame)
        
        # Check for keyboard input
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord('q'):
            # Quit the program
            running = False
        
        elif key == ord('l'):
            # Toggle manual learning mode
            learning_mode = not learning_mode
            if learning_mode:
                print("Learning mode activated. Enter name and press 'a' to add face.")
                new_face_name = input("Enter name for new face: ")
            else:
                print("Learning mode deactivated.")
        
        elif key == ord('a') and learning_mode and new_face_name:
            # Add the current face in learning mode
            success, message, known_face_encodings, known_face_names = add_new_face(
                current_frame, new_face_name, known_face_encodings, known_face_names
            )
            print(message)
            
            if success:
                speak(tts_engine, f"Face added for {new_face_name}")
                # Exit learning mode after successful addition
                learning_mode = False
    
    # Clean up
    cap.release()
    cv2.destroyAllWindows()
    print("Program terminated")

if __name__ == "__main__":
    main()"
 """
import cv2
import numpy as np
import face_recognition
import pickle
import os
import time
from datetime import datetime
import pyttsx3
import speech_recognition as sr
import threading
import random

# Import our custom classes
from serial_communication import SerialCommunication
from continuous_voice_listener import ContinuousVoiceListener

# Configuration
CAMERA_ID = 0  # Usually 0 for the first USB camera
FACE_DATABASE_FILE = 'known_faces.pkl'
FACES_DIR = 'face_images'
CONVERSATION_HISTORY_DIR = 'conversation_history'
SERIAL_PORT = 'COM3'  # Change to your actual serial port
MICROPHONE_INDEX = 1  # Set to a specific index or None for default
TRIGGER_WORDS = ["hey robot", "robot", "hello", "hey system"]

# Create necessary directories
if not os.path.exists(FACES_DIR):
    os.makedirs(FACES_DIR)
if not os.path.exists(CONVERSATION_HISTORY_DIR):
    os.makedirs(CONVERSATION_HISTORY_DIR)

# Initialize text-to-speech engine
def init_tts():
    engine = pyttsx3.init()
    engine.setProperty('rate', 150)
    engine.setProperty('volume', 0.9)
    return engine

# Initialize speech recognition for short targeted recordings
def init_speech_recognition():
    return sr.Recognizer()

# Function to speak text
def speak(engine, text):
    print(f"AI: {text}")
    engine.say(text)
    engine.runAndWait()

# Function to listen for speech and convert to text (for specific interactions)
def listen_for_speech(recognizer, source, timeout=5, phrase_time_limit=None):
    print("Listening...")
    try:
        audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
        print("Processing speech...")
        text = recognizer.recognize_google(audio)
        print(f"You said: {text}")
        return text
    except sr.WaitTimeoutError:
        print("Timeout waiting for speech")
        return None
    except sr.UnknownValueError:
        print("Could not understand audio")
        return None
    except sr.RequestError as e:
        print(f"Could not request results; {e}")
        return None

# Load known faces database
def load_known_faces():
    if os.path.exists(FACE_DATABASE_FILE):
        print(f"Loading face database from {FACE_DATABASE_FILE}")
        with open(FACE_DATABASE_FILE, "rb") as f:
            data = pickle.load(f)
            return data.get("encodings", []), data.get("names", [])
    
    print("No existing face database found. Creating new database.")
    return [], []

# Save known faces database
def save_known_faces(known_face_encodings, known_face_names):
    print(f"Saving {len(known_face_names)} faces to database")
    with open(FACE_DATABASE_FILE, "wb") as f:
        pickle.dump({
            "encodings": known_face_encodings,
            "names": known_face_names
        }, f)
    print("Face database saved successfully")

# Load conversation history for a specific user
def load_conversation_history(user_name):
    history_file = os.path.join(CONVERSATION_HISTORY_DIR, f"{user_name}_history.pkl")
    if os.path.exists(history_file):
        with open(history_file, "rb") as f:
            return pickle.load(f)
    return []

# Save conversation history for a specific user
def save_conversation_history(user_name, conversation):
    history_file = os.path.join(CONVERSATION_HISTORY_DIR, f"{user_name}_history.pkl")
    with open(history_file, "wb") as f:
        pickle.dump(conversation, f)

# Handle ESP32 responses - will be passed as a callback to SerialCommunication
def handle_esp32_response(response, tts_engine):
    """
    Process responses from ESP32 and speak them.
    This function will be called whenever a new response is received.
    
    Args:
        response (str): The response from ESP32
        tts_engine: Text-to-speech engine to use for speaking
    """
    # Simply speak the response as-is
    speak(tts_engine, response)

# Simple rule-based response generation
def generate_response(user_input, user_name=None, serial_comm=None):
    # Convert to lowercase for easier matching
    user_input_lower = user_input.lower()
    
    # Check for device commands first
    if serial_comm:
        # Check for light-related commands
        if any(phrase in user_input_lower for phrase in ["turn on the light", "light on", "lights on"]):
            command = "lightOn"
            serial_comm.send_command(command)
            return "I'm sending the command to turn the light on."
            
        if any(phrase in user_input_lower for phrase in ["turn off the light", "light off", "lights off"]):
            command = "lightOff"
            serial_comm.send_command(command)
            return "I'm sending the command to turn the light off."
            
        # Check for temperature inquiry
        if any(phrase in user_input_lower for phrase in ["temperature", "how hot", "how cold"]):
            command = "getTemp"
            serial_comm.send_command(command)
            return "I'm checking the temperature for you. Please wait a moment."
    
    # Greeting patterns
    if any(greeting in user_input_lower for greeting in ["hello", "hi ", "hey", "greetings"]):
        return random.choice([
            f"Hello{' ' + user_name if user_name else ''}! How can I help you today?",
            f"Hi{' ' + user_name if user_name else ''}! Nice to see you!",
            f"Hey there{' ' + user_name if user_name else ''}! How are you doing?"
        ])
    
    # Questions about the AI
    if "your name" in user_input_lower or "who are you" in user_input_lower:
        return "I'm your assistant, a computer vision and voice interactive AI created to help you."
    
    if "what can you do" in user_input_lower or "your abilities" in user_input_lower:
        return "I can recognize faces, chat with you, control devices, and perform various tasks. I'm still learning, but I'm here to assist you."
    
    # Time related
    if "time" in user_input_lower:
        current_time = datetime.now().strftime("%I:%M %p")
        return f"The current time is {current_time}."
    
    if "date" in user_input_lower:
        current_date = datetime.now().strftime("%A, %B %d, %Y")
        return f"Today is {current_date}."
    
    # Personal information
    if user_name and "my name" in user_input_lower:
        return f"Your name is {user_name}, according to my facial recognition system."
    
    # Farewell patterns
    if any(farewell in user_input_lower for farewell in ["bye", "goodbye", "see you", "later"]):
        return random.choice([
            f"Goodbye{' ' + user_name if user_name else ''}! Have a great day!",
            "See you later! Take care!",
            "Bye for now! Come back soon!"
        ])
    
    # Default responses if no pattern matches
    return random.choice([
        "I'm not sure I understand. Could you rephrase that?",
        "Interesting. Tell me more about that.",
        "I'm still learning. Can you elaborate?",
        "I don't have information about that yet.",
        "That's a good question. I'm afraid I don't have a specific answer right now."
    ])

# Process voice commands from continuous listener
def process_voice_command(command, tts_engine, current_user, serial_comm, known_face_encodings, known_face_names):
    """
    Process voice commands received from the continuous listener.
    
    Args:
        command (str): The voice command to process
        tts_engine: Text-to-speech engine
        current_user (str): Current recognized user, if any
        serial_comm: Serial communication object
        known_face_encodings: Known face encodings database
        known_face_names: Known face names database
        
    Returns:
        bool: True if the command was processed, False otherwise
    """
    print(f"Processing voice command: {command}")
    
    # If the command is empty, ignore it
    if not command or command.isspace():
        return False
    
    # Generate a response based on the command
    response = generate_response(command, current_user, serial_comm)
    
    # Speak the response
    speak(tts_engine, response)
    
    # If we have a current user, save this to conversation history
    if current_user:
        history = load_conversation_history(current_user)
        history.append({"user": command, "ai": response})
        save_conversation_history(current_user, history)
    
    return True

# Add a new face to the database
def add_new_face(frame, name, known_face_encodings, known_face_names):
    # Face detection and encoding logic
    face_locations = face_recognition.face_locations(frame)
    
    if not face_locations:
        return False, "No faces found in the image", known_face_encodings, known_face_names
    
    # If multiple faces found, use the largest face
    if len(face_locations) > 1:
        face_areas = [(right - left) * (bottom - top) for (top, right, bottom, left) in face_locations]
        largest_face_idx = face_areas.index(max(face_areas))
        face_locations = [face_locations[largest_face_idx]]
    
    # Compute face encoding
    face_encodings = face_recognition.face_encodings(frame, face_locations)
    
    if not face_encodings:
        return False, "Failed to encode face", known_face_encodings, known_face_names
    
    face_encoding = face_encodings[0]
    
    # Check if this face is already in the database
    if known_face_encodings:
        matches = face_recognition.compare_faces(known_face_encodings, face_encoding)
        if True in matches:
            match_index = matches.index(True)
            existing_name = known_face_names[match_index]
            
            if existing_name == name:
                return False, f"{name} is already in the database", known_face_encodings, known_face_names
            else:
                return False, f"This face is already in the database as {existing_name}", known_face_encodings, known_face_names
    
    # Add the new face to the database
    known_face_encodings.append(face_encoding)
    known_face_names.append(name)
    
    # Save an image of the face for reference
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    face_img_path = os.path.join(FACES_DIR, f"{name}_{timestamp}.jpg")
    
    # Extract the face region and save it
    (top, right, bottom, left) = face_locations[0]
    face_img = frame[top:bottom, left:right]
    cv2.imwrite(face_img_path, face_img)
    
    # Save the updated database
    save_known_faces(known_face_encodings, known_face_names)
    
    return True, f"Added {name} to the database", known_face_encodings, known_face_names

# Identify faces in a frame
def identify_faces(frame, known_face_encodings, known_face_names):
    # Face identification logic
    if not known_face_encodings:
        return [], []
    
    face_locations = face_recognition.face_locations(frame)
    
    if not face_locations:
        return [], []
    
    face_encodings = face_recognition.face_encodings(frame, face_locations)
    
    face_names = []
    for face_encoding in face_encodings:
        matches = face_recognition.compare_faces(known_face_encodings, face_encoding, tolerance=0.6)
        name = "Unknown"
        
        if True in matches:
            match_index = matches.index(True)
            name = known_face_names[match_index]
        else:
            face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)
            if len(face_distances) > 0:
                best_match_index = np.argmin(face_distances)
                if face_distances[best_match_index] < 0.7:
                    name = known_face_names[best_match_index]
        
        face_names.append(name)
    
    return face_locations, face_names

def main():
    # Load known faces database
    known_face_encodings, known_face_names = load_known_faces()
    print(f"Loaded {len(known_face_names)} faces from database")
    
    # Initialize text-to-speech
    tts_engine = init_tts()
    
    # Initialize speech recognition for targeted listening
    recognizer = init_speech_recognition()
    
    # Initialize microphone for targeted listening
    mic = sr.Microphone(device_index=MICROPHONE_INDEX)
    
    # Initialize serial communication
    serial_comm = SerialCommunication(port=SERIAL_PORT)
    if not serial_comm.connect():
        print("Warning: Failed to connect to ESP32. Continuing without device control.")
    else:
        # Set up callback for ESP32 responses
        serial_comm.set_response_callback(
            lambda response: handle_esp32_response(response, tts_engine)
        )
    
    # Initialize continuous voice listener
    listener = ContinuousVoiceListener(
        device_index=MICROPHONE_INDEX,
        trigger_words=["hey robot", "robot", "hello", "hey system"]
    )
    
    # Start the continuous listener
    if not listener.start():
        print("Warning: Failed to start continuous voice listener. Voice commands will not be available.")
    
    # Adjust for ambient noise (for targeted listening)
    print("Adjusting for ambient noise for targeted listening...")
    with mic as source:
        recognizer.adjust_for_ambient_noise(source, duration=1)
    
    # Initialize camera
    try:
        cap = cv2.VideoCapture(CAMERA_ID)
        
        # Check if camera opened successfully
        if not cap.isOpened():
            print("Error: Could not open camera.")
            return
        
        # Set resolution (optional)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        print(f"Camera initialized with resolution: {cap.get(cv2.CAP_PROP_FRAME_WIDTH)}x{cap.get(cv2.CAP_PROP_FRAME_HEIGHT)}")
    except Exception as e:
        print(f"Error initializing camera: {e}")
        return
    
    # Create window for display
    cv2.namedWindow('Face Recognition', cv2.WINDOW_NORMAL)
    
    # Variables for program control
    running = True
    learning_mode = False
    conversation_mode = False
    current_user = None
    new_face_name = ""
    frame_count = 0
    
    # Variables for greeting control
    last_greeting_time = {}  # Dictionary to store last greeting time for each person
    greeting_interval = 60   # Only greet the same person once per minute
    
    # Variable to track if we're currently asking "Who are you?"
    asking_for_name = False
    unknown_face_location = None
    
    # Variable for conversation history
    conversation_history = []
    
    print("System ready. Press:")
    print("  'q' to quit")
    print("  'l' to enter learning mode manually")
    print("  'a' to add the current face with the specified name")
    print("  'c' to start a conversation with the AI")
    print(f"Or say one of the trigger words: {', '.join(TRIGGER_WORDS)} followed by your command")
    
    speak(tts_engine, "Face recognition and interactive AI system is ready. You can speak to me by saying a trigger word first.")
    
    while running:
        # Check for voice commands from the continuous listener
        command = listener.get_command(block=False)
        if command:
            process_voice_command(command, tts_engine, current_user, serial_comm, known_face_encodings, known_face_names)
        
        # Read a frame from the camera
        ret, frame = cap.read()
        
        if not ret:
            print("Error: Failed to capture image from camera")
            break
        
        # Store current frame for learning
        current_frame = frame.copy()
        
        # Process every 3rd frame to reduce CPU load
        frame_count += 1
        process_this_frame = (frame_count % 3 == 0)
        
        # Keep track of the current recognized user (if any)
        current_recognized_user = None
        
        if process_this_frame:
            # Identify faces in the frame
            face_locations, face_names = identify_faces(frame, known_face_encodings, known_face_names)
            
            # Process each identified face
            current_time = time.time()
            for (top, right, bottom, left), name in zip(face_locations, face_names):
                # Draw a box around the face
                cv2.rectangle(frame, (left, top), (right, bottom), (0, 0, 255), 2)
                
                # Draw a filled rectangle below the face for the name label
                cv2.rectangle(frame, (left, bottom - 35), (right, bottom), (0, 0, 255), cv2.FILLED)
                
                # Draw the name text
                cv2.putText(frame, name, (left + 6, bottom - 6), cv2.FONT_HERSHEY_DUPLEX, 
                            0.8, (255, 255, 255), 1)
                
                # Update current recognized user (take the first known face)
                if name != "Unknown" and current_recognized_user is None:
                    current_recognized_user = name
                
                # Greeting logic
                if not asking_for_name and not conversation_mode:  # Don't greet if we're in conversation
                    if name != "Unknown":
                        # Check if we haven't greeted this person recently
                        if name not in last_greeting_time or (current_time - last_greeting_time[name]) > greeting_interval:
                            speak(tts_engine, f"Hello {name}")
                            last_greeting_time[name] = current_time
                    elif not learning_mode and not asking_for_name:
                        # Save this unknown face location for the "Who are you?" question
                        if unknown_face_location is None:
                            unknown_face_location = (top, right, bottom, left)
                            # Ask who they are, but don't try to listen yet
                            speak(tts_engine, "Who are you?")
                            asking_for_name = True
        
        # Update the current user for conversation
        if current_recognized_user:
            current_user = current_recognized_user
        
        # If we're asking for a name and no interaction has started yet
        if asking_for_name and not learning_mode:
            cv2.putText(frame, "Please say your name", (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            
            # Show the image with the instruction before listening
            cv2.imshow('Face Recognition', frame)
            cv2.waitKey(1)
            
            # Now listen for the name
            with mic as source:
                name = listen_for_speech(recognizer, source)
            
            if name:
                # Extract the face for the database (using saved location)
                if unknown_face_location:
                    top, right, bottom, left = unknown_face_location
                    # Capture a new frame to ensure it's current
                    ret, learning_frame = cap.read()
                    if ret:
                        # Add the face to the database
                        success, message, known_face_encodings, known_face_names = add_new_face(
                            learning_frame, name, known_face_encodings, known_face_names
                        )
                        print(message)
                        if success:
                            speak(tts_engine, f"Thank you {name}, I'll remember you")
                            current_user = name  # Set the current user
                        else:
                            speak(tts_engine, message)
            
            # Reset the asking state
            asking_for_name = False
            unknown_face_location = None
        
        # Conversation mode - activated by 'c' key or by voice command
        if conversation_mode and current_user:
            cv2.putText(frame, f"Conversation mode with {current_user}", (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            cv2.putText(frame, "Say something or press 'c' to exit", (10, 60), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            
            # Show the image before listening
            cv2.imshow('Face Recognition', frame)
            cv2.waitKey(1)
            
            # Listen for user input
            with mic as source:
                user_input = listen_for_speech(recognizer, source, timeout=10, phrase_time_limit=10)
            
            if user_input:
                # Check for exit commands
                if user_input.lower() in ["exit", "quit", "end conversation", "stop"]:
                    conversation_mode = False
                    speak(tts_engine, "Ending our conversation. See you later!")
                    continue
                
                # Check if it's a command for ESP32
                esp32_command = None
                if serial_comm:
                    esp32_command = serial_comm.translate_voice_command(user_input)
                    if esp32_command:
                        serial_comm.send_command(esp32_command)
                
                # Get AI response
                ai_response = generate_response(user_input, current_user, serial_comm)
                
                # Add to conversation history
                conversation_history.append({"user": user_input, "ai": ai_response})
                
                # Save conversation history
                save_conversation_history(current_user, conversation_history)
                
                # Speak the response
                speak(tts_engine, ai_response)
        
        # If in manual learning mode, display instruction
        if learning_mode:
            cv2.putText(frame, f"Learning: {new_face_name}", (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            cv2.putText(frame, "Press 'a' to add face", (10, 60), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        
# Show status of continuous listening
        cv2.putText(frame, "Voice listening active", (10, frame.shape[0] - 10), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        
        # Show the image
        cv2.imshow('Face Recognition', frame)
        
        # Check for keyboard input
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord('q'):
            # Quit the program
            running = False
        
        elif key == ord('l'):
            # Toggle manual learning mode
            learning_mode = not learning_mode
            if learning_mode:
                print("Learning mode activated. Enter name and press 'a' to add face.")
                new_face_name = input("Enter name for new face: ")
            else:
                print("Learning mode deactivated.")
        
        elif key == ord('a') and learning_mode and new_face_name:
            # Add the current face in learning mode
            success, message, known_face_encodings, known_face_names = add_new_face(
                current_frame, new_face_name, known_face_encodings, known_face_names
            )
            print(message)
            
            if success:
                speak(tts_engine, f"Face added for {new_face_name}")
                # Exit learning mode after successful addition
                learning_mode = False
        
        elif key == ord('c'):
            # Toggle conversation mode
            conversation_mode = not conversation_mode
            
            if conversation_mode:
                if current_user:
                    # Load conversation history for this user
                    conversation_history = load_conversation_history(current_user)
                    speak(tts_engine, f"Starting conversation with {current_user}. How can I help you today?")
                else:
                    speak(tts_engine, "I don't know who you are. Let me recognize your face first.")
                    conversation_mode = False
            else:
                speak(tts_engine, "Ending conversation mode.")
    
    # Clean up
    if listener:
        listener.stop()
    if serial_comm:
        serial_comm.disconnect()
    cap.release()
    cv2.destroyAllWindows()
    print("Program terminated")

if __name__ == "__main__":
    main()