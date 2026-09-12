import re
from typing import List, Dict, Tuple
from .ffmpeg_utils import run_ffmpeg, get_video_info

def detect_silence_intervals(
    video_or_audio_path: str,
    noise_threshold_db: float = -30.0,
    min_silence_duration: float = 0.4
) -> List[Tuple[float, float]]:
    """
    Detects silent intervals using ffmpeg silencedetect filter.
    Returns list of (silence_start, silence_end) in seconds.
    """
    args = [
        "-i", video_or_audio_path,
        "-vn",
        "-af", f"silencedetect=noise={noise_threshold_db}dB:d={min_silence_duration}",
        "-f", "null",
        "-"
    ]
    res = run_ffmpeg(args)
    stderr = res.stderr

    silence_starts = []
    silence_ends = []

    # Pattern for silence_start
    for match in re.finditer(r"silence_start:\s*([0-9.]+)", stderr):
        silence_starts.append(float(match.group(1)))

    # Pattern for silence_end
    for match in re.finditer(r"silence_end:\s*([0-9.]+)", stderr):
        silence_ends.append(float(match.group(1)))

    intervals: List[Tuple[float, float]] = []
    # Match pairs of start and end
    for i in range(len(silence_ends)):
        if i < len(silence_starts):
            intervals.append((silence_starts[i], silence_ends[i]))

    # If there is a trailing silence_start without silence_end (happens when silence extends to end)
    if len(silence_starts) > len(silence_ends):
        # We'll need the total duration to cap it
        info = get_video_info(video_or_audio_path)
        total_dur = info.get("duration", silence_starts[-1] + 1.0)
        intervals.append((silence_starts[-1], total_dur))

    return intervals

def compute_keep_segments(
    total_duration: float,
    silence_intervals: List[Tuple[float, float]],
    padding: float = 0.06,
    min_segment_len: float = 0.15
) -> List[Dict[str, float]]:
    """
    Inverts silence intervals to find spoken/active segments to keep.
    Applies small padding at start and end of speech for natural transitions.
    Returns a list of dicts: [{'start': float, 'end': float, 'duration': float}]
    """
    if not silence_intervals:
        return [{"start": 0.0, "end": total_duration, "duration": total_duration}]

    # Invert silence to keep intervals
    raw_keep: List[Tuple[float, float]] = []
    current_pos = 0.0

    for s_start, s_end in sorted(silence_intervals, key=lambda x: x[0]):
        if s_start > current_pos:
            raw_keep.append((current_pos, s_start))
        current_pos = max(current_pos, s_end)

    if current_pos < total_duration:
        raw_keep.append((current_pos, total_duration))

    # Apply padding and ensure non-overlapping & min_segment_len
    padded_segments: List[Dict[str, float]] = []
    for i, (k_start, k_end) in enumerate(raw_keep):
        # Add padding
        adj_start = max(0.0, k_start - padding)
        adj_end = min(total_duration, k_end + padding)

        # Prevent overlap with previous segment
        if padded_segments and adj_start < padded_segments[-1]["end"]:
            adj_start = padded_segments[-1]["end"]

        dur = adj_end - adj_start
        if dur >= min_segment_len:
            padded_segments.append({
                "start": round(adj_start, 3),
                "end": round(adj_end, 3),
                "duration": round(dur, 3)
            })

    return padded_segments

def analyze_and_cut(
    video_path: str,
    noise_threshold_db: float = -30.0,
    min_silence_duration: float = 0.4,
    padding: float = 0.06
) -> Dict:
    """High-level function to analyze silence and produce edit decision segments."""
    info = get_video_info(video_path)
    total_duration = info["duration"]

    silence_intervals = detect_silence_intervals(
        video_path,
        noise_threshold_db=noise_threshold_db,
        min_silence_duration=min_silence_duration
    )

    keep_segments = compute_keep_segments(
        total_duration=total_duration,
        silence_intervals=silence_intervals,
        padding=padding
    )

    total_silence = sum((s_end - s_start) for s_start, s_end in silence_intervals)
    final_duration = sum(seg["duration"] for seg in keep_segments)

    return {
        "original_duration": total_duration,
        "final_duration": round(final_duration, 3),
        "silence_saved": round(total_duration - final_duration, 3),
        "silence_count": len(silence_intervals),
        "keep_segments": keep_segments,
        "silence_intervals": silence_intervals
    }
