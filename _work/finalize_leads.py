import csv, re, collections

rows=list(csv.DictReader(open('leads_all.csv')))

CANON = {
 'A':"Replace WhatsApp/Drive video sharing: private courses, progress tracking, auto certificates (EN/AR RTL UI)",
 'B':"Self-paced video lessons per level, EN/AR interface, level-completion certificates",
 'C':"Staff/client compliance training portal: completion tracking and branded certificates for audits",
 'D':"White-label alternative: signed private playback + per-viewer watermark to protect paid content",
 'E':"Branded e-learning portal with admin analytics and category certificates",
}

def archetype(p):
    p=(p or '').lower()
    if 'whatsapp' in p or 'auto certificates' in p: return 'A'
    if 'self-paced' in p or 'level-' in p or 'level completion' in p: return 'B'
    if 'compliance' in p: return 'C'
    if 'watermark' in p or 'white-label' in p: return 'D'
    if 'e-learning portal' in p or 'admin analytics' in p: return 'E'
    return 'A'

for r in rows:
    a=archetype(r['pitch'])
    r['archetype']=a
    r['pitch_angle']=CANON[a]
    r['segment']=re.sub(r'\s+',' ',r['segment']).strip()

FIELDS=['n','organisation','segment','country','city','phone','email','website','instagram',
        'rating','reviews','priority','archetype','pitch_angle','status','notes']
with open('leads_full.csv','w',newline='',encoding='utf-8') as fh:
    w=csv.DictWriter(fh,fieldnames=FIELDS); w.writeheader()
    for r in rows: w.writerow({k:r.get(k,'') for k in FIELDS})

EMAILRE=re.compile(r"^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}$")
seen=set(); send=[]
for r in rows:
    e=r['email']
    if not EMAILRE.match(e) or e in seen:   # skip missing/invalid + duplicates
        continue
    seen.add(e); send.append(r)
with open('leads_sendlist.csv','w',newline='',encoding='utf-8') as fh:
    w=csv.DictWriter(fh,fieldnames=FIELDS); w.writeheader()
    for r in send: w.writerow({k:r.get(k,'') for k in FIELDS})

print('rows total          :', len(rows))
print('sendable (unique)   :', len(send))
print('no email on file    :', sum(1 for r in rows if not EMAILRE.match(r['email'])))
print('by country          :', dict(collections.Counter(r['country'] for r in send)))
print('by archetype        :', dict(collections.Counter(r['archetype'] for r in send)))
