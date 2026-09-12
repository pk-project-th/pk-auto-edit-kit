import os
import json
import uuid
import time
import shutil
from typing import List, Dict, Any
from .ffmpeg_utils import get_video_info

def get_capcut_draft_dir() -> str:
    """Returns the default CapCut Desktop draft directory on Windows/macOS."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        win_path = os.path.join(local_app_data, "CapCut", "User Data", "Projects", "com.lveditor.draft")
        if os.path.exists(win_path):
            return win_path

    home = os.path.expanduser("~")
    mac_path = os.path.join(home, "Movies", "CapCut", "User Data", "Projects", "com.lveditor.draft")
    if os.path.exists(mac_path):
        return mac_path

    if local_app_data:
        fallback = os.path.join(local_app_data, "CapCut", "User Data", "Projects", "com.lveditor.draft")
        os.makedirs(fallback, exist_ok=True)
        return fallback

    raise RuntimeError("Could not determine CapCut projects directory.")

def cleanup_old_autoedit_drafts(keep_recent: int = 3) -> int:
    """
    Deletes older temporary AutoEdit folders to save disk space.
    Keeps only the most recent `keep_recent` projects.
    Returns the number of deleted project folders.
    """
    drafts_root = get_capcut_draft_dir()
    if not os.path.exists(drafts_root):
        return 0

    autoedit_folders = []
    for item in os.listdir(drafts_root):
        full_path = os.path.join(drafts_root, item)
        if os.path.isdir(full_path) and item.startswith("AutoEdit_"):
            autoedit_folders.append((full_path, os.path.getmtime(full_path)))

    # Sort newest first
    autoedit_folders.sort(key=lambda x: x[1], reverse=True)

    deleted_count = 0
    # Delete beyond keep_recent
    for folder_path, _ in autoedit_folders[keep_recent:]:
        try:
            shutil.rmtree(folder_path, ignore_errors=True)
            deleted_count += 1
            print(f"[Cleanup] Removed old draft: {os.path.basename(folder_path)}")
        except Exception as e:
            print(f"[Cleanup Warning] Could not remove {folder_path}: {e}")

    return deleted_count

def get_template_draft() -> dict:
    """Loads a base template from existing draft or generates a robust default structure."""
    drafts_dir = get_capcut_draft_dir()
    for item in os.listdir(drafts_dir):
        draft_json_path = os.path.join(drafts_dir, item, "draft_content.json")
        if os.path.isfile(draft_json_path):
            try:
                with open(draft_json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "tracks" in data and "materials" in data:
                        return data
            except Exception:
                continue

    return {
        "id": str(uuid.uuid4()).upper(),
        "version": 360000,
        "new_version": "120.0.0",
        "name": "AutoEdit_Project",
        "fps": 30.0,
        "color_space": 0,
        "duration": 0,
        "canvas_config": {
            "height": 1920,
            "width": 1080,
            "ratio": "original"
        },
        "config": {
            "adjust_max_index": 1,
            "attachment_info": [],
            "combination_max_index": 1,
            "export_range": None,
            "extract_audio_last_index": 1,
            "lyrics_recognition_id": "",
            "lyrics_sync": True,
            "lyrics_task_id": "",
            "maintrack_adsorb": True,
            "material_save_mode": 0,
            "original_sound_last_index": 1,
            "record_audio_last_index": 1,
            "sticker_max_index": 1,
            "subtitle_recognition_id": "",
            "subtitle_sync": True,
            "subtitle_task_id": "",
            "system_font_list": [],
            "video_mute": False,
            "zoom_info_params": None
        },
        "materials": {
            "videos": [],
            "texts": [],
            "audios": [],
            "speeds": [],
            "canvases": [],
            "transitions": [],
            "effects": [],
            "stickers": [],
            "placeholder_infos": []
        },
        "tracks": []
    }

def resolve_capcut_font(font_name: str) -> Dict[str, str]:
    """Resolves font title, local path, and effect ID for CapCut Desktop."""
    # Kanit Bold from CapCut effect cache (matches user's Image 3)
    capcut_kanit_bold = "C:/Users/Marketing/AppData/Local/CapCut/User Data/Cache/effect/7553125745346792721/b6ebb59e5847ffc6a2d42efcc5c080ce/font.ttf"
    capcut_kanit_reg = "C:/Users/Marketing/AppData/Local/CapCut/User Data/Cache/effect/7229975647517413890/3ec5e7299462f75576b039520299c405/Kanit-Regular.ttf"
    mazda_bold = "C:/Users/Marketing/AppData/Local/Microsoft/Windows/Fonts/MazdaTypeTH-Bold.otf"

    if any(k in font_name for k in ["Kanit", "คณิต"]):
        if os.path.exists(capcut_kanit_bold):
            return {
                "path": capcut_kanit_bold.replace("\\", "/"),
                "id": "7553125745346792721",
                "title": "Kanit-Bold"
            }
        elif os.path.exists(capcut_kanit_reg):
            return {
                "path": capcut_kanit_reg.replace("\\", "/"),
                "id": "7229975647517413890",
                "title": "Kanit"
            }
        return {"path": "", "id": "", "title": "Kanit"}

    if any(k in font_name for k in ["Mazda", "มาสด้า"]):
        if os.path.exists(mazda_bold):
            return {
                "path": mazda_bold.replace("\\", "/"),
                "id": "",
                "title": "MazdaTypeTH-Bold"
            }
        return {"path": "", "id": "", "title": "MazdaTypeTH-Bold"}

    clean_title = font_name.split("(")[0].strip()
    return {"path": "", "id": "", "title": clean_title}

def create_capcut_project(
    video_path: str,
    keep_segments: List[Dict[str, float]],
    subtitles: List[Dict[str, Any]] = None,
    project_name: str = None,
    font_name: str = "Kanit (คณิต BD)",
    font_size: float = 8.5,               # Default 8.5 fits clip perfectly without overflow!
    text_color: List[float] = None,       # [R, G, B] 0.0 - 1.0 (default White [1.0, 1.0, 1.0])
    focus_color: List[float] = None,      # [R, G, B] 0.0 - 1.0 (default Red [1.0, 0.12, 0.15])
    stroke_width: float = 0.02,           # CapCut stroke 10% (matching Image 3)
    stroke_color: List[float] = None,     # [0.0, 0.0, 0.0]
    shadow_alpha: float = 0.80,           # Default 80% opacity
    shadow_distance: float = 5.0,
    text_y_position: float = -0.65,       # Safe lower-third zone
    letter_spacing: float = 2.0,          # Character spacing
    karaoke_mode: bool = True,
    anim_type: str = "pop",
    enable_pop: bool = True
) -> str:
    """
    Creates a full CapCut Desktop project folder with cut video and customized subtitles.
    Supports dynamic word-by-word karaoke focus color highlight and pop animation.
    Returns the absolute path to the generated CapCut project folder.
    """
    video_abs_path = os.path.abspath(video_path).replace("\\", "/")
    video_info = get_video_info(video_path)
    video_dur_us = int(video_info["duration"] * 1_000_000)
    width = video_info.get("width", 1080)
    height = video_info.get("height", 1920)
    fps = video_info.get("fps", 30.0)

    if text_color is None:
        text_color = [1.0, 1.0, 1.0] # White
    if focus_color is None:
        focus_color = [1.0, 0.12, 0.15] # Bright Red (#FF1E27)
    if stroke_color is None:
        stroke_color = [0.0, 0.0, 0.0] # Black outline

    timestamp_str = time.strftime("%Y%m%d_%H%M%S")
    sanitized_name = project_name or f"AutoEdit_{timestamp_str}"
    folder_name = f"AutoEdit_{timestamp_str}"

    drafts_root = get_capcut_draft_dir()
    project_dir = os.path.join(drafts_root, folder_name)
    os.makedirs(project_dir, exist_ok=True)

    # 1. Load base template
    content = get_template_draft()

    project_id = str(uuid.uuid4()).upper()
    content["id"] = project_id
    content["name"] = sanitized_name
    content["fps"] = fps
    content["canvas_config"] = {
        "width": width,
        "height": height,
        "ratio": "original"
    }

    if "materials" not in content:
        content["materials"] = {}
    content["materials"]["videos"] = []
    content["materials"]["texts"] = []
    content["materials"]["speeds"] = []
    content["materials"]["canvases"] = []

    # Video Material
    video_material_id = str(uuid.uuid4()).upper()
    video_mat = {
        "id": video_material_id,
        "type": "video",
        "duration": video_dur_us,
        "path": video_abs_path,
        "width": width,
        "height": height,
        "material_name": os.path.basename(video_abs_path),
        "has_audio": True,
        "category_id": "",
        "category_name": "local"
    }
    content["materials"]["videos"].append(video_mat)

    speed_id = str(uuid.uuid4()).upper()
    content["materials"]["speeds"].append({
        "id": speed_id,
        "speed": 1.0,
        "type": "speed"
    })

    canvas_id = str(uuid.uuid4()).upper()
    content["materials"]["canvases"].append({
        "id": canvas_id,
        "type": "canvas_color",
        "color": ""
    })

    # Build Video Track & Segments
    video_track_id = str(uuid.uuid4()).upper()
    video_segments = []
    timeline_cursor_us = 0

    for seg in keep_segments:
        start_us = int(seg["start"] * 1_000_000)
        dur_us = int(seg["duration"] * 1_000_000)
        if dur_us <= 0:
            continue

        seg_id = str(uuid.uuid4()).upper()
        video_segments.append({
            "id": seg_id,
            "material_id": video_material_id,
            "source_timerange": {
                "start": start_us,
                "duration": dur_us
            },
            "target_timerange": {
                "start": timeline_cursor_us,
                "duration": dur_us
            },
            "speed": 1.0,
            "volume": 1.0,
            "clip": {
                "scale": {"x": 1.0, "y": 1.0},
                "rotation": 0.0,
                "transform": {"x": 0.0, "y": 0.0},
                "flip": {"horizontal": False, "vertical": False},
                "alpha": 1.0
            },
            "extra_material_refs": [speed_id, canvas_id],
            "visible": True
        })
        timeline_cursor_us += dur_us

    total_timeline_duration_us = timeline_cursor_us
    content["duration"] = total_timeline_duration_us

    # Build Text Track & Segments
    text_segments = []
    font_resolved = resolve_capcut_font(font_name)

    if subtitles:
        from .thai_formatter import get_word_character_ranges

        for sub in subtitles:
            sub_text = sub.get("text", "").strip()
            if not sub_text:
                continue

            words = sub.get("words", [])

            # Base typography style with chosen font, stroke, and shadow
            base_style_obj = {
                "fill": {
                    "alpha": 1.0,
                    "content": {
                        "render_type": "solid",
                        "solid": {"alpha": 1.0, "color": text_color}
                    }
                },
                "font": font_resolved,
                "size": font_size,
                "bold": True,
                "useLetterColor": True,
                "shadows": [
                    {
                        "alpha": shadow_alpha,
                        "angle": -45.0,
                        "content": {
                            "render_type": "solid",
                            "solid": {"color": [0.0, 0.0, 0.0]}
                        },
                        "diffuse": 0.025,
                        "distance": shadow_distance,
                        "thickness_projection_angle": -45.0,
                        "thickness_projection_distance": 0.0,
                        "thickness_projection_enable": False
                    }
                ] if shadow_alpha > 0 else [],
                "strokes": [
                    {
                        "alpha": 1.0,
                        "content": {
                            "render_type": "solid",
                            "solid": {"alpha": 1.0, "color": stroke_color}
                        },
                        "width": stroke_width,
                        "mode": 0
                    }
                ] if stroke_width > 0 else [],
                "range": [0, len(sub_text)]
            }

            # Calculate safe scale to guarantee text strictly stays within the video canvas boundaries
            base_scale = round((font_size / 8.5) * 1.65, 3)
            lines = sub_text.split("\n")
            longest_len = max(len(l.strip()) for l in lines) if lines else len(sub_text)
            est_text_width = longest_len * 24.0

            if est_text_width * base_scale > 860.0:
                clip_scale = round(860.0 / est_text_width, 3)
            else:
                clip_scale = base_scale
            clip_scale = max(0.85, min(clip_scale, 1.85))

            capcut_letter_spacing = round(letter_spacing * 0.04, 3)

            effective_anim = anim_type if karaoke_mode else "none"
            if effective_anim == "none" and enable_pop and karaoke_mode:
                effective_anim = "pop"

            if karaoke_mode and words:
                ranges = get_word_character_ranges(sub_text, words)
                for w_idx, w in enumerate(words):
                    w_start_us = int(w.get("timeline_start", w["start"]) * 1_000_000)
                    w_end_us = int(w.get("timeline_end", w["end"]) * 1_000_000)
                    w_dur_us = max(100_000, w_end_us - w_start_us)

                    r_start, r_end = ranges[w_idx]

                    # Focus highlight style for the active word range
                    focus_style_obj = {
                        "fill": {
                            "alpha": 1.0,
                            "content": {
                                "render_type": "solid",
                                "solid": {"alpha": 1.0, "color": focus_color}
                            }
                        },
                        "range": [r_start, r_end]
                    }

                    if effective_anim == "glow":
                        focus_style_obj["strokes"] = [{
                            "alpha": 1.0,
                            "content": {
                                "render_type": "solid",
                                "solid": {"alpha": 1.0, "color": focus_color}
                            },
                            "width": max(0.025, stroke_width * 1.5),
                            "mode": 0
                        }]

                    text_content_payload = {
                        "text": sub_text,
                        "styles": [base_style_obj, focus_style_obj]
                    }

                    text_mat_id = str(uuid.uuid4()).upper()
                    text_mat = {
                        "id": text_mat_id,
                        "type": "text",
                        "name": sub_text.replace("\n", " ")[:20],
                        "content": json.dumps(text_content_payload, ensure_ascii=False),
                        "words": {"start_time": [], "end_time": [], "text": []},
                        "letter_spacing": capcut_letter_spacing,
                        "global_alpha": 1.0
                    }
                    content["materials"]["texts"].append(text_mat)

                    # Dynamic scale and transform based on animation style
                    if effective_anim == "pop":
                        pop_scale = round(clip_scale * 1.08, 3)
                        seg_y = text_y_position
                    elif effective_anim == "zoom":
                        pop_scale = round(clip_scale * 1.14, 3)
                        seg_y = text_y_position
                    elif effective_anim == "glow":
                        pop_scale = clip_scale
                        seg_y = text_y_position
                    elif effective_anim == "jump":
                        pop_scale = round(clip_scale * 1.04, 3)
                        seg_y = round(text_y_position + 0.02, 3)
                    else:
                        pop_scale = clip_scale
                        seg_y = text_y_position

                    text_seg_id = str(uuid.uuid4()).upper()
                    text_segments.append({
                        "id": text_seg_id,
                        "material_id": text_mat_id,
                        "source_timerange": None,
                        "target_timerange": {
                            "start": w_start_us,
                            "duration": w_dur_us
                        },
                        "clip": {
                            "scale": {"x": pop_scale, "y": pop_scale},
                            "rotation": 0.0,
                            "transform": {"x": 0.0, "y": seg_y},
                            "flip": {"horizontal": False, "vertical": False},
                            "alpha": 1.0
                        },
                        "speed": 1.0,
                        "volume": 1.0,
                        "visible": True
                    })
            else:
                sub_start_us = int(sub.get("timeline_start", 0.0) * 1_000_000)
                sub_dur_us = int(sub.get("duration", 1.0) * 1_000_000)
                if sub_dur_us <= 0:
                    continue

                text_content_payload = {
                    "text": sub_text,
                    "styles": [base_style_obj]
                }
                text_mat_id = str(uuid.uuid4()).upper()
                text_mat = {
                    "id": text_mat_id,
                    "type": "text",
                    "name": sub_text.replace("\n", " ")[:20],
                    "content": json.dumps(text_content_payload, ensure_ascii=False),
                    "words": {"start_time": [], "end_time": [], "text": []},
                    "letter_spacing": capcut_letter_spacing,
                    "global_alpha": 1.0
                }
                content["materials"]["texts"].append(text_mat)

                text_seg_id = str(uuid.uuid4()).upper()
                text_segments.append({
                    "id": text_seg_id,
                    "material_id": text_mat_id,
                    "source_timerange": None,
                    "target_timerange": {
                        "start": sub_start_us,
                        "duration": sub_dur_us
                    },
                    "clip": {
                        "scale": {"x": clip_scale, "y": clip_scale},
                        "rotation": 0.0,
                        "transform": {"x": 0.0, "y": text_y_position},
                        "flip": {"horizontal": False, "vertical": False},
                        "alpha": 1.0
                    },
                    "speed": 1.0,
                    "volume": 1.0,
                    "visible": True
                })

    tracks = [
        {
            "id": video_track_id,
            "type": "video",
            "attribute": 0,
            "segments": video_segments,
            "flag": 0
        }
    ]

    if text_segments:
        text_track_id = str(uuid.uuid4()).upper()
        tracks.append({
            "id": text_track_id,
            "type": "text",
            "attribute": 0,
            "segments": text_segments,
            "flag": 0
        })

    content["tracks"] = tracks

    # Write draft_content.json
    draft_content_file = os.path.join(project_dir, "draft_content.json")
    with open(draft_content_file, "w", encoding="utf-8") as f:
        json.dump(content, f, ensure_ascii=False, indent=2)

    # Write draft_meta_info.json
    now_us = int(time.time() * 1_000_000)
    meta_info = {
        "cloud_draft_cover": False,
        "cloud_draft_sync": False,
        "draft_cover": "draft_cover.jpg",
        "draft_fold_path": project_dir.replace("\\", "/"),
        "draft_id": project_id,
        "draft_materials": [
            {
                "type": 0,
                "value": [video_abs_path]
            }
        ],
        "draft_name": sanitized_name,
        "draft_root_path": drafts_root.replace("\\", "/"),
        "tm_duration": total_timeline_duration_us,
        "tm_draft_create": now_us,
        "tm_draft_modified": now_us,
        "tm_draft_removed": 0
    }
    draft_meta_file = os.path.join(project_dir, "draft_meta_info.json")
    with open(draft_meta_file, "w", encoding="utf-8") as f:
        json.dump(meta_info, f, ensure_ascii=False, indent=2)

    # Write supporting config files
    biz_config = {
        "timeline_settings": {
            project_id: {
                "adsorb_enabled": True,
                "linkage_enabled": True
            }
        }
    }
    with open(os.path.join(project_dir, "draft_biz_config.json"), "w", encoding="utf-8") as f:
        json.dump(biz_config, f, indent=2)

    agency_config = {
        "is_auto_agency_enabled": False,
        "is_auto_agency_popup": False,
        "is_single_agency_mode": False,
        "marterials": None,
        "use_converter": False,
        "video_resolution": 720
    }
    with open(os.path.join(project_dir, "draft_agency_config.json"), "w", encoding="utf-8") as f:
        json.dump(agency_config, f, indent=2)

    return project_dir
