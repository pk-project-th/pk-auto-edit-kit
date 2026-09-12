import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

p = r"C:\Users\Marketing\AppData\Local\CapCut\User Data\Projects\com.lveditor.draft\สัมภาษลูกค้า\draft_content.json"
with open(p, 'r', encoding='utf-8') as f:
    d = json.load(f)

for i, t in enumerate(d.get('materials', {}).get('texts', [])):
    c = json.loads(t.get('content', '{}'))
    mat_id = t.get('id')
    clip = None
    for tr in d.get('tracks', []):
        for seg in tr.get('segments', []):
            if seg.get('material_id') == mat_id:
                clip = seg.get('clip')
                break
    print(f"=== Text {i}: {c.get('text')} ===")
    print("Content styles:", json.dumps(c.get('styles'), indent=2, ensure_ascii=False))
    print("Clip:", json.dumps(clip, indent=2))
