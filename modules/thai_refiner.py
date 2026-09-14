import os
import json
import requests
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

def refine_thai_captions_with_llm(
    subtitles: List[Dict[str, Any]],
    gemini_api_key: str = None
) -> List[Dict[str, Any]]:
    """
    Pass 2 Thai Refinement with Google Gemini LLM:
    Polishes Thai subtitles to ensure natural, grammatically correct Thai:
    1. Continuous Thai word joining (คำในประโยคเขียนติดกัน ไม่เว้นวรรคมั่วซั่ว)
    2. Proper contextual spacing (เว้นวรรคเฉพาะจุดที่ถูกต้อง เช่น จบประโยค, คั่นชื่อแบรนด์, คั่นตัวเลข/ภาษาอังกฤษ)
    3. Spelling and transcription correction (แก้คำสะกดผิด/คำผิดเพี้ยนจากการถอดเสียง)
    4. Preserves exact millisecond timestamps and word-level karaoke sync data.
    """
    key = gemini_api_key or os.environ.get("GEMINI_API_KEY")
    if not key or not subtitles:
        return subtitles

    # Determine whether input is chunked subtitles or raw word tokens
    is_chunked = isinstance(subtitles[0], dict) and "text" in subtitles[0]

    models = ["gemini-3.8-flash", "gemini-3.6-flash"]
    headers = {"Content-Type": "application/json"}

    if is_chunked:
        # Polish existing chunk texts while preserving all timing metadata
        chunk_payload = [{"id": idx, "text": s["text"]} for idx, s in enumerate(subtitles)]

        prompt = (
            "คุณคือผู้เชี่ยวชาญภาษาไทยและการทำ Subtitle วิดีโอสั้น (TikTok/Reels/Shorts) ระดับมืออาชีพ\n\n"
            "หน้าที่ของคุณ:\n"
            "1. ตรวจทานและจัดเรียงข้อความซับไตเติลภาษาไทยแต่ละข้อความให้เขียนติดกันเป็นคำ/ประโยคตามหลักภาษาไทย (เช่น 'มาสด้าสินธานี', 'สวัสดีค่ะ', 'โปรโมชัน')\n"
            "2. เว้นวรรคเฉพาะจุดที่ถูกต้องและจำเป็นเท่านั้น เช่น คั่นชื่อแบรนด์กับคำทักทาย ('มาสด้าสินธานี สวัสดีค่ะ'), คั่นภาษาอังกฤษหรือตัวเลข ('Mazda 2', '0% 60 เดือน')\n"
            "3. แก้ไขคำสะกดผิด หรือคำที่ถอดเสียงเพี้ยน ให้ถูกต้องตามพจนานุกรมและบริบทการสนทนา\n"
            "4. ห้ามเปลี่ยนความหมายเดิม ห้ามตัดทอนหรือแต่งเติมเนื้อหาใหม่โดยไม่จำเป็น\n"
            "5. ห้ามรวมหรือแยกก้อน ต้องตอบกลับจำนวนข้อความเท่าเดิมตามลำดับ id\n\n"
            "ตอบกลับเป็น JSON Array แท้ๆ เท่านั้น (ห้ามใส่คำอธิบายเพิ่มเติม):\n"
            '[{"id": 0, "text": "ข้อความที่ขัดเกลาแล้ว"}, ...]\n\n'
            f"รายการข้อความ:\n{json.dumps(chunk_payload, ensure_ascii=False)}"
        )

        for model_name in models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key}"
            body = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.1,
                    "responseMimeType": "application/json"
                }
            }
            try:
                res = requests.post(url, headers=headers, json=body, timeout=25)
                if res.status_code == 200:
                    resp_data = res.json()
                    raw_text = resp_data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    refined_items = json.loads(raw_text)

                    # Map refined text back onto existing subtitle chunks
                    refined_dict = {item["id"]: item["text"] for item in refined_items if "id" in item and "text" in item}
                    output_chunks = []
                    for idx, s in enumerate(subtitles):
                        chunk_copy = dict(s)
                        if idx in refined_dict and refined_dict[idx].strip():
                            chunk_copy["text"] = refined_dict[idx].strip()
                            chunk_copy["raw_text"] = refined_dict[idx].strip()
                        output_chunks.append(chunk_copy)

                    print(f"[ThaiRefiner] ✅ Successfully refined {len(output_chunks)} Thai subtitle chunks with {model_name}!")
                    return output_chunks
                else:
                    print(f"[ThaiRefiner] {model_name} returned status {res.status_code}, trying fallback...")
            except Exception as e:
                print(f"[ThaiRefiner Warning] {model_name} error: {e}, trying fallback...")

        print("[ThaiRefiner Warning] All LLM models failed. Using original subtitle chunks.")
        return subtitles

    else:
        # Input is raw word tokens: group and refine into punchy chunks
        prompt = (
            "คุณคือผู้เชี่ยวชาญด้านการทำ Subtitle วิดีโอสั้น (TikTok/Reels/Shorts) ภาษาไทยระดับมืออาชีพ\n\n"
            "หน้าที่ของคุณ:\n"
            "1. รวมคำและแก้ไขคำสะกดผิดให้เป็นภาษาไทยที่ถูกต้อง คำในประโยคต้องเขียนติดกันตามหลักภาษาไทย\n"
            "2. เว้นวรรคเฉพาะจุดที่ถูกต้อง เช่น คั่นชื่อแบรนด์, คั่นภาษาอังกฤษหรือตัวเลข ('Mazda 2', '0% 60 เดือน')\n"
            "3. รวมคำเข้าเป็นก้อนซับไตเติลสั้นๆ ท่อนละ 15-25 ตัวอักษร อ่านง่ายกระชับตา ไม่เกิน 1 บรรทัด\n"
            "4. สำหรับแต่ละก้อน ให้ระบุ start และ end ให้ตรงตามต้นฉบับ\n"
            "5. ตอบกลับเป็น JSON Array แท้ๆ เท่านั้น:\n"
            '[{"text": "มาสด้าสินธานี สวัสดีค่ะ", "start": 0.5, "end": 1.4}, ...]\n\n'
            f"ข้อมูลคำดิบ:\n{json.dumps(subtitles, ensure_ascii=False)}"
        )

        for model_name in models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key}"
            body = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.1,
                    "responseMimeType": "application/json"
                }
            }
            try:
                res = requests.post(url, headers=headers, json=body, timeout=30)
                if res.status_code == 200:
                    resp_data = res.json()
                    raw_text = resp_data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    refined_chunks = json.loads(raw_text)
                    print(f"[ThaiRefiner] ✅ Successfully refined {len(refined_chunks)} Thai chunks from raw words with {model_name}!")
                    return refined_chunks
            except Exception as e:
                print(f"[ThaiRefiner Warning] {model_name} error: {e}")

        return []
