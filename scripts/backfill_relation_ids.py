from pathlib import Path
import json
import re
import sqlite3

DB = Path(__file__).resolve().parents[1] / 'data' / 'family.db'

def norm(v):
    return str(v or '').strip()

def split_names(v):
    raw = norm(v)
    if not raw:
        return []
    return [s.strip() for s in re.split(r'[、,，/\s]+', raw) if s.strip()]

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
rows = conn.execute('select id,name,father_name,mother_name,spouse_name,father_id,mother_id,spouse_ids from member order by id').fetchall()
by_name = {}
for r in rows:
    by_name.setdefault(norm(r['name']), []).append(r)

updated = 0
ambiguous = []
for r in rows:
    father_id = r['father_id']
    mother_id = r['mother_id']
    spouse_ids = r['spouse_ids']

    if not father_id and norm(r['father_name']):
        cands = by_name.get(norm(r['father_name']), [])
        if len(cands) == 1:
            father_id = cands[0]['id']
        elif len(cands) > 1:
            ambiguous.append({'member_id': r['id'], 'field': 'father_name', 'value': r['father_name'], 'candidate_ids': [x['id'] for x in cands]})

    if not mother_id and norm(r['mother_name']):
        cands = by_name.get(norm(r['mother_name']), [])
        if len(cands) == 1:
            mother_id = cands[0]['id']
        elif len(cands) > 1:
            ambiguous.append({'member_id': r['id'], 'field': 'mother_name', 'value': r['mother_name'], 'candidate_ids': [x['id'] for x in cands]})

    spouse_list = []
    if spouse_ids:
        try:
            spouse_list = json.loads(spouse_ids)
        except Exception:
            spouse_list = []
    if not spouse_list and norm(r['spouse_name']):
        for name in split_names(r['spouse_name']):
            cands = by_name.get(name, [])
            if len(cands) == 1:
                sid = cands[0]['id']
                if sid != r['id'] and sid not in spouse_list:
                    spouse_list.append(sid)
            elif len(cands) > 1:
                ambiguous.append({'member_id': r['id'], 'field': 'spouse_name', 'value': name, 'candidate_ids': [x['id'] for x in cands]})

    conn.execute('update member set father_id=?, mother_id=?, spouse_ids=? where id=?', (father_id, mother_id, json.dumps(spouse_list, ensure_ascii=False) if spouse_list else None, r['id']))
    updated += 1

conn.commit()
print(json.dumps({'db': str(DB), 'updated_rows': updated, 'ambiguous_count': len(ambiguous), 'ambiguous_samples': ambiguous[:20]}, ensure_ascii=False))
