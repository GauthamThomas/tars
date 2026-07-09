"""Audio playback and reaction handler."""

import time
import numpy as np
from pathlib import Path

AUDIO_DIR = Path(__file__).parent / "audio"

# Initialize pygame mixer lazily
_pygame_initialized = False


def _ensure_pygame():
    """Initialize pygame mixer if not already done."""
    global _pygame_initialized
    if not _pygame_initialized:
        import pygame
        try:
            pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
        except Exception:
            pygame.mixer.init()
        _pygame_initialized = True


def _play_beep():
    """Generate and play a simple sine wave beep using numpy and pygame."""
    _ensure_pygame()
    import pygame

    sample_rate = 22050
    duration = 0.3
    frequency = 440.0

    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    wave = 0.3 * np.sin(2 * np.pi * frequency * t)
    # Apply envelope to avoid clicks
    envelope = np.ones_like(wave)
    fade_len = int(sample_rate * 0.02)
    envelope[:fade_len] = np.linspace(0, 1, fade_len)
    envelope[-fade_len:] = np.linspace(1, 0, fade_len)
    wave = wave * envelope

    # Convert to 16-bit PCM
    wave_int16 = (wave * 32767).astype(np.int16)
    # Make stereo by stacking
    stereo = np.stack([wave_int16, wave_int16], axis=1)

    try:
        sound = pygame.sndarray.make_sound(stereo)
        sound.play()
    except Exception:
        pass  # If beep fails, silently continue


def play_response(audio_filename: str):
    """Play an audio file from the audio/ directory. Non-blocking.

    If the file doesn't exist, plays a beep instead.
    Never crashes - silently handles all errors.
    """
    try:
        audio_path = AUDIO_DIR / audio_filename
        if not audio_path.exists():
            _play_beep()
            return

        _ensure_pygame()
        import pygame

        sound = pygame.mixer.Sound(str(audio_path))
        sound.play()

        # Don't wait - return immediately so listening continues
    except Exception:
        # Last resort: try beep
        try:
            _play_beep()
        except Exception:
            pass