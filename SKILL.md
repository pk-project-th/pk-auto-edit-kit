---
name: auto-edit-kit
description: Automated video editing agent skill that detects silence, transcribes speech, formats Thai subtitles, and injects ready-to-edit timelines directly into CapCut Desktop.
---

# Auto Edit Kit (Agent Skill)

Use this skill when the user wants to edit a video, remove dead air / silence, generate Thai subtitles, or create a CapCut Desktop project automatically.

## Core Capabilities
1. **Silence Removal (Rough Cut)**: Uses FFmpeg silence detection to cut out quiet intervals and dead air with frame accuracy.
2. **Thai Transcription & Captioning**: Word-level timestamps with 2-pass phrase chunking (2-4 words per line) suited for TikTok/Reels.
3. **CapCut Desktop Direct Injection**: Directly writes `draft_content.json` and `draft_meta_info.json` into `%LOCALAPPDATA%\CapCut\User Data\Projects\com.lveditor.draft`, so the user can open CapCut and find the project ready on their timeline.
4. **Standalone Video Render**: Can optionally export a clean cut MP4 directly via FFmpeg without needing CapCut.

## How to Run

### 1. Command Line Execution (Headless)
To process a video file and inject it into CapCut:
```bash
python C:\Users\Marketing\.gemini\antigravity\scratch\auto-edit-kit\run.py -i "path/to/video.mp4" --name "ProjectName"
```

To also render a standalone cut MP4:
```bash
python C:\Users\Marketing\.gemini\antigravity\scratch\auto-edit-kit\run.py -i "path/to/video.mp4" --export-mp4
```

To customize silence threshold:
```bash
python C:\Users\Marketing\.gemini\antigravity\scratch\auto-edit-kit\run.py -i "path/to/video.mp4" --silence-db -32.0 --min-silence 0.35
```

### 2. Web UI Execution
Launch the interactive Streamlit dashboard:
```bash
streamlit run C:\Users\Marketing\.gemini\antigravity\scratch\auto-edit-kit\app.py
```

### 3. API Keys Configuration
Optional API keys can be set as environment variables or passed via CLI:
- `ELEVENLABS_API_KEY`: For ElevenLabs Scribe Thai speech-to-text.
- `GEMINI_API_KEY`: For Google Gemini multimodal video & speech analysis.
- If no keys are provided, the kit automatically operates with intelligent synthetic alignment for offline / demo mode.
