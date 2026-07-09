import threading
import queue
import time
import yaml
import sys
from pathlib import Path

from listener import start_listening
from classifier import TARSClassifier
from display import TARSDisplay
from reactor import play_response
from rich.live import Live

TRIGGERS_PATH = Path(__file__).parent / "triggers.yaml"


def load_triggers():
    with open(TRIGGERS_PATH) as f:
        return yaml.safe_load(f)["triggers"]


def _key_listener(display: TARSDisplay, stop_event: threading.Event, reload_flag: list):
    """Reads single keypresses in raw mode. Unix only; degrades gracefully on Windows."""
    try:
        import termios, tty
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            while not stop_event.is_set():
                ch = sys.stdin.read(1)
                if ch in ("q", "Q", "\x03"):   # Q or Ctrl+C
                    stop_event.set()
                elif ch in ("p", "P"):
                    display.toggle_pause()
                elif ch in ("r", "R"):
                    reload_flag[0] = True
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
    except Exception:
        # Windows or non-TTY - keyboard shortcuts unavailable, Ctrl+C still works
        pass


def main():
    tq = queue.Queue()
    pq = queue.Queue(maxsize=20)
    stop = threading.Event()
    reload_flag = [False]

    classifier = TARSClassifier()
    triggers = load_triggers()
    last_reload = time.time()
    display = TARSDisplay()

    threading.Thread(
        target=start_listening, args=(tq, pq, stop), daemon=True
    ).start()
    threading.Thread(
        target=_key_listener, args=(display, stop, reload_flag), daemon=True
    ).start()

    with Live(display.render(), refresh_per_second=10, screen=True) as live:
        while not stop.is_set():

            # Hot-reload triggers
            if reload_flag[0] or time.time() - last_reload > 30:
                try:
                    triggers = load_triggers()
                    last_reload = time.time()
                    reload_flag[0] = False
                except Exception:
                    pass

            # Drain partial queue (live transcription preview)
            while True:
                try:
                    kind, text = pq.get_nowait()
                    if kind == "partial":
                        display.set_partial(text)
                        display.status = "processing"
                    elif kind == "final":
                        display.set_partial("")
                        display.status = "listening"
                except queue.Empty:
                    break

            # Process completed sentences
            try:
                sentence = tq.get_nowait()
                name = classifier.classify(sentence, triggers)

                if name:
                    t = next(x for x in triggers if x["name"] == name)
                    color = t.get("color", "white")
                    reaction = t.get("reaction", name.upper())

                    display.add_sentence(sentence, name, color)
                    display.show_reaction(reaction, color)
                    display.triggers_fired += 1
                    display.status = "fired"

                    audio = t.get("audio")
                    if audio:
                        threading.Thread(
                            target=play_response, args=(audio,), daemon=True
                        ).start()
                else:
                    display.add_sentence(sentence)
                    display.status = "listening"

            except queue.Empty:
                pass

            live.update(display.render())
            time.sleep(0.05)

    stop.set()
    print("\nTARS offline.\n")


if __name__ == "__main__":
    main()
