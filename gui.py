import tkinter as tk
import threading
import queue
import time
import yaml
from pathlib import Path
from listener import start_listening
from classifier import TARSClassifier

TRIGGERS_PATH = Path(__file__).parent / "triggers.yaml"

BG         = "#0d0d0d"
FG_PARTIAL = "#2e2e2e"
FG_LATEST  = "#f0f0f0"
GOLD       = "#ffd700"
FONT       = "Menlo"

def load_triggers():
    with open(TRIGGERS_PATH) as f:
        return yaml.safe_load(f)["triggers"]


class TARS:
    HISTORY_FONTS = [40, 30, 22, 17, 14, 12]
    HISTORY_COLS  = ["#dddddd","#999999","#777777","#555555","#404040","#303030"]

    def __init__(self, root):
        self.root = root
        self.root.title("TARS")
        self.root.configure(bg=BG)
        self.root.attributes("-fullscreen", True)
        self.root.bind("<Escape>", lambda e: self.root.attributes("-fullscreen", False))
        self.root.bind("<F11>",    lambda e: self.root.attributes("-fullscreen", True))
        self.root.bind("<q>",      lambda e: self.shutdown())

        self._build()

        self.tq   = queue.Queue()
        self.pq   = queue.Queue(maxsize=20)
        self.stop = threading.Event()
        self.history = []
        self._overlay_job = None
        self._last_reload = time.time()

        self.classifier = TARSClassifier()
        self.triggers   = load_triggers()

        threading.Thread(target=start_listening,
                         args=(self.tq, self.pq, self.stop),
                         daemon=True).start()
        self.root.after(20, self._poll)

    def _build(self):
        sw = self.root.winfo_screenwidth()

        # header
        tk.Label(self.root, text="▶  T A R S",
                 font=(FONT, 13, "bold"), bg=BG, fg="#1e5555",
                 anchor="w", padx=24, pady=6).pack(fill="x")

        # giant partial text
        self.partial_var = tk.StringVar()
        self.partial_lbl = tk.Label(
            self.root, textvariable=self.partial_var,
            font=(FONT, 80, "bold"), bg=BG, fg=FG_PARTIAL,
            anchor="w", padx=28, pady=12,
            wraplength=sw - 60, justify="left")
        self.partial_lbl.pack(fill="x")

        # divider
        tk.Frame(self.root, bg="#1c1c1c", height=1).pack(fill="x", padx=20)

        # history
        self.hist_frame = tk.Frame(self.root, bg=BG)
        self.hist_frame.pack(fill="both", expand=True, padx=24, pady=14)

        # trigger overlay (hidden)
        self.overlay = tk.Frame(self.root, bg=BG)
        self.overlay_lbl = tk.Label(
            self.overlay, text="",
            font=(FONT, 82, "bold"), bg=BG, fg=GOLD,
            wraplength=sw - 80, justify="center")
        self.overlay_lbl.place(relx=0.5, rely=0.45, anchor="center")
        # click overlay to dismiss
        self.overlay.bind("<Button-1>", lambda e: self._hide_trigger())
        self.overlay_lbl.bind("<Button-1>", lambda e: self._hide_trigger())

    def _poll(self):
        if time.time() - self._last_reload > 30:
            try: self.triggers = load_triggers(); self._last_reload = time.time()
            except: pass

        # partial updates
        while True:
            try:
                kind, text = self.pq.get_nowait()
                if kind == "partial":
                    self.partial_var.set(text)
                else:
                    self.partial_var.set("")
            except queue.Empty:
                break

        # final sentence
        try:
            s = self.tq.get_nowait()
            self._add(s)
            name = self.classifier.classify(s, self.triggers)
            if name:
                t = next(x for x in self.triggers if x["name"] == name)
                self._trigger(t.get("reaction", t.get("visual", name.upper())))
        except queue.Empty:
            pass

        self.root.after(20, self._poll)

    def _add(self, text):
        self.history.insert(0, text)
        self.history = self.history[:12]
        for w in self.hist_frame.winfo_children():
            w.destroy()
        for i, t in enumerate(self.history[:len(self.HISTORY_FONTS)]):
            fs = self.HISTORY_FONTS[i]
            fc = self.HISTORY_COLS[i]
            tk.Label(self.hist_frame, text=t,
                     font=(FONT, fs), bg=BG, fg=fc,
                     anchor="w", padx=8, pady=1,
                     wraplength=self.root.winfo_width() - 80,
                     justify="left").pack(fill="x", anchor="w")

    def _trigger(self, label):
        if self._overlay_job:
            self.root.after_cancel(self._overlay_job)
        self.overlay_lbl.config(text=label)
        self.overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.overlay.lift()
        self._overlay_job = self.root.after(3500, self._hide_trigger)

    def _hide_trigger(self):
        self.overlay.place_forget()
        self._overlay_job = None

    def shutdown(self):
        self.stop.set()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = TARS(root)
    root.protocol("WM_DELETE_WINDOW", app.shutdown)
    root.mainloop()

if __name__ == "__main__":
    main()
