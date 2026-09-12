import os
import json
import requests
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

def refine_thai_captions_with_llm(
    raw_words: List[Dict[str, Any]],
    gemini_api_key: str = None
) -> List[Dict[str, Any]]:
    """
    Pass 2 Thai Refinement:
    Uses Gemini LLM to:
    1. Fix misspelled words and unnatural syllable splits (e.g. 'สวัส' + 'ดี' -> 'สวัสดี')
    2. Group words into natural, punchy subtitle chunks (2-4 words per line) suited for TikTok/Reels
    3. Accurately assign start and end timestamps to each chunk
    """
    key = gemini_api_key or os.environ.get("GEMINI_API_KEY")
    if not key or not raw_words:
        # If no key, return as-is
        return []

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}"
    headers = {"Content-Type": "application/json"}

    prompt = (
        "คุณคือผู้เชี่ยวชาญด้านการทำ Subtitle วิดีโอสั้น (TikTok/Reels/Shorts) ภาษาไทยระดับมืออาชีพ\n\n"
        "ด้านล่างนี้คือรายการคำและ timestamps จากระบบถอดเสียง (STT) ซึ่งอาจมีปัญหา:\n"
        "- คำถูกหั่นครึ่งพยางค์ (เช่น 'สวัส' กับ 'ดีครับ')\n"
        "- การตัดวรรคคำไม่เป็นธรรมชาติ ขาดช่วงความหมาย\n"
        "- คำพ้องเสียงสะกดผิด\n\n"
        "หน้าที่ของคุณ:\n"
        "1. รวมพยางค์ที่ขาดและแก้ไขคำสะกดผิดให้เป็นภาษาไทยที่ถูกต้องและเป็นธรรมชาติ\n"
        "2. รวมคำเข้าเป็นก้อนซับไตเติลสั้นๆ ก้อนละ 2-4 คำ (ไม่เกิน 20-25 ตัวอักษรต่อก้อน) อ่านง่ายกระชับตา\n"
        "3. สำหรับแต่ละก้อน ให้ระบุ start (เวลาเริ่มของคำแรกในก้อน) และ end (เวลาจบของคำสุดท้ายในก้อน) ให้ตรงตามต้นฉบับ\n"
        "4. ห้ามตัดทอนเนื้อหาสำคัญ ห้ามแต่งเนื้อความใหม่\n"
        "5. ตอบกลับเป็น JSON Array แท้ๆ เท่านั้น โดยไม่มี markdown formatting หรือคำอธิบายใดๆ:\n"
        '[{"text": "สวัสดีครับทุกคน", "start": 0.5, "end": 1.4}, ...]\n\n'
        f"ข้อมูลคำดิบ:\n{json.dumps(raw_words, ensure_ascii=False)}"
    )

    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json"
        }
    }

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=45)
        res.raise_for_status()
        resp_data = res.json()
        raw_text = resp_data["candidates"][0]["content"]["parts"][0]["text"].strip()
        
        # Clean up any residual markdown wrappers
        if raw_text.startswith("```"):
            lines = raw_text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            raw_text = "\n".join(lines).strip()

        refined_chunks = json.loads(raw_text)
        print(f"[ThaiRefiner] ✅ Successfully refined {len(refined_chunks)} Thai subtitle chunks with Gemini LLM!")
        return refined_chunks
    except Exception as e:
        print(f"[ThaiRefiner Warning] LLM refinement error: {e}. Using rule-based fallback.")
        return []
