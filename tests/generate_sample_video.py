import os
import sys
import wave
import struct
import math

# Ensure parent directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from modules.ffmpeg_utils import run_ffmpeg

def create_sample_wav(output_wav: str, duration_sec: float = 9.0) -> str:
    """Generate a 16kHz mono WAV file with speech tones and silent intervals."""
    sample_rate = 16000
    total_samples = int(sample_rate * duration_sec)

    # Active sound intervals:
    # 1.2s - 3.5s (Speech 1, 440 Hz)
    # 5.0s - 7.5s (Speech 2, 554 Hz)
    active_intervals = [
        (1.2, 3.5, 440.0),
        (5.0, 7.5, 554.0)
    ]

    with wave.open(output_wav, "w") as wav_file:
        wav_file.setnchannels(1)       # Mono
        wav_file.setsampwidth(2)      # 16-bit
        wav_file.setframerate(sample_rate)

        frames = bytearray()
        for i in range(total_samples):
            t = i / sample_rate
            sample_val = 0.0

            for start_t, end_t, freq in active_intervals:
                if start_t <= t <= end_t:
                    # Fade in / fade out envelope to avoid click sounds
                    fade_len = 0.05
                    amp = 0.25
                    if t - start_t < fade_len:
                        amp *= (t - start_t) / fade_len
                    elif end_t - t < fade_len:
                        amp *= (end_t - t) / fade_len

                    sample_val = amp * math.sin(2.0 * math.pi * freq * t)
                    break

            int_val = int(sample_val * 32767.0)
            frames.extend(struct.pack("<h", int_val))

        wav_file.writeframes(frames)

    return output_wav

def create_sample_test_video(output_mp4: str = None) -> str:
    """
    Generates a 9-second synthetic video with alternating speech tones and silences:
      0.0s - 1.2s : Silence
      1.2s - 3.5s : Sound / Speech 1
      3.5s - 5.0s : Silence
      5.0s - 7.5s : Sound / Speech 2
      7.5s - 9.0s : Silence
    """
    if output_mp4 is None:
        output_mp4 = os.path.abspath(os.path.join(os.path.dirname(__file__), "sample_video.mp4"))

    os.makedirs(os.path.dirname(output_mp4), exist_ok=True)
    temp_wav = os.path.splitext(output_mp4)[0] + "_tone.wav"
    create_sample_wav(temp_wav, duration_sec=9.0)

    try:
        args = [
            "-y",
            "-f", "lavfi",
            "-i", "color=c=0x0F172A:s=1080x1920:d=9.0:r=30",
            "-i", temp_wav,
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "128k",
            "-shortest",
            output_mp4
        ]

        res = run_ffmpeg(args)
        if res.returncode != 0:
            raise RuntimeError(f"Failed to create sample video: {res.stderr}")

        print(f"[Sample Video] Successfully generated: {output_mp4}")
        return output_mp4
    finally:
        if os.path.exists(temp_wav):
            try:
                os.remove(temp_wav)
            except Exception:
                pass

if __name__ == "__main__":
    create_sample_test_video()
