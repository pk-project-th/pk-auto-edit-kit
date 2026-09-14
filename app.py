import os
import sys
import importlib
import tempfile
import time
import requests
import socket
import streamlit as st
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Automatically sync Streamlit Cloud Secrets into os.environ if running on cloud
try:
    if hasattr(st, "secrets"):
        for sec_k, sec_v in st.secrets.items():
            if isinstance(sec_v, str) and sec_k not in os.environ:
                os.environ[sec_k] = sec_v
except Exception:
    pass

# Ensure local modules are accessible and dynamically reloaded
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import modules.ffmpeg_utils as ffmpeg_utils
import modules.silence_detector as silence_detector
import modules.transcriber as transcriber
import modules.thai_formatter as thai_formatter
import modules.capcut_generator as capcut_generator

importlib.reload(ffmpeg_utils)
importlib.reload(silence_detector)
importlib.reload(transcriber)
importlib.reload(thai_formatter)
importlib.reload(capcut_generator)

from modules.ffmpeg_utils import get_video_info, render_video_with_subtitles
from modules.silence_detector import analyze_and_cut
from modules.transcriber import transcribe_audio
from modules.thai_formatter import chunk_word_timestamps, generate_webvtt, map_timestamp_to_edited_timeline
from modules.capcut_generator import create_capcut_project, cleanup_old_autoedit_drafts

# Page Configuration - Optimized for Desktop Widescreen
st.set_page_config(
    page_title="PK Auto Edit Kit - Subtitle Studio Pro",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom Styling: Perfectionist 3-Column Studio, Indigo Navy & Luxury Aesthetics
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bai+Jamjuree:wght@600;700;800&family=Chakra+Petch:wght@600;700;800&family=Itim&family=Kanit:ital,wght@0,600;0,700;0,800;0,900;1,700;1,800&family=Mali:wght@600;700&family=Mitr:wght@500;600;700&family=Prompt:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Prompt', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* Header Bar - Luxury Deep Navy Gradient */
.pk-header {
    background: linear-gradient(135deg, #070D1E 0%, #0F1F3D 45%, #1E3A8A 85%, #1D4ED8 100%);
    padding: 16px 26px;
    border-radius: 16px;
    color: #FFFFFF;
    margin-bottom: 20px;
    box-shadow: 0 10px 28px -6px rgba(10, 25, 60, 0.45);
    border: 1px solid rgba(255, 255, 255, 0.14);
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 12px;
}

.pk-title {
    color: #FFFFFF !important;
    font-size: 1.85rem;
    font-weight: 800;
    margin: 0;
    letter-spacing: -0.5px;
    display: flex;
    align-items: center;
    gap: 10px;
}

.pk-edition-tag {
    font-size: 10px;
    font-weight: 700;
    background: linear-gradient(135deg, #F59E0B 0%, #D97706 100%);
    color: #FFFFFF;
    padding: 2px 8px;
    border-radius: 6px;
    letter-spacing: 0.8px;
    text-transform: uppercase;
    vertical-align: middle;
}

/* AI Status Pill */
.ai-status-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    font-weight: 600;
    padding: 6px 14px;
    border-radius: 999px;
    backdrop-filter: blur(10px);
}

.ai-status-ok {
    background: rgba(16, 185, 129, 0.16);
    border: 1px solid rgba(16, 185, 129, 0.45);
    color: #A7F3D0;
}

.ai-status-err {
    background: rgba(239, 68, 68, 0.16);
    border: 1px solid rgba(239, 68, 68, 0.45);
    color: #FECACA;
}

/* Studio Section Cards */
.studio-card {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 14px;
    padding: 15px 18px;
    margin-bottom: 14px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.03);
    transition: all 0.2s ease;
}

.studio-card:hover {
    border-color: #CBD5E1;
}

.studio-card-title {
    font-size: 0.95rem;
    font-weight: 700;
    color: #0F172A;
    margin-bottom: 10px;
    display: flex;
    align-items: center;
    gap: 6px;
}

/* Compact Smartphone Video Frame */
.video-preview-phone-frame {
    position: relative;
    max-width: 230px;
    margin: 0 auto 10px auto;
    border-radius: 20px;
    overflow: hidden;
    background: #000000;
    border: 3px solid #1E293B;
    box-shadow: 0 14px 32px -6px rgba(0, 0, 0, 0.45);
}

div[data-testid="stVideo"] {
    max-width: 100% !important;
    margin: 0 auto !important;
    background: #000000 !important;
    border-radius: 17px !important;
    overflow: hidden !important;
}

div[data-testid="stVideo"] video {
    width: 100% !important;
    height: auto !important;
    max-height: 400px !important;
    object-fit: contain !important;
    display: block !important;
    border-radius: 17px !important;
}

/* WebVTT Native Video Subtitle Styling */
video::cue {
    font-family: 'Kanit', sans-serif !important;
    font-weight: 900 !important;
    color: #FFE500 !important;
    background-color: transparent !important;
    text-shadow: 2px 2px 0px #000, -2px -2px 0px #000, 2px -2px 0px #000, -2px 2px 0px #000, 0px 3px 6px rgba(0,0,0,0.85) !important;
    font-size: 1.12rem !important;
}

/* Subtitle Overlay with Dynamic Vertical Position */
.video-sub-live-overlay {
    position: relative;
    z-index: 99;
    pointer-events: none;
    text-align: center;
    padding: 0 10px;
    width: 100%;
    box-sizing: border-box;
}

/* CapCut Bold Typography */
.capcut-bold-sub {
    font-family: 'Kanit', sans-serif !important;
    font-weight: 900 !important;
    line-height: 1.25 !important;
    letter-spacing: 0.3px !important;
    white-space: pre-wrap !important;
    text-align: center !important;
    display: inline-block !important;
    max-width: 95% !important;
    word-break: break-word !important;
    overflow-wrap: break-word !important;
    box-sizing: border-box !important;
    paint-order: stroke fill !important;
}

/* Primary Button Styling */
div.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #1E3A8A 0%, #1D4ED8 100%);
    color: #FFFFFF;
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 12px;
    padding: 10px 18px;
    font-weight: 600;
    font-size: 0.93rem;
    box-shadow: 0 4px 14px -3px rgba(29, 78, 216, 0.4);
    transition: all 0.15s ease;
}

div.stButton > button[kind="primary"]:hover {
    transform: translateY(-1px);
    background: linear-gradient(135deg, #1D4ED8 0%, #2563EB 100%);
    box-shadow: 0 8px 20px -3px rgba(37, 99, 235, 0.5);
}

/* Subtitle Studio Stats Bar */
.sub-studio-stats {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-bottom: 12px;
}

.sub-stat-pill {
    background: #F8FAFC;
    color: #334155;
    border: 1px solid #E2E8F0;
    font-size: 11.5px;
    font-weight: 600;
    padding: 4px 10px;
    border-radius: 999px;
    display: inline-flex;
    align-items: center;
    gap: 5px;
}

.sub-stat-pill-highlight {
    background: rgba(30, 58, 138, 0.08);
    color: #1E3A8A;
    border-color: rgba(30, 58, 138, 0.22);
}

.sub-stat-pill-success {
    background: rgba(16, 185, 129, 0.08);
    color: #065F46;
    border-color: rgba(16, 185, 129, 0.25);
}

/* Subtitle Container Wrappers (Native Streamlit Border Containers) */
div[data-testid="stVerticalBlockBorderWrapper"] {
    background: #FFFFFF !important;
    border-radius: 14px !important;
    border: 1px solid #E2E8F0 !important;
    padding: 12px 14px !important;
    margin-bottom: 12px !important;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.025) !important;
    transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
}

