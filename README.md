# 🎬 Auto Edit Kit

ชุดเครื่องมือตัดต่อวิดีโออัตโนมัติด้วย AI ทำงานคล้ายกับ **ii23 Edit Kit**:
1. **ตัดเดดแอร์/ช่วงเงียบ (Silence Removal)** อัตโนมัติด้วยความแม่นยำสูง
2. **ถอดเสียงและทำซับไตเติลภาษาไทย (Thai Captions)** คำต่อคำ จัดกลุ่ม 2-4 คำสไตล์ Reels / TikTok
3. **ฉีดโปรเจกต์เข้า CapCut Desktop (Windows)** โดยตรง สร้าง Video Track และ Subtitle Track ให้เปิดตรวจงานได้ทันที
4. **เรนเดอร์เป็นไฟล์ MP4 ได้ทันที** ไม่ต้องผ่านโปรแกรมตัดต่อหากต้องการงานด่วน

---

## โครงสร้างโปรเจกต์

```
auto-edit-kit/
├── app.py                   # หน้าต่าง Web UI (Streamlit) สวยงาม ใช้งานง่าย
├── run.py                   # สคริปต์ Command Line (CLI) สั่งรันคำสั่งเดียวจบ
├── SKILL.md                 # Agent Skill สำหรับสั่งงานผ่าน Antigravity หรือ AI Agent
├── .env.example             # ตัวอย่างการตั้งค่า API Key
├── modules/
│   ├── ffmpeg_utils.py      # เชื่อมต่อ FFmpeg (ดึงข้อมูลคลิป, แปลงไฟล์เสียง)
│   ├── silence_detector.py  # ตรวจจับช่วงเดดแอร์และคำนวณจุดตัด
│   ├── transcriber.py       # ถอดเสียง (รองรับ ElevenLabs / Gemini / Mock)
│   ├── thai_formatter.py    # จัดก้อนคำซับไทยและคำนวณ Timestamp บนไทม์ไลน์
│   └── capcut_generator.py  # สร้างไฟล์ draft_content.json เข้า CapCut Desktop
└── tests/
    ├── generate_sample_video.py  # สคริปต์สร้างวิดีโอทดสอบ
    └── sample_video.mp4          # วิดีโอทดสอบตัวอย่าง
```

---

## วิธีใช้งาน

### 1. ใช้งานผ่าน Web UI (แนะนำสำหรับผู้ใช้ทั่วไป)
เปิด Terminal ในโฟลเดอร์นี้แล้วสั่ง:
```bash
streamlit run app.py
```
เปิดเบราว์เซอร์ไปที่ `http://localhost:8501` คุณจะสามารถ:
- อัปโหลดวิดีโอ หรือทดลองใช้วิดีโอตัวอย่าง
- ปรับแถบเลื่อนความไวในการตัดช่วงเงียบ
- ดูพรีวิวและแก้ไขข้อความซับไตเติลภาษาไทย
- กดปุ่ม **"🚀 ฉีดเข้า CapCut Desktop ทันที"** เพื่อเปิดงานต่อใน CapCut

---

### 2. ใช้งานผ่าน Command Line (CLI)
```bash
# คำสั่งพื้นฐาน
python run.py -i "path/to/video.mp4" --name "MyFirstClip"

# สั่งให้เรนเดอร์เป็นไฟล์ MP4 ออกมาด้วย
python run.py -i "path/to/video.mp4" --export-mp4

# ปรับความไวในการตัดเสียงเงียบ (เช่น เงียบกว่า -35dB เกิน 0.3 วินาทีให้ตัด)
python run.py -i "path/to/video.mp4" --silence-db -35.0 --min-silence 0.3
```

---

### 3. ผลลัพธ์ใน CapCut Desktop
เมื่อรันเสร็จเรียบร้อย:
1. เปิดโปรแกรม **CapCut Desktop** บนคอมพิวเตอร์ของคุณ
2. ที่หน้าหลักของ CapCut จะพบโปรเจกต์ใหม่ปรากฏขึ้นทันที
3. ดับเบิลคลิกเข้าไป จะพบว่า:
   - **Video Track:** คลิปถูกตัดช่วงเงียบทิ้งไปทั้งหมด
   - **Text Track:** ซับไตเติลภาษาไทยถูกวางตามเวลาพูดอย่างแม่นยำ พร้อมปรับฟอนต์และสีได้ทันที
