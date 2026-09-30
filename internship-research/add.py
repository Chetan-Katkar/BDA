import json, os, sys
DB='companies.json'
def load():
    return json.load(open(DB)) if os.path.exists(DB) else []
def save(d):
    json.dump(d, open(DB,'w'), indent=1, ensure_ascii=False)
def add(recs):
    d=load(); names={r['company'].lower() for r in d}
    for r in recs:
        if r['company'].lower() in names:
            print('DUP skipped:', r['company']); continue
        d.append(r); names.add(r['company'].lower())
    save(d); print('total:', len(d))
