# EduFormation outreach — Gulf training centres

**Sender:** Titraoui Habib · Software Engineer, EduFormation
**Reply-to:** maisterhb@gmail.com · **WhatsApp:** +213 667 807 146
**Product:** https://formation-agency.vercel.app/

---

## Run it on your own machine (no more restarts)

Download these files into one folder and keep them together:

```
app.py   ui/   email_kit.py   csv_import.py   leads_active.csv   start.sh   start.bat
```

Then:
- **macOS / Linux** — double-click **`start.sh`** (or `bash start.sh`)
- **Windows** — double-click **`start.bat`**
- It asks for your Gmail app password once (16 characters), opens your browser at
  `http://localhost:8000`, and keeps running until you close the window.

Nothing is hidden: the launcher checks Python, warns if port 8000 is busy, opens the browser
after the server is up, and stops cleanly with Ctrl-C. Everything stays on your machine —
no cloud, no account, no data leaving the folder.

## The interface

```bash
python3 app.py          →  http://localhost:8000
```
(Already running in this workspace as the **Outreach dashboard** preview.)

### Upload a CSV — any CSV
Top of the Leads tab: **Upload CSV**, or drag a file onto the panel. That's the whole workflow
next month: export a new lead list, drop it in, and it becomes the active list.

The importer is forgiving on purpose:
- **Any column names** — `Company Name`, `E-Mail`, `Mobile`, `Stars`, `Google reviews`, `Category`,
  `Notes` and 60-odd synonyms all map automatically. Semicolon, tab and pipe files work too.
- **No pitch column needed** — each row's angle is inferred from its own words. "Needs audit-ready
  completion records" → compliance angle. "Worried about piracy / sells recordings" → protection
  angle. "IELTS, self-paced videos" → language angle. Otherwise training-centre default.
- **Duplicates merged**, invalid addresses dropped (the row is kept so you can fix it later),
  Excel BOM/newlines handled.

After an upload you get a report: rows imported, emailable, duplicates merged, angles inferred.

### Every row gets the email it needs — and no two emails match
Five angles, taken from the sheet itself:

| Code | Rows | The email leads with |
|---|---|---|
| A | 82 | private storage + signed links, progress and watch time, auto certificates, AR/FR/EN RTL |
| B | 31 | levels and categories, resume-watching, personal dashboards, level certificates |
| C | 30 | per-learner completion and watch time, audit-ready records, branded certificates |
| D | 14 | signed playback, per-viewer forensic watermark, capture/PiP/cast blocking, DRM-ready |
| E | 4 | learner/video/completion/watch-hour analytics, category certificates |

On top of that, **greeting, opening line, pain paragraph, bullet framing, call-to-action, sign-off
and subject pattern rotate per recipient** (picked deterministically from the address, so previews
stay honest). Current build: **94 of 94 emails are unique**, zero duplicate bodies.

### Anti-spam by construction
- Plain text only — no HTML, no images, no tracking pixels, no attachments
- Max 1 link in the body, and never in the first line
- No trigger vocabulary (free, guarantee, act now, click here, 100%…), no exclamation marks, no ALL CAPS
- One-click opt-out: `List-Unsubscribe` + `List-Unsubscribe-Post` headers, plus a plain-language
  "reply stop" line and a real signature with a real place (Setif, Algeria)
- Pacing enforced (45–90s between sends by default), batches capped, resumable, never double-sends
- Every email is checked before it goes: open any lead → **deliverability panel** shows
  link count, spam-word scan, caps, subject length and a uniqueness proof against the other 93

### Everything in one place
- **Leads** — 161 rows, search, country/angle/status filters, sorting, click any row for *its* email
- **Edit copy per row** — Save for this row (tagged **Custom**), or Reset to template
- **Templates** — edit each angle's opening variants, solution paragraph, bullets and subject tails
- **Send** — Dry run / Test (to your inbox) / Live, with batch size, country, angle, gaps,
  live progress bar and a console
- **Activity** — every attempt from `sent_log.csv`
- **Settings** — name, title, WhatsApp, email, demo link, booking link, subject patterns, Arabic block

---

## One-click sending

Press **Send 35 today** at the top right. That is the whole thing.

The first time, it needs your app password once:

1. **Send options** → paste the 16-character app password → tick
   **“Remember on this computer”** → **Test password** (it tells you straight away whether Gmail
   accepts it). 
