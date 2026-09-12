import os
import subprocess
import json
import re

def get_ffmpeg_path() -> str:
    """Find and return the ffmpeg executable path."""
    # 1. Check imageio_ffmpeg
    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        if os.path.exists(ffmpeg_exe):
            return ffmpeg_exe
    except ImportError:
        pass

    # 2. Check system PATH
    import shutil
    sys_ffmpeg = shutil.which("ffmpeg")
    if sys_ffmpeg:
        return sys_ffmpeg

    raise RuntimeError("FFmpeg executable not found. Please install imageio-ffmpeg or ffmpeg.")

def run_ffmpeg(args: list[str]) -> subprocess.CompletedProcess:
    """Run an FFmpeg command with given argument list."""
    ffmpeg_exe = get_ffmpeg_path()
    cmd = [ffmpeg_exe] + args
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    return result

def get_video_info(video_path: str) -> dict:
    """Extract duration, dimensions, and fps of a video file using FFmpeg output."""
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    # Use ffmpeg -i to parse stream information from stderr
    result = run_ffmpeg(["-i", video_path])
    stderr = result.stderr

    duration = 0.0
    fps = 30.0
    width = 1080
    height = 1920

    # Parse Duration: 00:01:23.45
    dur_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", stderr)
    if dur_match:
        hours = float(dur_match.group(1))
        minutes = float(dur_match.group(2))
        seconds = float(dur_match.group(3))
        duration = hours * 3600 + minutes * 60 + seconds

    # Parse Resolution: e.g. 1080x1920 or 1920x1080
    res_match = re.search(r",\s*(\d{3,4})x(\d{3,4})", stderr)
    if res_match:
        width = int(res_match.group(1))
        height = int(res_match.group(2))

    # Parse fps: e.g. 29.97 fps or 30 fps or 60 fps
    fps_match = re.search(r"(\d+(?:\.\d+)?)\s*fps", stderr)
    if fps_match:
        fps = float(fps_match.group(1))

    return {
        "duration": duration,
        "width": width,
        "height": height,
        "fps": fps
    }

def extract_audio(video_path: str, output_wav_path: str) -> str:
    """Extract audio from video to 16kHz mono WAV for high-accuracy VAD / STT."""
    os.makedirs(os.path.dirname(os.path.abspath(output_wav_path)), exist_ok=True)
    args = [
        "-y",
        "-i", video_path,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        output_wav_path
    ]
    res = run_ffmpeg(args)
    if res.returncode != 0:
        raise RuntimeError(f"Failed to extract audio: {res.stderr}")
    return output_wav_path

def hex_to_ass_color(hex_str: str) -> str:
    """Converts #RRGGBB hex color to ASS &HAABBGGRR format."""
    hex_clean = hex_str.lstrip("#")
    if len(hex_clean) == 6:
        r = hex_clean[0:2]
        g = hex_clean[2:4]
        b = hex_clean[4:6]
        return f"&H00{b}{g}{r}"
    return "&H0000E5FF" # default CapCut yellow

def format_ass_time(sec: float) -> str:
    """Format seconds into ASS timestamp: H:MM:SS.cs"""
    sec = max(0.0, sec)
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h:d}:{m:02d}:{s:05.2f}"

