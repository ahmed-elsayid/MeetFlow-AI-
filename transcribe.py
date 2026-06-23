import os
import wave
import numpy as np
import scipy.signal
from faster_whisper import WhisperModel

_model = None


def _get_model() -> WhisperModel:
    global _model
    if _model is None:
        size = os.getenv("WHISPER_MODEL", "base")
        print(f"[STT] Loading Whisper '{size}' model (first run downloads ~140 MB)...")
        _model = WhisperModel(size, device="cpu", compute_type="int8")
    return _model


def transcribe(audio_path: str) -> str:
    """
    Transcribe a WAV file and return the full text.
    Automatically converts to 16kHz mono float32.
    """
    model = _get_model()

    with wave.open(audio_path, "rb") as wf:
        src_rate = wf.getframerate()
        channels = wf.getnchannels()
        raw      = wf.readframes(wf.getnframes())

    audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

    if channels == 2:
        audio = audio.reshape(-1, 2).mean(axis=1)

    if src_rate != 16000:
        new_len = int(len(audio) * 16000 / src_rate)
        audio = scipy.signal.resample(audio, new_len)

    print("[STT] Transcribing audio...")
    segments, info = model.transcribe(audio, beam_size=5, vad_filter=True)

    transcript = " ".join(seg.text.strip() for seg in segments)
    word_count = len(transcript.split())
    print(f"[STT] {word_count} words transcribed from {info.duration:.1f}s of audio")
    return transcript