div[data-testid="stVerticalBlockBorderWrapper"]:hover {
    border-color: #93C5FD !important;
    box-shadow: 0 6px 18px -4px rgba(37, 99, 235, 0.12) !important;
}

/* Subtitle Top Bar */
.sub-card-top-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 6px;
    gap: 8px;
}

.sub-badge-id {
    background: linear-gradient(135deg, #0A1128 0%, #1E3A8A 100%);
    color: #FFFFFF !important;
    font-size: 11px;
    font-weight: 700;
    padding: 3px 9px;
    border-radius: 6px;
    letter-spacing: 0.4px;
    display: inline-flex;
    align-items: center;
    gap: 4px;
}

.sub-badge-capcut {
    background: #ECFDF5;
    color: #047857 !important;
    font-size: 11px;
    font-weight: 600;
    padding: 3px 9px;
    border-radius: 6px;
    border: 1px solid #A7F3D0;
    display: inline-flex;
    align-items: center;
    gap: 4px;
}

.sub-badge-source {
    background: #F1F5F9;
    color: #475569 !important;
    font-size: 11px;
    font-weight: 600;
    padding: 3px 8px;
    border-radius: 6px;
    border: 1px solid #E2E8F0;
    display: inline-flex;
    align-items: center;
    gap: 4px;
}

.sub-badge-active {
    background: #EFF6FF;
    color: #1D4ED8 !important;
    font-size: 11px;
    font-weight: 700;
    padding: 3px 8px;
    border-radius: 6px;
    border: 1px solid #BFDBFE;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    box-shadow: 0 0 8px rgba(37, 99, 235, 0.2);
}

/* Character Safe-Zone Meters */
.char-meter {
    font-size: 11px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 4px;
    display: inline-flex;
    align-items: center;
    gap: 4px;
}

.char-meter-safe {
    background: #F0FDF4;
    color: #15803D;
    border: 1px solid #BBF7D0;
}

.char-meter-warn {
    background: #FEFCE8;
    color: #A16207;
    border: 1px solid #FEF08A;
}

/* Input Fields inside Subtitle Review */
div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stTextInput"] input {
    font-size: 13.5px !important;
    font-weight: 500 !important;
    color: #0F172A !important;
    background: #F8FAFC !important;
    border-radius: 8px !important;
    border: 1px solid #CBD5E1 !important;
    padding: 7px 10px !important;
}

div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stTextInput"] input:focus {
    border-color: #2563EB !important;
    background: #FFFFFF !important;
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.15) !important;
}

div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stNumberInput"] input {
    font-size: 12.5px !important;
    font-weight: 600 !important;
    padding: 5px 8px !important;
    color: #0F172A !important;
    background: #F8FAFC !important;
}

/* Action Buttons inside Subtitle Cards */
div[data-testid="stVerticalBlockBorderWrapper"] button {
    border-radius: 8px !important;
    font-size: 12px !important;
    padding: 5px 8px !important;
    font-weight: 600 !important;
}

/* Sleek Scrollable Subtitle List */
.subs-scroll-container {
    max-height: 740px;
    overflow-y: auto;
    padding-right: 6px;
    padding-left: 2px;
    scrollbar-width: thin;
    scrollbar-color: #CBD5E1 transparent;
}

.subs-scroll-container::-webkit-scrollbar {
    width: 6px;
}

.subs-scroll-container::-webkit-scrollbar-thumb {
    background: #CBD5E1;
    border-radius: 10px;
}

.subs-scroll-container::-webkit-scrollbar-thumb:hover {
    background: #94A3B8;
}

