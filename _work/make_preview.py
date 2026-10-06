import sys, os
sys.path.insert(0,'/home/user'); os.chdir('/home/user')
import csv, html, collections
import email_kit

rows=list(csv.DictReader(open('leads_sendlist.csv')))
by_arch=collections.OrderedDict()
for r in rows:
    by_arch.setdefault(r['archetype'], r)

cards=[]
for i,(a,lead) in enumerate(sorted(by_arch.items())):
    subject, body = email_kit.render(lead)
    body_html = html.escape(body).replace('\n','<br>')
    cards.append(f"""
    <div style="border:1px solid #dfe3e8;border-radius:12px;margin:0 0 26px 0;overflow:hidden;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,.06)">
      <div style="background:#1f3b57;color:#fff;padding:14px 20px;font:600 15px/1.35 -apple-system,Segoe UI,Roboto,Arial,sans-serif">
        Pitch angle {html.escape(a)} &nbsp;·&nbsp; {html.escape(lead['segment'])}
      </div>
      <div style="padding:16px 20px;border-bottom:1px solid #eef1f4;font:13px/1.5 -apple-system,Segoe UI,Roboto,Arial,sans-serif;color:#333">
        <div><b>To:</b> {html.escape(lead['organisation'])} &lt;{html.escape(lead['email'])}&gt; &nbsp;·&nbsp; {html.escape(lead['city'])}, {html.escape(lead['country'])}</div>
        <div style="margin-top:4px"><b>From:</b> Maister HB &lt;maisterhb@gmail.com&gt;</div>
        <div style="margin-top:4px"><b>Subject:</b> {html.escape(subject)}</div>
      </div>
      <div style="padding:18px 20px;font:14px/1.65 -apple-system,Segoe UI,Roboto,Arial,sans-serif;color:#1c1c1c">{body_html}</div>
    </div>""")

out = f"""<!doctype html><html><head><meta charset="utf-8">
<title>Outreach preview — {len(rows)} recipients</title></head>
<body style="margin:0;background:#f4f6f8;padding:28px">
<div style="max-width:900px;margin:0 auto">
  <h1 style="font:700 24px/1.3 -apple-system,Segoe UI,Roboto,Arial,sans-serif;color:#12293f;margin:0 0 6px">
    Outreach preview — 5 pitch angles</h1>
  <p style="font:14px/1.6 -apple-system,Segoe UI,Roboto,Arial,sans-serif;color:#52606d;margin:0 0 22px">
    Sending from <b>maisterhb@gmail.com</b> to <b>{len(rows)} recipients</b> (every lead in your sheet that has an email on file).
    Each recipient gets the angle that was marked for them. Placeholders like
    YOUR_NAME / YOUR_BOOKING_LINK come from the CONFIG block in <code>email_kit.py</code>.
  </p>
  {''.join(cards)}
</div></body></html>"""
open('email_previews.html','w',encoding='utf-8').write(out)
print('wrote email_previews.html with', len(cards), 'variants')
