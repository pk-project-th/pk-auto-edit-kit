import re
from typing import List, Dict, Any, Optional

try:
    from pythainlp.tokenize import word_tokenize
    from pythainlp.corpus.common import thai_words
    THAI_WORDS_SET = set(thai_words())
    HAS_PYTHAINLP = True
except ImportError:
    HAS_PYTHAINLP = False
    THAI_WORDS_SET = set()

def map_timestamp_to_edited_timeline(
    raw_time: float,
    keep_segments: List[Dict[str, float]]
) -> float:
    """
    Given a timestamp in the raw video, maps it to the corresponding timestamp
    on the edited timeline (after silences are trimmed).
    """
    timeline_accum = 0.0
    for seg in keep_segments:
        s_start = seg["start"]
        s_end = seg["end"]
        s_dur = seg["duration"]

        if raw_time < s_start:
            return timeline_accum
        elif s_start <= raw_time <= s_end:
            return timeline_accum + (raw_time - s_start)
        else:
            timeline_accum += s_dur

    return timeline_accum

def clean_thai_word(word: str) -> str:
    """Cleans up internal odd spacing inside a Thai word token."""
    if " " in word and len(word.replace(" ", "")) > 0:
        return word.replace(" ", "")
    return word.strip()

def wrap_text_two_lines(
    text: str,
    max_words_per_line: int = 5,
    max_chars_per_line: int = 25
) -> str:
    """
    Splits text across two lines cleanly at natural Thai word boundaries
    if word count exceeds max_words_per_line or character length exceeds max_chars_per_line.
    """
    if not HAS_PYTHAINLP:
        return text

    words = [w for w in word_tokenize(text, engine="newmm") if w.strip()]
    if len(words) <= max_words_per_line and len(text) <= max_chars_per_line:
        return text

    # Balance lines nicely around midpoint or max_words_per_line
    total_words = len(words)
    mid_idx = min(max_words_per_line, max(1, (total_words + 1) // 2))
    
    line1 = "".join(words[:mid_idx]).strip()
    line2 = "".join(words[mid_idx:]).strip()

    if not line2:
        return line1

    return f"{line1}\n{line2}"

def assemble_thai_tokens(tokens: List[Dict[str, Any]]) -> str:
    """
    Joins Thai word tokens with natural spacing.
    Thai words within the same sentence or clause are joined continuously (ติดกัน),
    while spaces appear naturally at clause boundaries, after polite particles,
    around English/numbers, and during audible speech pauses.
    """
    if not tokens:
        return ""

    sentence_endings = ("ค่ะ", "ครับ", "นะคะ", "นะครับ", "จ้า", "เด้อ", "ฮะ", "เลยค่ะ", "เลยครับ")
    clause_starters = ("หรือ", "หาก", "ถ้า", "และ", "แต่", "โดย", "ซึ่ง", "เพื่อ", "เพราะ", "เช่น", "รวมถึง")
    ending_particles = ("ค่ะ", "ครับ", "นะคะ", "นะครับ", "จ้า", "เด้อ", "นะ", "ละ", "ล่ะ")
    greetings = ("สวัสดี", "กราบสวัสดี", "ฮัลโหล", "หวัดดี")

    res = ""
    for idx, t in enumerate(tokens):
        w = t["word"].strip()
        if not w:
            continue

        if idx == 0:
            res += w
            continue

        prev_tok = tokens[idx - 1]
        prev_w = prev_tok["word"].strip()
        is_curr_ascii = any(ord(c) < 128 for c in w)
        is_prev_ascii = any(ord(c) < 128 for c in prev_w)
        gap = float(t.get("start", 0.0)) - float(prev_tok.get("end", 0.0))

        need_space = False
        # 1. English or number boundary (e.g. รถยนต์ Mazda 2 นะคะ)
        if is_curr_ascii or is_prev_ascii:
            need_space = True
        # 2. Never space immediately before an ending particle (e.g. สวัสดีค่ะ, รุ่นนี้นะคะ)
        elif w in ending_particles:
            need_space = False
        # 3. Space before greeting after brand/place name (e.g. มาสด้าสินธานี สวัสดีค่ะ)
        elif w in greetings:
            need_space = True
        # 4. Space after sentence ending particle (e.g. สวัสดีค่ะ วันนี้ / รุ่นนี้นะคะ ราคาเต็ม)
        elif any(prev_w.endswith(end) for end in sentence_endings):
            need_space = True
        # 5. Space before clause starter / conjunction (e.g. หรือเลือกรับ...)
        elif any(w.startswith(starter) for starter in clause_starters):
            need_space = True
        # 6. Audible pause gap (> 0.22s) between speech phrases
        elif gap > 0.22:
            need_space = True

        if need_space:
            res += " " + w
        else:
            res += w

    return res.strip()

def chunk_word_timestamps(
    words: List[Dict[str, Any]],
    keep_segments: List[Dict[str, float]] = None,
    caption_mode: str = "sentence",       # 'sentence' (ประโยคสมบูรณ์) or 'short' (ก้อนคำสั้น)
    lines_mode: str = "1 แถว",             # '1 แถว' (ค่าเริ่มต้นแนะนำ) or '2 แถว'
    max_words_per_line: int = 5,           # คำสูงสุดต่อแถว
    max_chars_per_line: int = 24,          # ป้องกันข้อความยาวเกินขนาดขอบคลิป
    max_duration_per_chunk: float = 2.8,
    pause_threshold: float = 0.30
) -> List[Dict[str, Any]]:
    """
    Groups word tokens into natural, grammatically complete Thai sentences/clauses.
    Defaults to 1 clean line with support for 2-line layout and custom word/character limits.
    """
    if not words:
        return []

    # Step 1: Pre-clean word tokens
    cleaned_words = []
    for w in words:
        raw_w = clean_thai_word(w.get("word", ""))
        if raw_w:
            cleaned_words.append({
                "word": raw_w,
                "start": float(w.get("start", 0.0)),
                "end": float(w.get("end", 0.0)),
                "leading_space": bool(w.get("leading_space", False))
            })

    if not cleaned_words:
        return []

    # Adjust limits based on line mode
    if lines_mode == "2 แถว":
        max_chars = max_chars_per_line * 2
        max_dur = max_duration_per_chunk * 1.4
    else:
        max_chars = max_chars_per_line
        max_dur = max_duration_per_chunk

    sentence_endings = (
        "ค่ะ", "ครับ", "นะคะ", "นะครับ", "จ้า", "เด้อ", "เลยค่ะ", "เลยครับ", "เองค่ะ", "เองครับ",
        "ไม่ได้", "ไม่ได้เลย", "ได้เลย", "แล้ว", "กัน", "ดีกว่า"
    )
    clause_openings = (
        "เชิญชวน", "ขอเชิญ", "ชวน", "แนะนำ", "สนใจ", "ติดต่อ", "ทัก", "ทักแชท", "โทร", "รีบ", "อย่าลืม",
        "มาดู", "มาชม", "มาพบ", "มารับ", "แวะมา", "มาที่", "มาสด้า", "โชว์รูม",
        "ใครที่", "สำหรับ", "ท่านใด", "ถ้าหาก", "หาก", "ถ้า", "เมื่อ",
        "หรือ", "และ", "แต่", "โดย", "ซึ่ง", "เพื่อ", "เพราะ", "เกี่ยวกับ",
        "ราคาจะอยู่ที่", "ราคา", "อยู่ที่", "ผ่อนละ", "ผ่อนเริ่มต้น", "ผ่อน", "ดาวน์เริ่มต้น", "ดาวน์",
        "ดอกเบี้ย", "ส่วนลด", "โปรโมชัน", "วันนี้จะมา", "วันนี้"
    )
    ending_particles = ("ค่ะ", "ครับ", "นะคะ", "นะครับ", "จ้า", "เด้อ", "นะ", "ละ", "ล่ะ", "เอง", "เองค่ะ", "เองครับ")
    number_units = ("สิบ", "ร้อย", "พัน", "หมื่น", "แสน", "ล้าน", "บาท", "บาทค่ะ", "เปอร์เซ็นต์", "%", "เดือน", "วัน", "ปี", "งวด")
    dangling_words = ("เกี่ยวกับ", "อยู่ที่", "ราคาจะอยู่ที่", "หรือเลือกรับ", "ดาวน์เริ่มต้น", "ผ่อนเริ่มต้น", "เลือกรับ", "ดอกเบี้ย", "ใครที่")
    anti_split_before = ("ไม่ได้", "ไม่เป็น", "ไม่อยู่", "ไม่มี", "นะคะ", "นะครับ", "ครับ", "ค่ะ", "เปอร์เซ็นต์", "%", "เดือน", "บาท", "บาทค่ะ", "งวด", "วัน", "ปี", "เอง", "เองค่ะ")

    chunks: List[Dict[str, Any]] = []
    current_tokens: List[Dict[str, Any]] = []

    def flush_chunk():
        nonlocal current_tokens
        if not current_tokens:
            return

        assembled = assemble_thai_tokens(current_tokens)

        # Apply 2-line wrap if requested
        if lines_mode == "2 แถว":
            display_text = wrap_text_two_lines(
                assembled,
                max_words_per_line=max_words_per_line,
                max_chars_per_line=max_chars_per_line
            )
        else:
            display_text = assembled

        s_start = current_tokens[0]["start"]
        s_end = current_tokens[-1]["end"]
        dur = max(0.3, s_end - s_start)

        t_start = s_start
        t_end = s_end
        if keep_segments:
            t_start = map_timestamp_to_edited_timeline(s_start, keep_segments)
            t_end = map_timestamp_to_edited_timeline(s_end, keep_segments)
            if t_end <= t_start:
                t_end = t_start + dur

        # Map each individual word token to timeline as well for karaoke sync
        for tok in current_tokens:
            w_s = tok["start"]
            w_e = tok["end"]
            if keep_segments:
                tok["timeline_start"] = round(map_timestamp_to_edited_timeline(w_s, keep_segments), 3)
                tok["timeline_end"] = round(map_timestamp_to_edited_timeline(w_e, keep_segments), 3)
            else:
                tok["timeline_start"] = round(w_s, 3)
                tok["timeline_end"] = round(w_e, 3)

        chunks.append({
            "text": display_text,
            "raw_text": assembled,
            "source_start": round(s_start, 3),
            "source_end": round(s_end, 3),
            "timeline_start": round(t_start, 3),
            "timeline_end": round(t_end, 3),
            "duration": round(t_end - t_start, 3),
            "words": list(current_tokens)
        })
        current_tokens = []

    for i, tok in enumerate(cleaned_words):
        current_tokens.append(tok)
        curr_text = assemble_thai_tokens(current_tokens)
        curr_dur = current_tokens[-1]["end"] - current_tokens[0]["start"]

        remaining = cleaned_words[i+1:]

        # Anti-orphan check: Keep ending particles, number units, and closing words intact
        next_is_ending_orphan = False
        if len(remaining) == 1:
            next_is_ending_orphan = True
        elif remaining:
            next_w = remaining[0]["word"].strip()
            if any(next_w.endswith(e) for e in sentence_endings) or next_w in ending_particles:
                next_is_ending_orphan = True
            elif next_w in number_units and len(current_tokens) >= 1:
                next_is_ending_orphan = True
            elif tok["word"].strip() in dangling_words:
                next_is_ending_orphan = True

        should_split = False

        if not next_is_ending_orphan and remaining:
            next_w = remaining[0]["word"].strip()
            next_is_anti_split = any(next_w.startswith(asp) for asp in anti_split_before)

            if not next_is_anti_split:
                # 1. Natural ending particle or clause-ending verb/negation
                if any(tok["word"].endswith(e) for e in sentence_endings):
                    if curr_dur >= 0.5 or len(curr_text) >= 10:
                        should_split = True

                # 2. Next word is a clause opener or action verb (split before it starts)
                elif any(next_w.startswith(op) for op in clause_openings):
                    if curr_dur >= 0.6 or len(curr_text) >= 10:
                        should_split = True

                # 3. Audible gap in speech
                elif (remaining[0]["start"] - tok["end"] > pause_threshold) and (curr_dur >= 0.5):
                    should_split = True

                # 4. Limit reached or lookahead overflow
                elif curr_dur >= max_dur or len(curr_text) >= max_chars:
                    should_split = True
                elif len(curr_text) >= 14 and (len(curr_text) + len(next_w) > max_chars):
                    should_split = True

        if should_split:
            flush_chunk()

    flush_chunk()
    return chunks

def realign_subtitle_words(
    text: str,
    current_words: Optional[List[Dict[str, Any]]] = None,
    master_words: Optional[List[Dict[str, Any]]] = None,
    s_start: float = 0.0,
    s_end: float = 0.0,
    keep_segments: Optional[List[Dict[str, float]]] = None
) -> List[Dict[str, Any]]:
    """
    Dynamically re-aligns word tokens and timestamps when subtitle text is edited or words are moved.

    Guarantees:
    1. Words moved from other chunks preserve their exact millisecond speech timestamps.
    2. Deleted words are cleanly removed from the word list.
    3. Newly typed or edited words receive smooth interpolated timestamps.
    4. Monotonically increasing timestamps prevent highlight jumping backwards.
    5. Tokens exactly match the characters in `text` so karaoke focus never drifts.
    6. Properly maps each token to both source time and edited timeline.
    """
    if not text or not text.strip():
        return []

    clean_text = text.strip()

    # 1. Gather candidate words, prioritized by temporal proximity to [s_start, s_end]
    raw_candidates: List[Dict[str, Any]] = []
    if current_words:
        for w in current_words:
            if w.get("word") and str(w["word"]).strip():
                raw_candidates.append(dict(w))

    if master_words:
        chunk_center = (s_start + s_end) / 2.0 if (s_start and s_end) else 0.0
        sorted_master = sorted(
            master_words,
            key=lambda w: abs(((float(w.get("start", 0.0)) + float(w.get("end", 0.0))) / 2.0) - chunk_center)
        )
        for w in sorted_master:
            if w.get("word") and str(w["word"]).strip():
                raw_candidates.append(dict(w))

    # Expand compound candidates into sub-tokens to support any token granularity
    candidates: List[Dict[str, Any]] = []
    for c in raw_candidates:
        w_str = str(c.get("word", "")).strip()
        if not w_str:
            continue
        candidates.append(c)
        if HAS_PYTHAINLP:
            try:
                sub_toks = word_tokenize(w_str, engine="newmm")
                if len(sub_toks) > 1:
                    c_start = float(c.get("start", 0.0))
                    c_end = float(c.get("end", c_start + 0.3))
                    c_dur = max(0.05, c_end - c_start)
                    total_len = len(w_str)
                    curr_offset = 0
                    for st in sub_toks:
                        st_len = len(st)
                        st_start = c_start + (curr_offset / total_len) * c_dur
                        st_end = c_start + ((curr_offset + st_len) / total_len) * c_dur
                        candidates.append({
                            "word": st,
                            "start": round(st_start, 3),
                            "end": round(st_end, 3),
                            "is_sub": True
                        })
                        curr_offset += st_len
            except Exception:
                pass

    # 2. Tokenize clean_text into words
    if HAS_PYTHAINLP:
        try:
            raw_tokens = word_tokenize(clean_text, engine="newmm")
        except Exception:
            raw_tokens = re.findall(r'\S+', clean_text)
    else:
        raw_tokens = re.findall(r'\S+', clean_text)

    # Clean tokens: keep track of leading spaces
    tokens: List[Dict[str, Any]] = []
    curr_char_idx = 0
    full_str = clean_text

    for t in raw_tokens:
        if not t.strip():
            curr_char_idx += len(t)
            continue

        has_leading_space = False
        pos_in_full = full_str.find(t, curr_char_idx)
        if pos_in_full > 0 and full_str[pos_in_full - 1].isspace():
            has_leading_space = True
        if pos_in_full != -1:
            curr_char_idx = pos_in_full + len(t)

        tokens.append({
            "word": t,
            "leading_space": has_leading_space,
            "char_len": len(t)
        })

    if not tokens:
        return []

    # 3. Match tokens to candidate words
    aligned_words: List[Dict[str, Any]] = []
    used_candidate_ids = set()

    for tok_idx, tok in enumerate(tokens):
        t_word = tok["word"]
        matched_cand = None
        best_dist = float("inf")

        chunk_center = (s_start + s_end) / 2.0 if (s_start and s_end) else 0.0

        for c_idx, cand in enumerate(candidates):
            if cand.get("word") == t_word and c_idx not in used_candidate_ids:
                cand_center = (float(cand.get("start", 0.0)) + float(cand.get("end", 0.0))) / 2.0
                dist = abs(cand_center - chunk_center)
                if dist < best_dist:
                    best_dist = dist
                    matched_cand = (c_idx, cand)

        if matched_cand:
            c_idx, cand = matched_cand
            used_candidate_ids.add(c_idx)
            w_start = float(cand.get("start", s_start))
            w_end = float(cand.get("end", w_start + 0.3))
            aligned_words.append({
                "word": t_word,
                "start": round(w_start, 3),
                "end": round(w_end, 3),
                "leading_space": tok["leading_space"],
                "matched": True
            })
        else:
            aligned_words.append({
                "word": t_word,
                "start": None,
                "end": None,
                "leading_space": tok["leading_space"],
                "matched": False
            })

    # 4. Interpolate timestamps for unmatched (newly typed or split) tokens
    total_tokens = len(aligned_words)
    default_start = s_start
    default_end = s_end if s_end > s_start else s_start + max(0.5, total_tokens * 0.3)

    for i, w in enumerate(aligned_words):
        if not w["matched"]:
            prev_end = default_start
            prev_idx = -1
            for p in range(i - 1, -1, -1):
                if aligned_words[p]["end"] is not None:
                    prev_end = aligned_words[p]["end"]
                    prev_idx = p
                    break

            next_start = default_end
            next_idx = total_tokens
            for n in range(i + 1, total_tokens):
                if aligned_words[n]["start"] is not None:
                    next_start = aligned_words[n]["start"]
                    next_idx = n
                    break

            if next_start <= prev_end:
                next_start = prev_end + 0.3 * (next_idx - prev_idx)

            gap_tokens = next_idx - prev_idx
            pos_in_gap = i - prev_idx
            span = next_start - prev_end

            w["start"] = round(prev_end + (pos_in_gap - 1) * (span / gap_tokens), 3)
            w["end"] = round(prev_end + pos_in_gap * (span / gap_tokens), 3)
            if w["end"] <= w["start"]:
                w["end"] = round(w["start"] + 0.2, 3)

    # 5. Ensure monotonically increasing timestamps
    for i in range(1, len(aligned_words)):
        if aligned_words[i]["start"] < aligned_words[i-1]["start"]:
            aligned_words[i]["start"] = round(aligned_words[i-1]["end"] + 0.02, 3)
            if aligned_words[i]["end"] <= aligned_words[i]["start"]:
                aligned_words[i]["end"] = round(aligned_words[i]["start"] + 0.25, 3)

    # 6. Map to timeline (with keep_segments)
    final_words = []
    for w in aligned_words:
        w_s = w["start"]
        w_e = w["end"]

        if keep_segments:
            tl_s = round(map_timestamp_to_edited_timeline(w_s, keep_segments), 3)
            tl_e = round(map_timestamp_to_edited_timeline(w_e, keep_segments), 3)
            if tl_e <= tl_s:
                tl_e = round(tl_s + max(0.1, w_e - w_s), 3)
        else:
            tl_s = round(w_s, 3)
            tl_e = round(w_e, 3)

        final_words.append({
            "word": w["word"],
            "start": w_s,
            "end": w_e,
            "leading_space": w.get("leading_space", False),
            "timeline_start": tl_s,
            "timeline_end": tl_e
        })

    return final_words

def get_word_character_ranges(full_text: str, words: List[Dict[str, Any]]) -> List[tuple]:
    """
    Sequentially maps each word token to its exact (start_char, end_char) range in full_text.
    Handles duplicate words and whitespace differences gracefully.
    """
    ranges = []
    cursor = 0
    for w in words:
        w_text = w.get("word", "").strip()
        if not w_text:
            ranges.append((cursor, cursor))
            continue
        idx = full_text.find(w_text, cursor)
        if idx != -1:
            start_pos = idx
            end_pos = idx + len(w_text)
            ranges.append((start_pos, end_pos))
            cursor = end_pos
        else:
            ranges.append((cursor, min(len(full_text), cursor + len(w_text))))
            cursor += len(w_text)
    return ranges

def format_vtt_timestamp(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"

def format_srt_timestamp(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    if ms >= 1000:
        s += 1
        ms = 0
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def generate_webvtt(
    subtitles: List[Dict[str, Any]],
    use_source_time: bool = True,
    line_position: int = 82,
    karaoke_mode: bool = False
) -> str:
    """
    Generates WebVTT format string with vertical position cues for synchronized video playback.
    When karaoke_mode=True, breaks each sentence into word-level cues highlighting the active word.
    """
    lines = ["WEBVTT", ""]
    cue_idx = 1

    for sub in subtitles:
        cue_text = sub.get("text", "").strip()
        if not cue_text:
            continue

        words = sub.get("words", [])
        if karaoke_mode and words:
            ranges = get_word_character_ranges(cue_text, words)
            for w_idx, w in enumerate(words):
                w_start = w.get("start" if use_source_time else "timeline_start", 0.0)
                w_end = w.get("end" if use_source_time else "timeline_end", w_start + 0.3)
                if w_end <= w_start:
                    w_end = w_start + 0.2

                start_str = format_vtt_timestamp(w_start)
                end_str = format_vtt_timestamp(w_end)

                r_start, r_end = ranges[w_idx]
                prefix = cue_text[:r_start]
                active = cue_text[r_start:r_end]
                suffix = cue_text[r_end:]

                highlighted = f"{prefix}<c.focus>{active}</c>{suffix}"

                lines.append(f"{cue_idx}")
                lines.append(f"{start_str} --> {end_str} line:{line_position}%")
                lines.append(highlighted)
                lines.append("")
                cue_idx += 1
        else:
            s_start = sub.get("source_start" if use_source_time else "timeline_start", 0.0)
            s_end = sub.get("source_end" if use_source_time else "timeline_end", s_start + 1.0)
            start_str = format_vtt_timestamp(s_start)
            end_str = format_vtt_timestamp(s_end)
            lines.append(f"{cue_idx}")
            lines.append(f"{start_str} --> {end_str} line:{line_position}%")
            lines.append(cue_text)
            lines.append("")
            cue_idx += 1

    return "\n".join(lines)

def generate_srt(subtitles: List[Dict[str, Any]], use_source_time: bool = False) -> str:
    """
    Generates standard SRT format string.
    """
    lines = []
    for i, sub in enumerate(subtitles):
        s_start = sub.get("source_start" if use_source_time else "timeline_start", 0.0)
        s_end = sub.get("source_end" if use_source_time else "timeline_end", s_start + 1.0)
        start_str = format_srt_timestamp(s_start)
        end_str = format_srt_timestamp(s_end)
        cue_text = sub.get("text", "").strip()
        if cue_text:
            lines.append(str(i+1))
            lines.append(f"{start_str} --> {end_str}")
            lines.append(cue_text)
            lines.append("")
    return "\n".join(lines)