/* Luxury Empty State */
.luxury-empty-state {
    background: linear-gradient(180deg, #FFFFFF 0%, #F8FAFC 100%);
    border: 1.5px dashed #CBD5E1;
    border-radius: 16px;
    padding: 28px 20px;
    text-align: center;
    color: #475569;
}

.luxury-empty-icon {
    font-size: 38px;
    margin-bottom: 10px;
}

.luxury-empty-title {
    font-size: 1.05rem;
    font-weight: 700;
    color: #0F172A;
    margin-bottom: 6px;
}

.luxury-empty-desc {
    font-size: 12.5px;
    color: #64748B;
    line-height: 1.6;
    margin-bottom: 16px;
}

.luxury-step-list {
    text-align: left;
    display: inline-block;
    font-size: 12.5px;
    line-height: 1.8;
    color: #334155;
    background: #FFFFFF;
    padding: 12px 18px;
    border-radius: 10px;
    border: 1px solid #E2E8F0;
    box-shadow: 0 1px 3px rgba(0,0,0,0.03);
}

/* ============================================================
   RESPONSIVE DESIGN: MOBILE (SMARTPHONE) & TABLET (iPAD)
   ============================================================ */

/* 1. iPad & Tablet Responsive Grid (Width 769px - 1120px) */
@media screen and (min-width: 769px) and (max-width: 1120px) {
    div[data-testid="stHorizontalBlock"]:not(div[data-testid="column"] div[data-testid="stHorizontalBlock"]) {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: wrap !important;
        gap: 16px !important;
    }
    /* Col 1: Controls (Left 50%) */
    div[data-testid="stHorizontalBlock"]:not(div[data-testid="column"] div[data-testid="stHorizontalBlock"]) > div[data-testid="column"]:nth-child(1) {
        flex: 1 1 calc(50% - 10px) !important;
        min-width: calc(50% - 10px) !important;
        max-width: calc(50% - 10px) !important;
    }
    /* Col 2: Live Monitor (Right 50%) */
    div[data-testid="stHorizontalBlock"]:not(div[data-testid="column"] div[data-testid="stHorizontalBlock"]) > div[data-testid="column"]:nth-child(2) {
        flex: 1 1 calc(50% - 10px) !important;
        min-width: calc(50% - 10px) !important;
        max-width: calc(50% - 10px) !important;
    }
    /* Col 3: Subtitle Studio (Bottom 100% Full Width) */
    div[data-testid="stHorizontalBlock"]:not(div[data-testid="column"] div[data-testid="stHorizontalBlock"]) > div[data-testid="column"]:nth-child(3) {
        flex: 1 1 100% !important;
        min-width: 100% !important;
        max-width: 100% !important;
        margin-top: 8px !important;
    }
    .video-preview-phone-frame {
        max-width: 290px !important;
    }
}

/* 2. Mobile Phone Responsive Optimization (Width <= 768px: iPhone, Android) */
@media screen and (max-width: 768px) {
    .block-container {
        padding-left: 0.75rem !important;
        padding-right: 0.75rem !important;
        padding-top: 0.75rem !important;
        padding-bottom: 2.5rem !important;
        max-width: 100% !important;
    }

    /* Header Bar Mobile */
    .pk-header {
        padding: 12px 14px !important;
        flex-direction: column !important;
        align-items: flex-start !important;
        gap: 8px !important;
        border-radius: 12px !important;
        margin-bottom: 12px !important;
    }
    .pk-title {
        font-size: 1.35rem !important;
        gap: 6px !important;
    }
    .ai-status-pill {
        font-size: 11px !important;
        padding: 4px 8px !important;
    }

    /* Stack 3 Main Columns */
    div[data-testid="stHorizontalBlock"]:not(div[data-testid="column"] div[data-testid="stHorizontalBlock"]) {
        display: flex !important;
        flex-direction: column !important;
        gap: 12px !important;
    }
    div[data-testid="stHorizontalBlock"]:not(div[data-testid="column"] div[data-testid="stHorizontalBlock"]) > div[data-testid="column"] {
        width: 100% !important;
        min-width: 100% !important;
        max-width: 100% !important;
        flex: 1 1 100% !important;
    }

    /* Phone Video Frame */
    .video-preview-phone-frame {
        max-width: min(280px, 85vw) !important;
        margin: 0 auto 12px auto !important;
    }

    /* Subtitle Card Precision Timing Controls (2x2 grid on mobile) */
    div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: wrap !important;
        gap: 6px !important;
    }
    /* Start Time (50%) */
    div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(1) {
        flex: 1 1 calc(50% - 4px) !important;
        min-width: calc(50% - 4px) !important;
        max-width: calc(50% - 4px) !important;
    }
    /* End Time (50%) */
    div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(2) {
        flex: 1 1 calc(50% - 4px) !important;
        min-width: calc(50% - 4px) !important;
        max-width: calc(50% - 4px) !important;
    }
    /* Preview Button (70%) */
    div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(3) {
        flex: 1 1 calc(70% - 4px) !important;
        min-width: calc(70% - 4px) !important;
    }
    /* Delete Button (30%) */
    div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(4) {
        flex: 1 1 calc(30% - 4px) !important;
        min-width: calc(30% - 4px) !important;
    }

    /* Expander Batch Actions (2x2 grid on mobile) */
    div[data-testid="stExpander"] div[data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: wrap !important;
        gap: 6px !important;
    }
    div[data-testid="stExpander"] div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
        flex: 1 1 calc(50% - 4px) !important;
        min-width: calc(50% - 4px) !important;
    }

    /* iOS Safari prevent zoom on text/number inputs */
    input[type="text"], input[type="number"], select, textarea {
        font-size: 16px !important;
    }

    /* Touch Hit Target Size */
    div.stButton > button {
        min-height: 44px !important;
        font-size: 14px !important;
    }

    /* Subtitle Scroll Container on Mobile */
    .subs-scroll-container {
        max-height: 520px !important;
        -webkit-overflow-scrolling: touch;
    }

    /* Studio Card Padding */
    .studio-card {
        padding: 12px 14px !important;
        margin-bottom: 10px !important;
    }
}
</style>
""", unsafe_allow_html=True)

# 1. Real-time AI status check
@st.cache_data(ttl=300)
def check_elevenlabs_status():
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key:
        return False, "ยังไม่ได้ระบุคีย์ API"
    try:
        res = requests.get(
            "https://api.elevenlabs.io/v1/models",
            headers={"xi-api-key": key},
            timeout=3
        )
        if res.status_code == 200:
            return True, "พร้อมใช้งาน"
        else:
            return False, f"รหัส {res.status_code}"
    except Exception:
        return False, "ข้อผิดพลาดเครือข่าย"

@st.cache_data(ttl=300)
def check_groq_status():
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        return False, "ยังไม่ได้ระบุคีย์"
    try:
        res = requests.get(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {key}"},
            timeout=3
        )
        if res.status_code == 200:
            return True, "พร้อมใช้งาน (เร็วพิเศษ)"
        return False, f"รหัส {res.status_code}"
    except Exception:
        return False, "ข้อผิดพลาดเครือข่าย"

@st.cache_data(ttl=300)
def check_gemini_status():
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        return False, "ยังไม่ได้ระบุคีย์"
    try:
        res = requests.get(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash?key={key}",
            timeout=3
        )
        if res.status_code == 200:
            return True, "พร้อมใช้งาน (Gemini 3.8 Flash)"
        return False, f"รหัส {res.status_code}"
    except Exception:
        return False, "ข้อผิดพลาดเครือข่าย"

ai_is_ok, ai_msg = check_elevenlabs_status()
groq_is_ok, groq_msg = check_groq_status()
gemini_is_ok, gemini_msg = check_gemini_status()

status_pills = []
if groq_is_ok:
    status_pills.append(f'<div class="ai-status-pill ai-status-ok">⚡ Groq Whisper: {groq_msg}</div>')
else:
    status_pills.append(f'<div class="ai-status-pill ai-status-err">⚡ Groq Whisper: {groq_msg}</div>')

if gemini_is_ok:
    status_pills.append(f'<div class="ai-status-pill ai-status-ok">✨ Gemini 3.8: {gemini_msg}</div>')
else:
    status_pills.append(f'<div class="ai-status-pill ai-status-err">✨ Gemini: {gemini_msg}</div>')

if ai_is_ok:
    status_pills.append(f'<div class="ai-status-pill ai-status-ok">🟢 ElevenLabs: {ai_msg}</div>')
else:
    status_pills.append(f'<div class="ai-status-pill ai-status-err">🔴 ElevenLabs: {ai_msg}</div>')
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "192.168.1.170"

local_ip = get_local_ip()
status_pills.append(f'<div class="ai-status-pill" style="background:rgba(37,99,235,0.18); border:1px solid rgba(147,197,253,0.4); color:#DBEAFE;">📱 มือถือ/iPad: <b>http://{local_ip}:8501</b></div>')

status_html = f'<div style="display:flex; gap:8px; flex-wrap:wrap; align-items:center;">{"".join(status_pills)}</div>'

# Header Bar
st.markdown(f"""
<div class="pk-header">
    <div class="pk-title">
        ⚡ PK Auto Edit Kit
        <span class="pk-edition-tag">Studio Pro</span>
    </div>
    <div>{status_html}</div>
