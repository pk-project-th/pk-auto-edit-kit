import os
import sys
import argparse
import time

# Ensure UTF-8 stdout on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from modules.ffmpeg_utils import get_video_info, run_ffmpeg
from modules.silence_detector import analyze_and_cut
from modules.transcriber import transcribe_audio
from modules.thai_formatter import chunk_word_timestamps
from modules.capcut_generator import create_capcut_project

def export_standalone_video(video_path: str, keep_segments: list, output_path: str) -> str:
    """Uses FFmpeg filter_complex concat to render a standalone cut video."""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

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
        f"concat=n={len(keep_segments)}:v=1:a=1[outv][outa]"
    )

    args = [
        "-y",
        "-i", video_path,
        "-filter_complex", concat_filter,
        "-map", "[outv]",
        "-map", "[outa]",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        output_path
    ]

    print(f"[Export] Rendering standalone cut video to {output_path}...")
    res = run_ffmpeg(args)
    if res.returncode != 0:
        print(f"[Export Warning] Could not render standalone MP4: {res.stderr[:200]}")
        return ""
    return output_path

def main():
    parser = argparse.ArgumentParser(
        description="Auto Edit Kit: Automated silence removal, Thai transcription, and CapCut desktop injection."
    )
    parser.add_argument("-i", "--input", required=True, help="Path to input video file (e.g. .mp4, .mov)")
    parser.add_argument("-n", "--name", default=None, help="Name for the project in CapCut Desktop")
    parser.add_argument("--silence-db", type=float, default=-30.0, help="Noise threshold in dB for silence (default: -30.0)")
    parser.add_argument("--min-silence", type=float, default=0.4, help="Min silence duration to cut in seconds (default: 0.4)")
    parser.add_argument("--padding", type=float, default=0.06, help="Padding in seconds around speech (default: 0.06)")
    parser.add_argument("--font-size", type=float, default=12.0, help="Subtitle font size in CapCut (default: 12.0)")
    parser.add_argument("--text-y", type=float, default=-0.65, help="Subtitle vertical position (-1.0 to 1.0, default: -0.65)")
    parser.add_argument("--caption-mode", choices=["sentence", "short"], default="sentence", help="Subtitle chunking style: 'sentence' (full natural sentences) or 'short' (2-3 words)")
    parser.add_argument("--elevenlabs-key", default=None, help="ElevenLabs API key for Thai transcription")
    parser.add_argument("--gemini-key", default=None, help="Google Gemini API key for transcription / analysis")
    parser.add_argument("--no-ai-refine", action="store_true", help="Skip Gemini AI Thai grammar and spacing refinement")
    parser.add_argument("--export-mp4", action="store_true", help="Also export a standalone cut MP4 file")
    parser.add_argument("--no-capcut", action="store_true", help="Skip creating CapCut draft")

    args = parser.parse_args()

    input_path = os.path.abspath(args.input)
    if not os.path.exists(input_path):
        print(f"[Error] File not found: {input_path}")
        sys.exit(1)

    print("=" * 60)
    print("🎬 AUTO EDIT KIT: STARTING AUTOMATED VIDEO PIPELINE")
    print("=" * 60)
    print(f"📁 Input Video : {input_path}")

    # 1. Analyze video
    video_info = get_video_info(input_path)
    print(f"⏱️ Original Duration : {video_info['duration']:.2f} seconds ({video_info['width']}x{video_info['height']} @ {video_info['fps']} fps)")

    # 2. Silence Detection
    print(f"\n🔍 [1/3] Detecting dead air & silence (Threshold: {args.silence_db}dB, Min Duration: {args.min_silence}s)...")
    analysis = analyze_and_cut(
        input_path,
        noise_threshold_db=args.silence_db,
        min_silence_duration=args.min_silence,
        padding=args.padding
    )

    keep_segments = analysis["keep_segments"]
    print(f"✂️ Speech Segments Kept : {len(keep_segments)} segments")
    print(f"⚡ Silence Cut Out      : {analysis['silence_saved']:.2f} seconds saved")
    print(f"🎯 New Edited Duration  : {analysis['final_duration']:.2f} seconds")

    # 3. Transcribe & Subtitles
    print(f"\n📝 [2/3] Transcribing audio & formatting Thai subtitles...")
    words = transcribe_audio(
        input_path,
        elevenlabs_api_key=args.elevenlabs_key,
        gemini_api_key=args.gemini_key,
        preferred_engine="elevenlabs",
        keep_segments=keep_segments
    )
    subtitles = chunk_word_timestamps(
        words,
        keep_segments=keep_segments,
        caption_mode=args.caption_mode
    )

    if not args.no_ai_refine and (args.gemini_key or os.environ.get("GEMINI_API_KEY")):
        try:
            from modules.thai_refiner import refine_thai_captions_with_llm
            refined = refine_thai_captions_with_llm(subtitles, gemini_api_key=args.gemini_key)
            if refined:
                subtitles = refined
        except Exception as e:
            print(f"[Warning] AI Thai refinement skipped: {e}")

    print(f"💬 Generated Subtitle Chunks: {len(subtitles)} captions")
    for i, sub in enumerate(subtitles[:5]):
        print(f"   [{sub['timeline_start']}s -> {sub['timeline_end']}s] {sub['text']}")
    if len(subtitles) > 5:
        print(f"   ... and {len(subtitles) - 5} more captions")

    # 4. Inject into CapCut Desktop
    capcut_project_dir = ""
    if not args.no_capcut:
        print(f"\n🚀 [3/3] Injecting project into CapCut Desktop...")
        proj_name = args.name or f"AutoEdit_{os.path.splitext(os.path.basename(input_path))[0]}"
        capcut_project_dir = create_capcut_project(
            video_path=input_path,
            keep_segments=keep_segments,
            subtitles=subtitles,
            project_name=proj_name,
            font_size=args.font_size,
            text_y_position=args.text_y
        )
        print(f"🎉 SUCCESS! CapCut project created at:")
        print(f"   {capcut_project_dir}")
        print("👉 You can now open CapCut Desktop and find your ready-to-edit project on the home screen!")

    # 5. Optional Standalone Export
    if args.export_mp4:
        out_mp4 = os.path.splitext(input_path)[0] + "_edited.mp4"
        export_standalone_video(input_path, keep_segments, out_mp4)
        print(f"💾 Standalone cut MP4 saved to: {out_mp4}")

    print("\n" + "=" * 60)
    print("✨ ALL DONE! Workflow completed seamlessly.")
    print("=" * 60)

if __name__ == "__main__":
    main()
