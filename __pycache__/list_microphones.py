import sounddevice as sd

def list_microphones():
    print("Available input devices (microphones):")
    devices = sd.query_devices()
    for idx, device in enumerate(devices):
        if device['max_input_channels'] > 0:
            print(f"Index: {idx}")
            print(f"  Name: {device['name']}")
            print(f"  Default Sample Rate: {device['default_samplerate']}")
            print(f"  Max Input Channels: {device['max_input_channels']}")
            print("-" * 40)

if __name__ == "__main__":
    list_microphones()