2. From then on the button sends your daily batch with a single press — no password, no settings.
3. `Forget saved password` deletes it instantly.

How the one press behaves:
- sends `daily cap − already sent today` (default cap 35, change it in Settings)
- skips everyone already in `sent_log.csv`, so pressing it twice a day never double-sends
- keeps the 45–90s gap and a copy in your inbox (BCC)
- shows live progress; `Stop` halts cleanly and resumes later
- if the password is wrong or revoked it says exactly that and sends nothing

**Where the password lives:** an owner-only file `.gmail_app_password` (permissions `600`) in this
folder. It is never sent anywhere, never stored in the browser, and never written into any log. An
app password can only *send* mail — it cannot read your inbox — and you can revoke it at Google at
any moment. Keep this folder to yourself; if the machine is shared, leave the checkbox unticked and
paste the password per run instead.

**Command line equivalent** (same engine, same rules):
```bash
export GMAIL_APP_PASSWORD='abcdefghijklmnop'
python3 send_emails.py --send            # sends the remaining queue in one command
```

## Sending for real

**Never use your Google account password.** Gmail refuses account passwords for SMTP, and an app
password is a *separate*, revocable 16-character code that can be deleted at any time without
touching your real password. Nothing here ever needs your account password, and you never have to
send a credential to me — the dashboard talks to Gmail directly from wherever you run it.

1. **Settings tab** — everything is already filled in with your details; add a booking link only if
   you want one (if it's blank the CTA asks for a reply instead).
2. **Gmail app password** — Google Account → Security → 2-Step Verification ON → App passwords →
   create one named "outreach". You get 16 characters (spaces are cosmetic).
   Paste it into the Send panel and press **Test password** — it replies with either
   "signed in successfully" or exactly why Gmail refused it. The password stays in memory, is
   cleared when the run ends, and is never written to disk. Or export it:
   ```bash
   export GMAIL_APP_PASSWORD='abcdefghijklmnop'
   python3 app.py
   ```
3. **Dry run** first, then **Test** to your own inbox, then **Live** with "how many this run" ≈ 35.
   Run it daily until the list is done.

**Built-in guards:** a password that isn't exactly 16 characters is refused before anything is
sent — client-side with an explanation, and again server-side. If Gmail rejects an app password,
the panel tells you to regenerate it (old app passwords are revoked whenever you change your
Google password).

**If you ever paste a real password somewhere it shouldn't be** (chat, ticket, screenshot):
change it at myaccount.google.com/security. Changing your Google password instantly revokes every
app password too, so the outreach sender just needs a fresh one afterwards.

CLI equivalent (shares the same copy engine, overrides included):
```bash
python3 send_emails.py                       # dry run → ./previews/
python3 send_emails.py --test maisterhb@gmail.com
python3 send_emails.py --send --limit 10
```

## Files

| File | What it is |
|---|---|
| `app.py` + `ui/index.html` | The interface (upload, preview, per-row edits, sending). |
| `csv_import.py` | The importer — fuzzy columns, angle inference, dedupe. |
| `email_kit.py` | The copy engine — angles, variant pools, spam lint. |
| `send_emails.py` | Headless sender with the same rules. |
| `leads_active.csv` | Whatever you uploaded last — the live list. |
| `dashboard_snapshot.html` | The dashboard with data embedded (opens with no server). |
| `email_previews.html` | The 5 email variants side by side. |
| `leads_full.csv` / `leads_sendlist.csv` | Auto-generated: all rows / emailable rows. |
| `ui_settings.json`, `ui_templates.json`, `ui_overrides.json`, `sent_log.csv` | Your settings, edited copy, per-row overrides, send history. |

## Still true about the product
No payments, quizzes/exams, live classes, instructor marketplace or email/SMS notifications yet —
the copy deliberately doesn't claim them. If a lead asks, those are roadmap items.

## Practical notes
- Expect a few bounces: addresses come off public listings, and `info@` boxes die quietly.
  `sent_log.csv` records them — that's your cleanup list.
- 67 rows have no email on file; they're in `leads_full.csv` with phone + website if you want a
  WhatsApp follow-up list (your number is in the Settings tab, ready to paste).
- Reply to anyone who answers from the same Gmail account. That single habit does more for
  deliverability than any wording change.
