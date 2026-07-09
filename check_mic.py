import sounddevice as sd
import numpy as np
import time

print("Available audio devices:")
print(sd.query_devices())
print(f"\nDefault input device: {sd.query_devices(kind='input')['name']}")
print("\nListening for 5 seconds - speak now and watch the levels...")

def callback(indata, frames, time, status):
    rms = np.sqrt(np.mean(indata**2))
    bars = int(rms * 500)
    print(f"\r{'█' * bars:<50} RMS: {rms:.4f}", end="", flush=True)

with sd.InputStream(callback=callback, channels=1, samplerate=16000):
    time.sleep(5)

print("\n\nIf you saw bars moving when you spoke, mic is working.")
print("If nothing moved, grant Terminal mic permission in:")
print("System Settings → Privacy & Security → Microphone")
