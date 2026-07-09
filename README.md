# TARS - Ambient Semantic Listener

TARS is a background Python application that listens continuously to your microphone, transcribes everything it hears in real time, and displays it as a live scrolling stream in a beautiful terminal UI. When it detects that someone said something semantically matching a trigger phrase, it plays an audio response and displays a reaction on screen. No wake word. No button. No user interaction. It just runs.

## How it works

TARS runs a four-stage pipeline entirely on your local machine. The microphone captures audio in 100ms chunks using sounddevice. An energy-based voice activity detector (RMS threshold) identifies speech segments, and when silence is detected for 0.8 seconds, the utterance is transcribed using OpenAI Whisper (tiny.en model) via faster-whisper. Each completed sentence is passed to a Needle semantic classifier, which compares it against your trigger library using a small LLM. If a semantic match is found, TARS plays an audio response, highlights the matched sentence in the transcript, and shows a reaction panel. The display is built with Rich and updates 10 times per second.

## Installation

```bash
git clone <repo>
cd tars
python -m venv venv
source venv/bin/activate        # Mac/Linux
venv\Scripts\activate           # Windows
pip install -r requirements.txt
python main.py
```

## First run

On first run, Needle model weights (~50MB) download automatically to `~/.tars/needle.pkl`. The Whisper tiny.en model (~150MB) downloads on first use as well. Both models cache locally and load on subsequent runs without downloading.

## Adding triggers

Triggers are defined in `triggers.yaml`. Each trigger has:

- **name**: Unique identifier
- **description**: What phrases to match (used by the semantic classifier)
- **audio**: Filename of the audio file to play (in `audio/` directory)
- **reaction**: Text displayed in the reaction panel
- **color**: Rich-compatible color name for highlighting
- **cooldown**: Seconds before the same trigger can fire again

TARS automatically reloads `triggers.yaml` every 30 seconds, so you can edit it while TARS is running and changes take effect without restarting. You can also press **R** to force an immediate reload.

## Adding audio

See `audio/README.txt` for details. Place `.wav` or `.mp3` files in the `audio/` directory and reference them by filename in `triggers.yaml`. If a file is missing, TARS plays a beep instead so triggers still fire audibly.

## Microphone permissions

### macOS
System Settings → Privacy & Security → Microphone → add Terminal (or your terminal app)

### Windows
Settings → Privacy → Microphone → allow desktop apps to access the microphone

## Keyboard shortcuts

| Key | Action |
|-----|--------|
| P | Pause/resume listening (mic stays open, transcriptions discarded) |
| Q | Quit TARS |
| R | Force-reload triggers.yaml immediately |

## Limitations

- **Latency**: 1-2 second delay on modern Mac hardware, 3-4 seconds on slower machines. This is inherent to running Whisper locally.
- **Accuracy**: Whisper tiny.en works best with clear, confident speech. Heavy accents, background noise, or very quiet speech may produce poor transcriptions.
- **Semantic matching**: Needle is a small model and may occasionally miss matches or produce false positives. The system is tuned to err on the side of no_match.
- **Single language**: English only (tiny.en model).
- **Resource usage**: ~200MB RAM total (Whisper ~150MB, Needle ~50MB). Under 5% CPU on modern hardware.

## Privacy

All audio processing happens entirely on your machine. No audio is ever saved to disk or sent over the network. The microphone stream is processed in memory and discarded immediately after transcription.