</div>
""", unsafe_allow_html=True)

# 3-Column Desktop Studio Layout (Controls 30% | Live Monitor 31% | Subtitle Review 39%)
col_controls, col_monitor, col_subs = st.columns([1.05, 1.1, 1.35], gap="medium")

# ==========================================
# COLUMN 1: CONTROLS & SETTINGS (สตูดิโอตั้งค่า)
# ==========================================
with col_controls:
    st.markdown("### ⚙️ สตูดิโอตั้งค่า (Controls)")

    # 1. Video Source & AI Engine
    with st.container():
        st.markdown('<div class="studio-card">', unsafe_allow_html=True)
        st.markdown('<div class="studio-card-title">📂 1. เลือกไฟล์วิดีโอ & เครื่องยนต์ AI</div>', unsafe_allow_html=True)

        up_file = st.file_uploader(
            "📤 อัปโหลดไฟล์วิดีโอ (คลิก Browse files หรือลากไฟล์มาวางที่นี่):",
            type=["mp4", "mov", "mkv", "avi"],
            help="รองรับไฟล์วิดีโอ .mp4, .mov ทุกขนาด อัปโหลดได้ทันทีจากคอมพิวเตอร์ โทรศัพท์มือถือ และ iPad"
        )

        video_path = None
        if up_file is not None:
            upload_dir = os.path.join(tempfile.gettempdir(), "auto_edit_uploads")
            os.makedirs(upload_dir, exist_ok=True)
            saved_upload_path = os.path.join(upload_dir, up_file.name)
            with open(saved_upload_path, "wb") as f:
                f.write(up_file.getbuffer())
            video_path = saved_upload_path
            st.session_state["uploaded_video_path"] = saved_upload_path
            st.success(f"✅ อัปโหลดสำเร็จ: `{up_file.name}` ({up_file.size / (1024*1024):.1f} MB)")
        elif "uploaded_video_path" in st.session_state and os.path.exists(st.session_state["uploaded_video_path"]):
            video_path = st.session_state["uploaded_video_path"]
            st.caption(f"✅ ไฟล์ปัจจุบัน: `{os.path.basename(video_path)}`")
        else:
            video_path = None

        # AI Speech Engine selection
        st.markdown("---")
        st.markdown("**🤖 AI ถอดเสียง (STT Engine):**")
        stt_engine_choice = st.selectbox(
            "เลือกเอนจิน AI:",
            options=[
                "🎯 ElevenLabs Scribe STT (โมเดลหลัก - แม่นยำสูงสุด)",
                "✨ Google Gemini 3.8 Flash (โมเดลใหม่ล่าสุด - มัลติโมดอล)",
                "⚡ Groq Cloud - Whisper Large v3 / Turbo (เร็วพิเศษ)"
            ],
            index=0,
            help="เลือกเอนจิน AI: ElevenLabs แม่นยำสูงสุด, Gemini 3.8 Flash รุ่นใหม่ล่าสุด, หรือ Groq Whisper ความเร็วสูง",
            label_visibility="collapsed"
        )
        st.markdown('</div>', unsafe_allow_html=True)

    # 2. Typography & Layout
    with st.container():
        st.markdown('<div class="studio-card">', unsafe_allow_html=True)
        st.markdown('<div class="studio-card-title">🔤 2. ตัวหนังสือ & ฟอนต์ (Auto-Fit)</div>', unsafe_allow_html=True)

        font_options = [
            "Kanit (คณิต BD)",
            "MazdaTypeTH-Bold (มาสด้า โบลด์)",
            "Prompt (พร้อมท์)",
            "Mitr (มิตร)",
            "Chakra Petch (จักรเพชร)",
            "Bai Jamjuree (ใบจามจุรี)",
            "Itim (ไอติม)",
            "Mali (มะลิ)"
        ]
        chosen_font = st.selectbox("เลือกฟอนต์:", options=font_options, index=0)

        f_c1, f_c2 = st.columns(2)
        with f_c1:
            lines_mode = st.selectbox("จำนวนแถว:", options=["1 แถว (แนะนำ)", "2 แถว (ประโยคยาว)"], index=0)
        with f_c2:
            font_size_val = st.slider("ขนาดตัวอักษร:", min_value=6.0, max_value=14.0, value=8.5, step=0.5, help="ขนาด 8.5 พอดีกับหน้าจอ ไม่ล้นคลิปแน่นอน")

        max_words = st.slider("คำสูงสุดต่อแถว:", min_value=3, max_value=8, value=5, step=1, help="ควบคุมให้ตัดแบ่งเป็นก้อนคำสั้นกระชับ")
        letter_spacing = st.slider("ระยะห่างตัวหนังสือ (Letter Spacing):", min_value=0.0, max_value=8.0, value=3.5, step=0.5, help="เพิ่มช่องไฟระหว่างตัวอักษรให้อ่านง่าย โปร่ง สบายตา ไม่เบียดติดกัน")

        enable_ai_refine = st.checkbox(
            "✨ ขัดเกลาภาษาไทย & วรรคตอนอัจฉริยะด้วย Gemini LLM (AI Polish)",
            value=True,
            help="ตรวจทานให้คำในประโยคเขียนติดกันตามหลักภาษาไทย และเว้นวรรคเฉพาะจุดที่ถูกต้อง เช่น คั่นชื่อแบรนด์, ภาษาอังกฤษ หรือตัวเลข"
        )

        # Color & Stroke
        st.markdown("**สีข้อความหลัก (Base Color):**")
        color_presets = {
            "⚪ ขาวสด (#FFFFFF) [แบบคลิปคู่แข่ง]": "#FFFFFF",
            "🟡 เหลือง CapCut (#FFE500)": "#FFE500",
            "🟢 เขียวนีออน (#10B981)": "#10B981",
            "🔵 ฟ้าไซแอน (#06B6D4)": "#06B6D4",
            "🔴 แดงสด (#EF4444)": "#EF4444"
        }
        color_choice = st.radio("เลือกสีหลัก:", list(color_presets.keys()), index=0, horizontal=True, label_visibility="collapsed")
        chosen_hex = color_presets[color_choice]
        custom_color = st.color_picker("หรือระบุสีหลักที่ต้องการ:", value=chosen_hex)
        final_color_hex = custom_color

        h = final_color_hex.lstrip('#')
        rgb_color = [int(h[i:i+2], 16) / 255.0 for i in (0, 2, 4)]

        b_c1, b_c2 = st.columns(2)
        with b_c1:
            stroke_val = st.slider("ขอบดำ (Stroke):", min_value=0, max_value=20, value=8, step=1)
        with b_c2:
            shadow_val = st.slider("เงา (Shadow %):", min_value=0, max_value=100, value=80, step=5)

        # ----------------------------------------------------
        # Karaoke Word Focus & Animations (แบบคลิปคู่แข่ง & หลากหลาย)
        # ----------------------------------------------------
        st.markdown("---")
        st.markdown("**🎯 แอนิเมชัน & โฟกัสคำพูด (Word Focus Animation):**")
        karaoke_mode = st.toggle(
            "🔥 เปิดไฮไลต์คำพูดตามจังหวะเสียง (Word Focus)",
            value=True,
            help="เปลี่ยนสีเน้นเฉพาะคำที่กำลังพูดทีละคำ พร้อมแอนิเมชันเคลื่อนไหวเหมือนคลิปตัวอย่างคู่แข่ง"
        )

        if karaoke_mode:
            focus_presets = {
                "🔴 แดงสปอร์ต (#FF1E27) [เหมือนคู่แข่ง]": "#FF1E27",
                "🟡 เหลืองนีออน (#FFE500)": "#FFE500",
                "🟢 เขียวนีออน (#10B981)": "#10B981",
                "🔵 ฟ้าไซแอน (#06B6D4)": "#06B6D4",
                "🟠 ส้มสด (#F97316)": "#F97316"
            }
            focus_choice = st.radio(
                "สีคำที่กำลังพูด (Focus Color):",
                list(focus_presets.keys()),
                index=0,
                horizontal=True
            )
            focus_chosen_hex = focus_presets[focus_choice]
            custom_focus_color = st.color_picker("หรือระบุสีโฟกัสที่ต้องการ:", value=focus_chosen_hex)
            final_focus_hex = custom_focus_color

            anim_presets = {
                "💥 ขยายเด้ง (Pop Bounce - แนะนำแบบคู่แข่ง)": "pop",
                "⚡ ขยายค้างทั้งคำ (Zoom Active 1.15x)": "zoom",
                "✨ นีออนโกลว์เรืองแสง (Neon Glow Pulse)": "glow",
                "🌊 กระโดดยกตัว (Jump / Lift Up)": "jump",
                "🎯 ไฮไลต์สีนิ่งหรู (Clean Color Only)": "none"
            }
            selected_anim_label = st.selectbox(
                "🎬 รูปแบบ Animation คำที่กำลังพูด:",
                options=list(anim_presets.keys()),
                index=0,
                help="เลือกแอนิเมชันที่ต้องการ ทั้ง 5 รูปแบบใช้งานได้จริงทั้งในวิดีโอพรีวิว, CapCut และไฟล์ MP4!"
            )
            anim_type = anim_presets[selected_anim_label]
            pop_anim = (anim_type != "none")
        else:
            final_focus_hex = final_color_hex
            anim_type = "none"
            pop_anim = False

        h_f = final_focus_hex.lstrip('#')
        focus_rgb = [int(h_f[i:i+2], 16) / 255.0 for i in (0, 2, 4)]

        # Subtitle Vertical Position Slider (Real-Time Up/Down)
        st.markdown("---")
        vert_pos_pct = st.slider(
            "↕️ ตำแหน่งความสูงซับ (Vertical Position):",
            min_value=55,
            max_value=92,
            value=82,
            step=1,
            help="82% คือระยะ Lower-Third ด้านล่างมาตรฐาน สามารถเลื่อนขึ้นหรือลงตามองค์ประกอบภาพได้สดๆ"
        )
        st.markdown('</div>', unsafe_allow_html=True)

    # 3. Silence Cut
    with st.container():
        st.markdown('<div class="studio-card">', unsafe_allow_html=True)
        st.markdown('<div class="studio-card-title">✂️ 3. การตัดเดดแอร์ (Silence Cut)</div>', unsafe_allow_html=True)
        cut_silence_enabled = st.toggle("เปิดตัดเสียงเงียบอัตโนมัติ", value=True, help="หากเปิด จะตัดจังหวะเงียบที่ไม่พูดออก หากปิด จะคงคลิปเดิมไว้ทั้งหมด")
        pacing = st.select_slider(
            "จังหวะการตัด:",
            options=["ผ่อนคลาย", "มาตรฐาน (แนะนำ)", "กระชับเร็ว"],
            value="มาตรฐาน (แนะนำ)"
        )
        if pacing == "กระชับเร็ว":
            silence_db = -28.0
            min_silence = 0.30
            padding = 0.04
        elif pacing == "ผ่อนคลาย":
            silence_db = -32.0
            min_silence = 0.60
            padding = 0.08
        else:
            silence_db = -30.0
            min_silence = 0.40
            padding = 0.06
        st.markdown('</div>', unsafe_allow_html=True)

    # Step 1 Button
    btn_transcribe = st.button("🔍 ขั้นที่ 1: วิเคราะห์คลิป & ถอดเสียง (AI Transcribe)", type="primary", use_container_width=True)


# ==========================================
# COLUMN 2: LIVE MONITOR & EXPORT (จอมอนิเตอร์ & ส่งออก)
# ==========================================
with col_monitor:
    st.markdown("### 📱 จอมอนิเตอร์พรีวิว (Live Monitor)")

    preview_clean_font = chosen_font.split("(")[0].strip()
    if "Kanit" in chosen_font or "คณิต" in chosen_font:
        preview_clean_font = "Kanit"
    elif "Mazda" in chosen_font:
        preview_clean_font = "Prompt"

    has_cached_subs = "cached_subtitles" in st.session_state and st.session_state.get("cached_video_path") == video_path

    # Smartphone Preview Frame with Synchronized Subtitles (Pure & Clean)
    if video_path and os.path.exists(video_path):
        v_info = get_video_info(video_path)

        # Dynamic focus cue style based on chosen animation type
        if anim_type == "glow":
            focus_cue_css = f"color: {final_focus_hex} !important; font-weight: 900 !important; text-shadow: 0 0 10px {final_focus_hex}, 0 0 22px {final_focus_hex}, 2px 2px 0 #000, -2px -2px 0 #000 !important;"
        elif anim_type in ("pop", "zoom"):
            focus_cue_css = f"color: {final_focus_hex} !important; font-weight: 900 !important; text-shadow: 0 0 8px {final_focus_hex}, 2px 2px 0 #000, -2px -2px 0 #000 !important; font-size: 1.24rem !important;"
        elif anim_type == "jump":
            focus_cue_css = f"color: {final_focus_hex} !important; font-weight: 900 !important; text-shadow: 0 -2px 8px {final_focus_hex}, 2px 2px 0 #000, -2px -2px 0 #000 !important; font-size: 1.18rem !important;"
        else:
            focus_cue_css = f"color: {final_focus_hex} !important; font-weight: 900 !important; text-shadow: 2px 2px 0 #000, -2px -2px 0 #000, 2px -2px 0 #000, -2px 2px 0 #000 !important;"

        st.markdown(f"""
        <style>
        video::cue {{
            font-family: '{preview_clean_font}', sans-serif !important;
            font-weight: 900 !important;
            color: {final_color_hex} !important;
            background-color: transparent !important;
            text-shadow: 2px 2px 0px #000, -2px -2px 0px #000, 2px -2px 0px #000, -2px 2px 0px #000, 0px 3px 6px rgba(0,0,0,0.85) !important;
            font-size: 1.14rem !important;
            letter-spacing: {letter_spacing:.1f}px !important;
            word-spacing: {letter_spacing * 2.0:.1f}px !important;
        }}
        video::cue(c.focus) {{
            {focus_cue_css}
        }}
        </style>
        """, unsafe_allow_html=True)

        st.markdown('<div class="video-preview-phone-frame">', unsafe_allow_html=True)

        preview_seek = int(st.session_state.get("preview_seek_time", 0))

        # Synchronized native WebVTT subtitles in video player
        if has_cached_subs and st.session_state["cached_subtitles"]:
            vtt_content = generate_webvtt(
                st.session_state["cached_subtitles"],
                use_source_time=True,
                line_position=vert_pos_pct,
                karaoke_mode=karaoke_mode
            )
            st.video(video_path, start_time=preview_seek, subtitles=vtt_content)
        else:
            st.video(video_path, start_time=preview_seek)

        st.markdown('</div>', unsafe_allow_html=True)

        st.caption(f"ความยาว: **{v_info['duration']:.2f}s** • ขนาด: **{v_info['width']}x{v_info['height']}** • **{v_info['fps']} fps**")
    else:
        st.markdown("""
        <div style="border: 2px dashed #CBD5E1; border-radius: 16px; padding: 48px 20px; text-align: center; background: #F8FAFC; margin-top: 16px; margin-bottom: 24px;">
            <div style="font-size: 3.5rem; margin-bottom: 12px;">🎬</div>
            <div style="font-size: 1.15rem; font-weight: 700; color: #1E293B; margin-bottom: 8px;">พร้อมรับวิดีโอของคุณ</div>
            <div style="font-size: 0.92rem; color: #64748B; max-width: 280px; margin: 0 auto; line-height: 1.5;">
                กรุณากดปุ่ม <b style="color: #2563EB;">Browse files</b> ที่แผงด้านซ้ายเพื่อเลือกไฟล์วิดีโอ (.mp4, .mov)
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Metrics Summary (if analyzed)
    if "cached_analysis" in st.session_state and st.session_state.get("cached_video_path") == video_path:
        an = st.session_state["cached_analysis"]
        m_c1, m_c2, m_c3 = st.columns(3)
        m_c1.metric("เดิม", f"{an['original_duration']:.1f}s")
        m_c2.metric("หลังตัด", f"{an['final_duration']:.1f}s")
        m_c3.metric("ประหยัด", f"-{an['silence_saved']:.1f}s")

    st.markdown("---")

    # Step 2A: Send to CapCut Desktop
    st.markdown("#### 🚀 ขั้นที่ 2: ส่งเข้า CapCut Desktop")
    custom_proj_name = st.text_input("ตั้งชื่อโปรเจกต์ใน CapCut:", value=f"AutoEdit_{time.strftime('%Y%m%d_%H%M%S')}")
    btn_final_capcut = st.button("🚀 ส่งเข้า CapCut Desktop ทันที", type="primary", use_container_width=True)

    # Calculate CapCut Y coordinate from vertical percentage
    capcut_y_pos = round((0.5 - (vert_pos_pct / 100.0)) * 2.0, 3)

    if btn_final_capcut:
        if not has_cached_subs or not st.session_state.get("cached_subtitles"):
            st.error("⚠️ กรุณากดปุ่ม '🔍 ขั้นที่ 1: วิเคราะห์คลิป & ถอดเสียง' ก่อนส่งเข้า CapCut ครับ")
        else:
            with st.spinner("📦 กำลังสร้างโปรเจกต์ใน CapCut Desktop พร้อมฟอนต์และสไตล์ที่กำหนด..."):
                analysis_data = st.session_state["cached_analysis"]
                edited_subs = st.session_state["cached_subtitles"]

                capcut_stroke_width = (stroke_val / 10.0) * 0.018
                capcut_shadow_alpha = shadow_val / 100.0

                capcut_dir = create_capcut_project(
                    video_path=video_path,
                    keep_segments=analysis_data["keep_segments"],
                    subtitles=edited_subs,
                    project_name=custom_proj_name,
                    font_name=chosen_font,
                    font_size=font_size_val,
                    text_color=rgb_color,
                    focus_color=focus_rgb,
                    stroke_width=capcut_stroke_width,
                    stroke_color=[0.0, 0.0, 0.0],
                    shadow_alpha=capcut_shadow_alpha,
                    shadow_distance=5.0,
                    text_y_position=capcut_y_pos,
                    letter_spacing=letter_spacing,
                    karaoke_mode=karaoke_mode,
                    anim_type=anim_type,
                    enable_pop=pop_anim
                )
                st.balloons()
                st.success(f"🎉 **สร้างโปรเจกต์ใน CapCut Desktop สำเร็จสมบูรณ์!**")
                st.info(f"📂 **โฟลเดอร์โปรเจกต์:** `{capcut_dir}`\n\n👉 **เปิด CapCut Desktop บนเครื่อง จะพบโปรเจกต์ `{custom_proj_name}` ขึ้นที่หน้าแรกทันที!**")

    # Step 2B: Direct MP4 Render & Download (No CapCut Required)
    st.markdown("---")
    st.markdown("#### 🎬 ดาวน์โหลดคลิปโดยตรง (Direct MP4)")
    btn_direct_mp4 = st.button("⚡ เรนเดอร์ไฟล์ MP4 ตัดต่อพร้อมซับ (สำหรับมือถือ)", use_container_width=True)

    if btn_direct_mp4:
        if not has_cached_subs or not st.session_state.get("cached_subtitles"):
            st.error("⚠️ กรุณากดปุ่ม '🔍 ขั้นที่ 1: วิเคราะห์คลิป & ถอดเสียง' ก่อนเรนเดอร์วิดีโอครับ")
        else:
            with st.spinner("⏳ กำลังตัดเดดแอร์ + ฝังซับไตเติลลงในคลิป MP4 ด้วย FFmpeg..."):
                analysis_data = st.session_state["cached_analysis"]
                edited_subs = st.session_state["cached_subtitles"]

                out_render_path = os.path.join(tempfile.gettempdir(), f"AutoEdit_{time.strftime('%Y%m%d_%H%M%S')}.mp4")
                rendered_file = render_video_with_subtitles(
                    video_path=video_path,
                    keep_segments=analysis_data["keep_segments"],
                    subtitles=edited_subs,
                    output_path=out_render_path,
                    font_name=chosen_font,
                    font_size=font_size_val,
                    text_color_hex=final_color_hex,
                    focus_color_hex=final_focus_hex,
                    stroke_val=stroke_val,
                    shadow_val=shadow_val,
                    vertical_position_pct=vert_pos_pct,
                    letter_spacing=letter_spacing,
                    karaoke_mode=karaoke_mode,
                    anim_type=anim_type,
                    enable_pop=pop_anim
                )

                if os.path.exists(rendered_file):
                    st.session_state["rendered_mp4_path"] = rendered_file
                    st.success("✅ เรนเดอร์คลิปวิดีโอพร้อมซับไตเติลเสร็จเรียบร้อย!")

    # If rendered MP4 is ready, provide direct download button
    if "rendered_mp4_path" in st.session_state and os.path.exists(st.session_state["rendered_mp4_path"]):
        with open(st.session_state["rendered_mp4_path"], "rb") as f_mp4:
            st.download_button(
                label="⬇️ คลิกเพื่อดาวน์โหลดคลิป (.mp4) เข้าเครื่อง/มือถือ",
                data=f_mp4.read(),
                file_name=f"AutoEdit_{os.path.basename(video_path or 'video')}.mp4",
                mime="video/mp4",
                use_container_width=True
            )

    # Clean Old Drafts button
    st.markdown("---")
    if st.button("🧹 ล้าง Draft เก่าใน CapCut", help="ลบโฟลเดอร์โปรเจกต์ทดสอบเก่าเพื่อประหยัดพื้นที่ฮาร์ดดิสก์", use_container_width=True):
        deleted = cleanup_old_autoedit_drafts(keep_recent=1)
        if deleted > 0:
            st.success(f"ล้างดราฟต์เก่าไป {deleted} โฟลเดอร์เรียบร้อย!")
        else:
            st.info("ไม่มีดราฟต์เก่าที่ต้องลบ")


