import os
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import threading, queue
import numpy as np
import sounddevice as sd
import mlx_whisper

SAMPLE_RATE    = 16000
FINAL_MODEL    = "mlx-community/whisper-base.en-mlx"
PARTIAL_MODEL  = "mlx-community/whisper-tiny.en-mlx"
CHUNK          = int(0.1 * SAMPLE_RATE)
MIN_RMS        = 0.004
SPEECH_ON      = 2
SILENCE_END    = 5
MAX_CHUNKS     = 150

def _junk(text):
    t = text.lower().strip()
    if t in {"","you","the","thank you.","thanks.","bye.","huh.",
             "um.","uh.","hmm.","oh.","okay.","ok.","yeah.","yep.",
             "right.","sure.","thank you","thanks","okay","ok"}:
        return True
    words = t.split()
    return len(words) >= 5 and len(set(words)) <= 2

def _partial_worker(audio_q, out_q, stop_event):
    """Tiny model - fast, runs continuously while speaking."""
    # warm up tiny model
    mlx_whisper.transcribe(np.zeros(SAMPLE_RATE, dtype=np.float32),
                           path_or_hf_repo=PARTIAL_MODEL)
    while not stop_event.is_set():
        try:
            audio = audio_q.get(timeout=0.5)
        except queue.Empty:
            continue
        try:
            r = mlx_whisper.transcribe(
                audio, path_or_hf_repo=PARTIAL_MODEL,
                language="en", fp16=False,
                condition_on_previous_text=False,
            )
            text = r.get("text","").strip()
            if text and not _junk(text):
                try: out_q.put_nowait(("partial", text))
                except queue.Full: pass
        except Exception:
            pass

def start_listening(transcription_queue, partial_queue, stop_event):
    raw_q       = queue.Queue(maxsize=300)
    partial_aq  = queue.Queue(maxsize=1)   # always latest audio for partial

    print("Loading base model...", flush=True)
    mlx_whisper.transcribe(np.zeros(SAMPLE_RATE, dtype=np.float32),
                           path_or_hf_repo=FINAL_MODEL)

    print("Loading tiny model...", flush=True)
    threading.Thread(target=_partial_worker,
                     args=(partial_aq, partial_queue, stop_event),
                     daemon=True).start()

    print("Ready.\n", flush=True)

    def cb(indata, frames, t, status):
        try: raw_q.put_nowait(indata.copy().flatten())
        except queue.Full: pass

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                        dtype="float32", blocksize=CHUNK, callback=cb):
        while not stop_event.is_set():

            # ── Phase 1: wait for speech ──────────────────────────
            run, pre = 0, []
            while not stop_event.is_set():
                try: chunk = raw_q.get(timeout=1.0)
                except queue.Empty: continue
                rms = float(np.sqrt(np.mean(chunk**2)))
                if rms >= MIN_RMS:
                    run += 1
                    pre.append(chunk)
                    if run >= SPEECH_ON:
                        break
                else:
                    run = 0
                    pre = pre[-2:]

            if stop_event.is_set():
                break

            # ── Phase 2: record + stream partials ────────────────
            utt = list(pre)
            sil = 0
            partial_tick = 0

            while not stop_event.is_set() and len(utt) < MAX_CHUNKS:
                try: chunk = raw_q.get(timeout=0.4)
                except queue.Empty:
                    sil += 3
                    if sil >= SILENCE_END: break
                    continue

                rms = float(np.sqrt(np.mean(chunk**2)))
                utt.append(chunk)
                sil = 0 if rms >= MIN_RMS else sil + 1
                if sil >= SILENCE_END:
                    break

                # feed partial model every ~0.5s of new audio
                partial_tick += 1
                if partial_tick % 5 == 0:
                    audio_so_far = np.concatenate(utt)
                    # evict stale, put latest
                    try: partial_aq.get_nowait()
                    except queue.Empty: pass
                    try: partial_aq.put_nowait(audio_so_far)
                    except queue.Full: pass

            # ── Phase 3: final transcription with base model ──────
            try: partial_queue.put_nowait(("partial", "  …"))
            except: pass

            if len(utt) >= 3:
                audio = np.concatenate(utt)
                try:
                    r = mlx_whisper.transcribe(
                        audio,
                        path_or_hf_repo=FINAL_MODEL,
                        language="en",
                        fp16=False,
                        condition_on_previous_text=False,
                        temperature=0.0,
                    )
                    text = r.get("text","").strip()
                    if not _junk(text) and len(text) > 1:
                        transcription_queue.put(text)
                except Exception:
                    pass

            try: partial_queue.put_nowait(("final",""))
            except: pass

            # flush stale audio
            while not raw_q.empty():
                try: raw_q.get_nowait()
                except: break
