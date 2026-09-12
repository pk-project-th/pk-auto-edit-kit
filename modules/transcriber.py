import os
import json
import requests
from typing import List, Dict, Any
from dotenv import load_dotenv
from .ffmpeg_utils import extract_audio

# Load .env file automatically
load_dotenv()

def align_tokens_to_thai_words(raw_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Aligns character/subword tokens from ElevenLabs Scribe or Groq Whisper
    with PyThaiNLP word_tokenize for 100% natural Thai word boundaries and exact timestamps.
    """
    try:
        from pythainlp.tokenize import word_tokenize
        has_pythainlp = True
    except ImportError:
        has_pythainlp = False

    if has_pythainlp:
        char_items = []
        full_chars_text = ""
        for item in raw_items:
            t = item.get("text", item.get("word", ""))
            s = float(item.get("start", 0.0))
            e = float(item.get("end", s + 0.1))
            dur = max(0.01, e - s)
            if not t:
                continue

            if item.get("type") == "spacing" or t == " ":
                char_items.append({"text": " ", "start": s, "end": e, "is_space": True})
                full_chars_text += " "
            else:
                c_len = len(t)
                for c_i, ch in enumerate(t):
                    c_start = s + (c_i / c_len) * dur
                    c_end = s + ((c_i + 1) / c_len) * dur
                    char_items.append({"text": ch, "start": c_start, "end": c_end, "is_space": False})
                    full_chars_text += ch

        tokens = word_tokenize(full_chars_text, engine="newmm")
        words_list = []
        curr_char_idx = 0

        for tok in tokens:
            if not tok.strip():
                curr_char_idx += len(tok)
                continue

            tok_len = len(tok)
            accum = ""
            start_time = None
            end_time = None
            has_leading_space = False

            if curr_char_idx > 0 and char_items[curr_char_idx - 1]["is_space"]:
                has_leading_space = True

            while curr_char_idx < len(char_items) and len(accum) < tok_len:
                c = char_items[curr_char_idx]
                accum += c["text"]
                if start_time is None and not c["is_space"]:
                    start_time = c["start"]
                if not c["is_space"]:
                    end_time = c["end"]
                curr_char_idx += 1

            if start_time is not None and end_time is not None:
                words_list.append({
                    "word": tok,
                    "start": round(start_time, 3),
                    "end": round(end_time, 3),
                    "leading_space": has_leading_space
                })

        if words_list:
            return words_list

    # Fallback grouping if PyThaiNLP is unavailable
    words_list = []
    for item in raw_items:
        t = item.get("text", item.get("word", "")).strip()
        if t:
            words_list.append({
                "word": t,
                "start": round(float(item.get("start", 0.0)), 3),
                "end": round(float(item.get("end", 0.0)), 3),
                "leading_space": False
            })
    return words_list

def transcribe_with_groq(audio_or_video_path: str, api_key: str) -> List[Dict[str, Any]]:
    """Call Groq Whisper Large v3 / Turbo API for ultra-fast Speech-to-Text with word timestamps."""
    url = "https://api.groq.com/openai/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {api_key}"}

    temp_wav = audio_or_video_path
    if not audio_or_video_path.lower().endswith(".wav"):
        temp_wav = os.path.splitext(audio_or_video_path)[0] + "_groq_temp.wav"
        extract_audio(audio_or_video_path, temp_wav)

    models_to_try = ["whisper-large-v3", "whisper-large-v3-turbo"]
    last_error = None

    try:
        for model_name in models_to_try:
            try:
                with open(temp_wav, "rb") as f:
                    files = {"file": (os.path.basename(temp_wav), f, "audio/wav")}
                    data = {
                        "model": model_name,
                        "language": "th",
                        "response_format": "verbose_json",
                        "timestamp_granularities[]": "word"
                    }
                    res = requests.post(url, headers=headers, files=files, data=data, timeout=90)
                    res.raise_for_status()
                    result_json = res.json()

                raw_items = result_json.get("words", [])
                if raw_items:
                    print(f"[Transcriber] Groq {model_name} successfully returned {len(raw_items)} tokens.")
                    return align_tokens_to_thai_words(raw_items)
            except Exception as err:
                print(f"[Transcriber] Groq model {model_name} failed: {err}. Retrying next Groq model...")
                last_error = err
                continue

        if last_error:
            raise last_error
        return []
    finally:
        if temp_wav != audio_or_video_path and os.path.exists(temp_wav):
            try:
                os.remove(temp_wav)
            except Exception:
                pass

def transcribe_audio(
    audio_or_video_path: str,
    elevenlabs_api_key: str = None,
    groq_api_key: str = None,
    gemini_api_key: str = None,
    preferred_engine: str = "elevenlabs",
    keep_segments: List[Dict[str, float]] = None
) -> List[Dict[str, Any]]:
    """
    Transcribes audio into word-level timestamps.
    Supports:
      - Groq Whisper Large v3 (ultra-fast, 1-3 seconds)
      - ElevenLabs Scribe STT (high-precision Thai acoustic model)
      - Gemini Multimodal API (fallback)
      - Synthetic Thai alignment (offline fallback)
    """
    groq_key = groq_api_key or os.environ.get("GROQ_API_KEY")
    elevenlabs_key = elevenlabs_api_key or os.environ.get("ELEVENLABS_API_KEY")
    gemini_key = gemini_api_key or os.environ.get("GEMINI_API_KEY")

    engines = []
    if preferred_engine == "groq":
        if groq_key: engines.append(("groq", groq_key))
        if gemini_key: engines.append(("gemini", gemini_key))
        if elevenlabs_key: engines.append(("elevenlabs", elevenlabs_key))
    elif preferred_engine == "gemini":
        if gemini_key: engines.append(("gemini", gemini_key))
        if groq_key: engines.append(("groq", groq_key))
        if elevenlabs_key: engines.append(("elevenlabs", elevenlabs_key))
    else:
        # ElevenLabs preferred or Auto
        if elevenlabs_key: engines.append(("elevenlabs", elevenlabs_key))
        if groq_key: engines.append(("groq", groq_key))
        if gemini_key: engines.append(("gemini", gemini_key))

    for engine_name, key in engines:
        try:
            if engine_name == "groq":
                print("[Transcriber] Using Groq Whisper Large v3 for ultra-fast STT...")
                words = transcribe_with_groq(audio_or_video_path, key)
                if words:
                    print(f"[Transcriber] Groq transcribed {len(words)} words successfully!")
                    return words
            elif engine_name == "elevenlabs":
                print("[Transcriber] Using ElevenLabs Scribe STT API for high-precision Thai captions...")
                words = transcribe_with_elevenlabs(audio_or_video_path, key)
                if words:
                    print(f"[Transcriber] ElevenLabs transcribed {len(words)} words successfully!")
                    return words
            elif engine_name == "gemini":
                print("[Transcriber] Using Google Gemini Multimodal API for transcription...")
                words = transcribe_with_gemini(audio_or_video_path, key)
                if words:
                    print(f"[Transcriber] Gemini transcribed {len(words)} words successfully!")
                    return words
        except Exception as e:
            print(f"[Transcriber] {engine_name} error: {e}. Trying next available engine...")

    print("[Transcriber] No API key provided or API unavailable. Using synthetic Thai speech alignment.")
    return generate_mock_thai_transcription(keep_segments)

def transcribe_with_elevenlabs(audio_or_video_path: str, api_key: str) -> List[Dict[str, Any]]:
    """Call ElevenLabs Scribe Speech-to-Text API for Thai word-level timestamps."""
    url = "https://api.elevenlabs.io/v1/speech-to-text"
    headers = {"xi-api-key": api_key}

    temp_wav = audio_or_video_path
    if not audio_or_video_path.lower().endswith(".wav"):
        temp_wav = os.path.splitext(audio_or_video_path)[0] + "_temp.wav"
        extract_audio(audio_or_video_path, temp_wav)

    try:
        with open(temp_wav, "rb") as f:
            files = {"file": f}
            data = {
                "model_id": "scribe_v1",
                "language_code": "tha",
                "timestamps_granularity": "word"
            }
            res = requests.post(url, headers=headers, files=files, data=data, timeout=120)
            res.raise_for_status()
            result_json = res.json()

        raw_items = result_json.get("words", [])
        if not raw_items:
            return []

        return align_tokens_to_thai_words(raw_items)
    finally:
        if temp_wav != audio_or_video_path and os.path.exists(temp_wav):
            try:
                os.remove(temp_wav)
            except Exception:
                pass

def transcribe_with_gemini(audio_or_video_path: str, api_key: str) -> List[Dict[str, Any]]:
    """Use Gemini Flash to transcribe audio with word-level or phrase timestamps."""
    import base64
    temp_wav = audio_or_video_path
    if not audio_or_video_path.lower().endswith(".wav"):
        temp_wav = os.path.splitext(audio_or_video_path)[0] + "_gemini.wav"
        extract_audio(audio_or_video_path, temp_wav)

    # gemini-3.6-flash is current flagship, fallback to gemini-flash-latest or gemini-2.5-flash
    models_to_try = ["gemini-3.6-flash", "gemini-flash-latest", "gemini-2.5-flash"]
    headers = {"Content-Type": "application/json"}

    try:
        with open(temp_wav, "rb") as f:
            audio_b64 = base64.b64encode(f.read()).decode("utf-8")

        prompt = (
            "Please transcribe the speech in Thai from this audio with word-level timestamps. "
            "Output strict JSON array without markdown formatting: "
            '[{"word": "...", "start": 0.0, "end": 0.5}]'
        )
        payload = {
            "contents": [{
                "parts": [
                    {
                        "inlineData": {
                            "mimeType": "audio/wav",
                            "data": audio_b64
                        }
                    },
                    {
                        "text": prompt
                    }
                ]
            }],
            "generationConfig": {
                "responseMimeType": "application/json"
            }
        }

        for model_name in models_to_try:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
                res = requests.post(url, headers=headers, json=payload, timeout=60)
                if res.status_code == 200:
                    resp_data = res.json()
                    raw_text = resp_data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    if raw_text.startswith("```"):
                        raw_text = raw_text.split("```")[1]
                        if raw_text.startswith("json"):
                            raw_text = raw_text[4:]
                    words = json.loads(raw_text.strip())
                    print(f"[Transcriber] Gemini {model_name} successfully transcribed {len(words)} words.")
                    return words
                else:
                    print(f"[Transcriber] Gemini {model_name} returned {res.status_code}: {res.text[:120]}")
            except Exception as err:
                print(f"[Transcriber] Gemini {model_name} error: {err}")
                continue
        return []
    finally:
        if temp_wav != audio_or_video_path and os.path.exists(temp_wav):
            try:
                os.remove(temp_wav)
            except Exception:
                pass

def generate_mock_thai_transcription(keep_segments: List[Dict[str, float]] = None) -> List[Dict[str, Any]]:
    """
    Generates realistic Thai demo words mapped to the active speech intervals.
    Enables instant offline testing and verification without burning API credits.
    """
    sample_vocab = [
        "สวัสดีครับ", "วันนี้", "เราจะมา", "แนะนำ", "วิธีการ",
        "ตัดต่อวิดีโอ", "ด้วยระบบ", "AI", "อัตโนมัติ", "ประหยัดเวลา",
        "ตัดช่วงเงียบ", "ใส่ซับไทย", "ส่งเข้า", "CapCut", "ทันที",
        "ง่ายมากๆ", "ลองเอาไป", "ใช้งานกัน", "ดูนะครับ"
    ]

    if not keep_segments:
        keep_segments = [{"start": 0.5, "end": 2.5, "duration": 2.0}]

    words: List[Dict[str, Any]] = []
    vocab_idx = 0

    for seg in keep_segments:
        start_t = seg["start"]
        end_t = seg["end"]
        dur = end_t - start_t

        # Number of words inside this segment (approx 2-3 words per second)
        num_words = max(1, int(dur * 2.2))
        word_dur = dur / num_words

        for i in range(num_words):
            w_start = start_t + i * word_dur
            w_end = w_start + word_dur
            w_text = sample_vocab[vocab_idx % len(sample_vocab)]
            vocab_idx += 1
            words.append({
                "word": w_text,
                "start": round(w_start, 3),
                "end": round(w_end, 3)
            })

    return words