# ==========================================
# COLUMN 3: PERFECTIONIST SUBTITLE STUDIO (ตรวจทาน & ปรับเวลา)
# ==========================================
with col_subs:
    st.markdown("### 📝 ตรวจทาน & ปรับเวลา (Subtitle Studio)")

    # Execute Transcription when Step 1 is clicked
    if btn_transcribe:
        if not video_path or not os.path.exists(video_path):
            st.error("⚠️ กรุณากดปุ่ม 'Browse files' อัปโหลดไฟล์วิดีโอด้านบนก่อนเริ่มวิเคราะห์ครับ")
        else:
            if "ElevenLabs" in stt_engine_choice:
                engine_label = "ElevenLabs Scribe STT"
                pref_engine = "elevenlabs"
            elif "Gemini" in stt_engine_choice:
                engine_label = "Google Gemini 3.8 Flash"
                pref_engine = "gemini"
            else:
                engine_label = "Groq Whisper Large v3 / Turbo"
                pref_engine = "groq"

            with st.spinner(f"🤖 กำลังวิเคราะห์คลิปและถอดเสียงด้วย {engine_label}..."):
                if cut_silence_enabled:
                    analysis = analyze_and_cut(
                        video_path,
                        noise_threshold_db=silence_db,
                        min_silence_duration=min_silence,
                        padding=padding
                    )
                else:
                    v_dur = get_video_info(video_path)["duration"]
                    analysis = {
                        "original_duration": v_dur,
                        "final_duration": v_dur,
                        "silence_saved": 0.0,
                        "keep_segments": [{"start": 0.0, "end": v_dur, "duration": v_dur}]
                    }

                words = transcribe_audio(
                    video_path,
                    preferred_engine=pref_engine,
                    keep_segments=analysis["keep_segments"]
                )

                subtitles = chunk_word_timestamps(
                    words,
                    keep_segments=analysis["keep_segments"],
                    caption_mode="sentence",
                    lines_mode="1 แถว" if "1 แถว" in lines_mode else "2 แถว",
                    max_words_per_line=max_words,
                    max_chars_per_line=22 if "1 แถว" in lines_mode else 46,
                    pause_threshold=0.22
                )

                # Optional AI Refinement (Pass 2) via Gemini LLM
                if enable_ai_refine and os.environ.get("GEMINI_API_KEY"):
                    with st.spinner("✨ กำลังขัดเกลาไวยากรณ์ไทยและจัดวรรคตอนด้วย Gemini LLM..."):
                        try:
                            from modules.thai_refiner import refine_thai_captions_with_llm
                            refined_subs = refine_thai_captions_with_llm(subtitles)
                            if refined_subs:
                                subtitles = refined_subs
                        except Exception as e:
                            st.warning(f"⚠️ AI Polish warning: {e}")

                # Assign unique stable IDs
                timestamp_seed = int(time.time() * 1000)
                for idx, s in enumerate(subtitles):
                    s["id"] = f"sub_{timestamp_seed}_{idx}"

                st.session_state["cached_analysis"] = analysis
                st.session_state["cached_subtitles"] = subtitles
                st.session_state["raw_ai_subtitles"] = [dict(s) for s in subtitles]
                st.session_state["cached_video_path"] = video_path
                st.session_state["selected_sub_idx"] = 0
                st.session_state["preview_seek_time"] = 0
                st.rerun()

    # If we have cached transcription results
    if has_cached_subs and st.session_state["cached_subtitles"]:
        subs_list = st.session_state["cached_subtitles"]
        analysis_data = st.session_state.get("cached_analysis", {})
        keep_segs = analysis_data.get("keep_segments", [])

        # Ensure all items have unique IDs
        for idx, s in enumerate(subs_list):
            if "id" not in s:
                s["id"] = f"sub_{idx}"

        # 1. Studio Meta & Overview Stats Bar
        orig_d = analysis_data.get("original_duration", 0.0)
        final_d = analysis_data.get("final_duration", 0.0)
        mode_label = "1 แถว Auto-Fit" if "1 แถว" in lines_mode else "2 แถว"

        st.markdown(f"""
        <div class="sub-studio-stats">
            <span class="sub-stat-pill sub-stat-pill-highlight">🎯 ทั้งหมด: <b>{len(subs_list)} ท่อน</b></span>
            <span class="sub-stat-pill">⏱️ คลิปเดิม: <b>{orig_d:.1f}s</b></span>
            <span class="sub-stat-pill sub-stat-pill-success">✂️ ไทม์ไลน์ CapCut: <b>{final_d:.1f}s</b></span>
            <span class="sub-stat-pill">📐 <b>{mode_label}</b></span>
        </div>
        """, unsafe_allow_html=True)

        # 2. Batch Tools & Actions Bar (Collapsible)
        with st.expander("⚡ เครื่องมือจัดการเวลาทั้งคลิป & เพิ่ม/ลบท่อน (Batch Actions)", expanded=False):
            st.caption("ขยับเวลาซับไตเติลทุกท่อนพร้อมกันทีละนิด หรือเพิ่มท่อนคำพูดใหม่:")
            t_col1, t_col2, t_col3, t_col4 = st.columns(4)
            with t_col1:
                btn_shift_minus = st.button("⏪ เร็วขึ้น 0.1s", use_container_width=True, help="เลื่อนเวลาเริ่มต้น-สิ้นสุดของทุกท่อนขึ้น 0.1 วินาที")
            with t_col2:
                btn_shift_plus = st.button("ช้าลง 0.1s ⏩", use_container_width=True, help="เลื่อนเวลาเริ่มต้น-สิ้นสุดของทุกท่อนถอย 0.1 วินาที")
            with t_col3:
                btn_add_new = st.button("➕ เพิ่มท่อนใหม่", use_container_width=True, help="เพิ่มท่อนข้อความว่างต่อท้ายรายการ")
            with t_col4:
                btn_reset_raw = st.button("🔄 คืนค่า AI เดิม", use_container_width=True, help="ล้างการแก้ไขทั้งหมดแล้วคืนค่าที่ AI ถอดเสียงไว้เดิม")

            # Handle Shift Minus
            if btn_shift_minus:
                for s in subs_list:
                    sid = s["id"]
                    new_s = max(0.0, round(float(s.get("source_start", 0.0)) - 0.1, 3))
                    new_e = max(0.1, round(float(s.get("source_end", 0.0)) - 0.1, 3))
                    s["source_start"] = new_s
                    s["source_end"] = new_e
                    if keep_segs:
                        s["timeline_start"] = round(map_timestamp_to_edited_timeline(new_s, keep_segs), 3)
                        s["timeline_end"] = round(map_timestamp_to_edited_timeline(new_e, keep_segs), 3)
                    else:
                        s["timeline_start"] = new_s
                        s["timeline_end"] = new_e
                    s["duration"] = round(max(0.2, s["timeline_end"] - s["timeline_start"]), 3)
                    if f"start_val_{sid}" in st.session_state:
                        st.session_state[f"start_val_{sid}"] = round(new_s, 2)
                    if f"end_val_{sid}" in st.session_state:
                        st.session_state[f"end_val_{sid}"] = round(new_e, 2)
                st.session_state["cached_subtitles"] = subs_list
                st.rerun()

            # Handle Shift Plus
            if btn_shift_plus:
                for s in subs_list:
                    sid = s["id"]
                    new_s = max(0.0, round(float(s.get("source_start", 0.0)) + 0.1, 3))
                    new_e = max(0.1, round(float(s.get("source_end", 0.0)) + 0.1, 3))
                    s["source_start"] = new_s
                    s["source_end"] = new_e
                    if keep_segs:
                        s["timeline_start"] = round(map_timestamp_to_edited_timeline(new_s, keep_segs), 3)
                        s["timeline_end"] = round(map_timestamp_to_edited_timeline(new_e, keep_segs), 3)
                    else:
                        s["timeline_start"] = new_s
                        s["timeline_end"] = new_e
                    s["duration"] = round(max(0.2, s["timeline_end"] - s["timeline_start"]), 3)
                    if f"start_val_{sid}" in st.session_state:
                        st.session_state[f"start_val_{sid}"] = round(new_s, 2)
                    if f"end_val_{sid}" in st.session_state:
                        st.session_state[f"end_val_{sid}"] = round(new_e, 2)
                st.session_state["cached_subtitles"] = subs_list
                st.rerun()

            # Handle Add Subtitle
            if btn_add_new:
                last_end = float(subs_list[-1]["source_end"]) if subs_list else 0.0
                new_start_t = round(last_end + 0.05, 3)
                new_end_t = round(new_start_t + 1.8, 3)
                new_item = {
                    "id": f"sub_{int(time.time()*1000)}",
                    "text": "ข้อความใหม่...",
                    "source_start": new_start_t,
                    "source_end": new_end_t,
                    "timeline_start": round(map_timestamp_to_edited_timeline(new_start_t, keep_segs), 3) if keep_segs else new_start_t,
                    "timeline_end": round(map_timestamp_to_edited_timeline(new_end_t, keep_segs), 3) if keep_segs else new_end_t,
                    "duration": 1.8
                }
                subs_list.append(new_item)
                st.session_state["cached_subtitles"] = subs_list
                st.session_state["selected_sub_idx"] = len(subs_list) - 1
                st.rerun()

            # Handle Reset AI
            if btn_reset_raw and "raw_ai_subtitles" in st.session_state:
                raw_copies = [dict(s) for s in st.session_state["raw_ai_subtitles"]]
                for s in raw_copies:
                    sid = s["id"]
                    if f"start_val_{sid}" in st.session_state:
                        st.session_state[f"start_val_{sid}"] = round(float(s["source_start"]), 2)
                    if f"end_val_{sid}" in st.session_state:
                        st.session_state[f"end_val_{sid}"] = round(float(s["source_end"]), 2)
                    if f"sub_txt_{sid}" in st.session_state:
                        st.session_state[f"sub_txt_{sid}"] = s["text"]
                st.session_state["cached_subtitles"] = raw_copies
                st.rerun()

        # 3. Quick Search Bar
        search_kw = st.text_input(
            "🔍 ค้นหาคำในซับไตเติล (Quick Search):",
            placeholder="พิมพ์คำที่ต้องการค้นหา เช่น มาสด้า, โปรโมชั่น, บาท...",
            help="พิมพ์คำเพื่อกรองเฉพาะท่อนซับไตเติลที่มีคำนั้นขึ้นมาตรวจทานได้ทันที"
        )

        # 4. Render Subtitle Cards
        selected_sub_idx = st.session_state.get("selected_sub_idx", 0)

        # Filter items if search keyword is active
        displayed_items = [
            (i, s) for i, s in enumerate(subs_list)
            if not search_kw or search_kw.strip().lower() in s["text"].lower()
        ]

        if not displayed_items:
            st.warning(f"🔍 ไม่พบข้อความที่มีคำว่า '{search_kw}'")
        else:
            st.markdown('<div class="subs-scroll-container">', unsafe_allow_html=True)

            for i, sub in displayed_items:
                sub_id = sub["id"]
                s_start = float(sub.get('source_start', sub.get('timeline_start', 0.0)))
                s_end = float(sub.get('source_end', sub.get('timeline_end', 0.0)))
                dur = max(0.1, s_end - s_start)
                tl_start = float(sub.get('timeline_start', 0.0))
                tl_end = float(sub.get('timeline_end', 0.0))
                is_active = (i == selected_sub_idx)

                # Native Bordered Container for unified luxury card look
                with st.container(border=True):
                    # Top Row: Header Badges
                    active_badge = f'<span class="sub-badge-active">🌟 กำลังพรีวิวบนจอ</span>' if is_active else ''
                    card_header_html = (
                        f'<div class="sub-card-top-bar">'
                        f'<div style="display:flex; align-items:center; gap:6px;">'
                        f'<span class="sub-badge-id">ท่อน #{i+1}</span>{active_badge}'
                        f'</div>'
                        f'<div style="display:flex; align-items:center; gap:6px; flex-wrap:wrap;">'
                        f'<span class="sub-badge-source">⏱️ {s_start:.2f}s - {s_end:.2f}s</span>'
                        f'<span class="sub-badge-capcut">✂️ CapCut: {tl_start:.2f}s - {tl_end:.2f}s</span>'
                        f'</div>'
                        f'</div>'
                    )
                    st.markdown(card_header_html, unsafe_allow_html=True)

                    # Subtitle Text Input
                    new_text = st.text_input(
                        f"ข้อความท่อน #{i+1}",
                        value=sub["text"],
                        key=f"sub_txt_{sub_id}",
                        placeholder="พิมพ์ข้อความซับไตเติล...",
                        label_visibility="collapsed"
                    )

                    # Safe-Zone Indicator & Character Count
                    char_count = len(new_text.replace("\n", "").strip())
                    if char_count <= 24:
                        char_meter_html = f'<span class="char-meter char-meter-safe">🟢 {char_count} ตัวอักษร (พอดี 1 แถว ไม่ล้นคลิป)</span>'
                    else:
                        char_meter_html = f'<span class="char-meter char-meter-warn">🟡 {char_count} ตัวอักษร (ยาวเกิน 24 ตัว แนะนำแบ่งท่อน)</span>'

                    meter_html = (
                        f'<div style="display:flex; justify-content:space-between; align-items:center; margin-top:-4px; margin-bottom:8px;">'
                        f'<div>{char_meter_html}</div>'
                        f'<div style="font-size:11.5px; color:#64748B;">ความยาวเสียง: <b>{dur:.2f} วินาที</b></div>'
                        f'</div>'
                    )
                    st.markdown(meter_html, unsafe_allow_html=True)

                    # Precision Timing Controls & Action Buttons Row
                    c_start, c_end, c_prev, c_del = st.columns([1.1, 1.1, 1.0, 0.45])

                    with c_start:
                        new_start = st.number_input(
                            f"🕒 เริ่ม (วิ) #{i+1}:",
                            min_value=0.0,
                            max_value=999.0,
                            value=round(s_start, 2),
                            step=0.05,
                            format="%.2f",
                            key=f"start_val_{sub_id}",
                            help="เวลาเริ่มพูดในคลิปต้นฉบับ"
                        )

                    with c_end:
                        new_end = st.number_input(
                            f"🏁 จบ (วิ) #{i+1}:",
                            min_value=0.0,
                            max_value=999.0,
                            value=round(s_end, 2),
                            step=0.05,
                            format="%.2f",
                            key=f"end_val_{sub_id}",
                            help="เวลาจบประโยคในคลิปต้นฉบับ"
                        )

                    with c_prev:
                        st.write("")  # Visual alignment
                        if st.button("👁️ พรีวิว", key=f"btn_prev_{sub_id}", help="แสดงท่อนนี้บนจอมอนิเตอร์และเลื่อนคลิปไปยังวินาทีนี้ทันที", use_container_width=True):
                            st.session_state["selected_sub_idx"] = i
                            st.session_state["preview_seek_time"] = float(new_start)
                            st.rerun()

                    with c_del:
                        st.write("")  # Visual alignment
                        if st.button("🗑️", key=f"btn_del_{sub_id}", help=f"ลบท่อน #{i+1} ทิ้ง", use_container_width=True):
                            subs_list.pop(i)
                            st.session_state["cached_subtitles"] = subs_list
                            if st.session_state.get("selected_sub_idx", 0) >= len(subs_list):
                                st.session_state["selected_sub_idx"] = max(0, len(subs_list) - 1)
                            st.rerun()

                    # Dynamically update subtitle object in list
                    sub["text"] = new_text
                    sub["source_start"] = round(new_start, 3)
                    sub["source_end"] = round(new_end, 3)

                    if keep_segs:
                        sub["timeline_start"] = round(map_timestamp_to_edited_timeline(new_start, keep_segs), 3)
                        sub["timeline_end"] = round(map_timestamp_to_edited_timeline(new_end, keep_segs), 3)
                    else:
                        sub["timeline_start"] = round(new_start, 3)
                        sub["timeline_end"] = round(new_end, 3)

                    sub["duration"] = round(max(0.2, sub["timeline_end"] - sub["timeline_start"]), 3)

            st.markdown('</div>', unsafe_allow_html=True)
            st.session_state["cached_subtitles"] = subs_list

    else:
        # Luxury Empty State (Perfectionist Studio Design)
        st.markdown("""
        <div class="luxury-empty-state">
            <div class="luxury-empty-icon">🎬</div>
            <div class="luxury-empty-title">ห้องตรวจทาน & สตูดิโอปรับแต่งซับไตเติล</div>
            <div class="luxury-empty-desc">
                เมื่อกด <b>'🔍 ขั้นที่ 1: วิเคราะห์คลิป & ถอดเสียง'</b> ในสตูดิโอตั้งค่าด้านซ้าย<br>
                ประโยคภาษาไทยและช่วงเวลาที่ AI ถอดเสียงจะปรากฏที่นี่อย่างเป็นระเบียบ
            </div>
            <div class="luxury-step-list">
                ✨ <b>ความสามารถระดับ Perfectionist ในหน้านี้:</b><br>
                1️⃣ ตรวจสอบและแก้ไขคำพูดสดๆ ตัวหนังสืออัปเดตบนจอมอนิเตอร์ทันที<br>
                2️⃣ มีแถบวัด Safe-Zone แจ้งเตือนจำนวนตัวอักษร ไม่ให้ล้นขอบวิดีโอ 100%<br>
                3️⃣ ปรับเวลาเริ่ม-จบ ได้อิสระ ละเอียดระดับ 0.05 วินาที<br>
                4️⃣ ปุ่ม 👁️ พรีวิว กดปุ๊บ วิดีโอเลื่อนไปวินาทีนั้นพร้อมโชว์ซับบนจอสดๆ<br>
                5️⃣ เครื่องมือ Batch Shift ขยับเวลาซับทั้งคลิปพร้อมกันได้ในคลิกเดียว
            </div>
        </div>
        """, unsafe_allow_html=True)
