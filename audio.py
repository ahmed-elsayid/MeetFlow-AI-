import wave
import threading
import pyaudiowpatch as pyaudio


def _find_loopback(p: pyaudio.PyAudio) -> dict:
    """Auto-detect the WASAPI loopback device for the default speakers."""
    wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
    default_speakers = p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
    for loopback in p.get_loopback_device_info_generator():
        if default_speakers["name"] in loopback["name"]:
            return loopback
    raise RuntimeError(
        "No WASAPI loopback device found. "
        "Make sure your speakers are set as the default playback device."
    )


def record_audio(stop_event: threading.Event, output_path: str):
    """
    Record system audio to output_path until stop_event is set.
    Blocks until recording is complete.
    """
    CHUNK = 1024

    with pyaudio.PyAudio() as p:
        device = _find_loopback(p)
        rate     = int(device["defaultSampleRate"])
        channels = device["maxInputChannels"]

        print(f"[AUDIO] Capturing: {device['name']} @ {rate} Hz, {channels} ch")

        stream = p.open(
            format=pyaudio.paInt16,
            channels=channels,
            rate=rate,
            input=True,
            frames_per_buffer=CHUNK,
            input_device_index=device["index"],
        )

        frames = []
        while not stop_event.is_set():
            try:
                data = stream.read(CHUNK, exception_on_overflow=False)
                frames.append(data)
            except Exception:
                break

        stream.stop_stream()
        stream.close()

        with wave.open(output_path, "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(2)          
            wf.setframerate(rate)
            wf.writeframes(b"".join(frames))

        duration = len(frames) * CHUNK / rate
        print(f"[AUDIO] Saved {duration:.1f}s of audio -> {output_path}")