def render_video_with_subtitles(
    video_path: str,
    keep_segments: list[dict],
    subtitles: list[dict],
    output_path: str,
    font_name: str = "Kanit",
    font_size: float = 8.5,
    text_color_hex: str = "#FFFFFF",
    focus_color_hex: str = "#FF1E27",
    stroke_val: int = 8,
    shadow_val: int = 80,
    vertical_position_pct: float = 82.0,
    letter_spacing: float = 2.0,
    karaoke_mode: bool = True,
    anim_type: str = "pop",
    enable_pop: bool = True
) -> str:
    """
    Renders a standalone cut MP4 video with burned-in styled subtitles using FFmpeg.
    Supports dynamic word-by-word focus color highlight, custom letter spacing, and multiple animation styles.
    """
    from .thai_formatter import get_word_character_ranges

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    v_info = get_video_info(video_path)
    width = v_info.get("width", 1080)
    height = v_info.get("height", 1920)

    clean_font = font_name.split("(")[0].strip()
    if "Kanit" in font_name or "คณิต" in font_name:
        clean_font = "Kanit"
    elif "Mazda" in font_name:
        clean_font = "Prompt"

    ass_base = hex_to_ass_color(text_color_hex)
    ass_focus = hex_to_ass_color(focus_color_hex)
    ass_stroke = hex_to_ass_color("#000000")

    # Dynamic scaling for 1080x1920 or 2160x3840
    ass_font_size = int(height * (font_size / 8.5) * 0.038)
    outline_px = max(2, int(ass_font_size * (stroke_val / 10.0) * 0.16))
    shadow_depth = max(1, int(ass_font_size * (shadow_val / 100.0) * 0.08))
    margin_v = int(height * (1.0 - (vertical_position_pct / 100.0)))
    margin_v = max(30, min(margin_v, height - 100))
    ass_spacing = max(0, int(letter_spacing * 2.5))

    # Resolve active animation type
    effective_anim = anim_type if karaoke_mode else "none"
    if effective_anim == "none" and enable_pop and karaoke_mode:
        effective_anim = "pop"

    # Generate ASS script
    dialogues = []
    for sub in subtitles:
        cue_text = sub.get("text", "").strip()
        if not cue_text:
            continue

        words = sub.get("words", [])
        if karaoke_mode and words:
            ranges = get_word_character_ranges(cue_text, words)
            for w_idx, w in enumerate(words):
                w_start = format_ass_time(w.get("timeline_start", w["start"]))
                w_end = format_ass_time(w.get("timeline_end", w["end"]))

                r_start, r_end = ranges[w_idx]
                prefix = cue_text[:r_start]
                active = cue_text[r_start:r_end]
                suffix = cue_text[r_end:]

                if effective_anim == "pop":
                    active_tagged = f"{{\\c{ass_focus}\\fscx118\\fscy118\\t(0,120,\\fscx100\\fscy100)}}{active}{{\\c{ass_base}\\fscx100\\fscy100}}"
                elif effective_anim == "zoom":
                    active_tagged = f"{{\\c{ass_focus}\\fscx114\\fscy114}}{active}{{\\c{ass_base}\\fscx100\\fscy100}}"
                elif effective_anim == "glow":
                    active_tagged = f"{{\\c{ass_focus}\\bord{outline_px + 4}\\blur4\\t(0,140,\\bord{outline_px + 1}\\blur2)}}{active}{{\\c{ass_base}\\bord{outline_px}\\blur0}}"
                elif effective_anim == "jump":
                    active_tagged = f"{{\\c{ass_focus}\\fscy114\\fscx106\\t(0,110,\\fscy100\\fscx100)}}{active}{{\\c{ass_base}\\fscy100\\fscx100}}"
                else:
                    active_tagged = f"{{\\c{ass_focus}}}{active}{{\\c{ass_base}}}"

                line_str = f"{prefix}{active_tagged}{suffix}"
                dialogues.append(f"Dialogue: 0,{w_start},{w_end},Default,,0,0,0,,{line_str}")
        else:
            s_start = format_ass_time(sub.get("timeline_start", 0.0))
            s_end = format_ass_time(sub.get("timeline_end", sub.get("timeline_start", 0.0) + 1.0))
            dialogues.append(f"Dialogue: 0,{s_start},{s_end},Default,,0,0,0,,{cue_text}")

    ass_content = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{clean_font},{ass_font_size},{ass_base},&H000000FF,{ass_stroke},&H80000000,-1,0,0,0,100,100,{ass_spacing},0,1,{outline_px},{shadow_depth},2,40,40,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""" + "\n".join(dialogues) + "\n"

    temp_ass = os.path.splitext(output_path)[0] + "_subs.ass"
    with open(temp_ass, "w", encoding="utf-8") as f:
        f.write(ass_content)

    ass_escaped = temp_ass.replace("\\", "/").replace(":", "\\:")
    sub_filter = f"subtitles='{ass_escaped}'"

    try:
        orig_dur = v_info["duration"]
        is_full_video = (
            len(keep_segments) == 1 and
            abs(keep_segments[0]["start"]) < 0.1 and
            abs(keep_segments[0]["end"] - orig_dur) < 0.5
        )

        if is_full_video:
            args = [
                "-y",
                "-i", video_path,
                "-vf", sub_filter,
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "192k",
                output_path
            ]
        else:
            filter_parts = []
            concat_inputs = []
            for i, seg in enumerate(keep_segments):
                s_start = seg["start"]
                s_end = seg["end"]
                filter_parts.append(
                    f"[0:v]trim=start={s_start}:end={s_end},setpts=PTS-STARTPTS[v{i}]; "
                    f"[0:a]atrim=start={s_start}:end={s_end},asetpts=PTS-STARTPTS[a{i}]"
                )
                concat_inputs.append(f"[v{i}][a{i}]")

            concat_filter = (
                "; ".join(filter_parts) + "; " +
                "".join(concat_inputs) +
                f"concat=n={len(keep_segments)}:v=1:a=1[cv][ca]; "
                f"[cv]{sub_filter}[outv]"
            )

            args = [
                "-y",
                "-i", video_path,
                "-filter_complex", concat_filter,
                "-map", "[outv]",
                "-map", "[ca]",
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "192k",
                output_path
            ]

        res = run_ffmpeg(args)
        if res.returncode != 0:
            raise RuntimeError(f"FFmpeg render error: {res.stderr[-400:]}")
        return output_path
    finally:
        if os.path.exists(temp_ass):
            try:
                os.remove(temp_ass)
            except Exception:
                pass

