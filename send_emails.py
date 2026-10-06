#!/usr/bin/env python3
"""
send_emails.py — sends the personalized outreach from maisterhb@gmail.com.

WHY YOU RUN IT (and not me): sending needs your Gmail password. I never see it;
the script talks straight to Gmail from your computer.

--------------------------------------------------------------------------
ONE-TIME SETUP (Gmail app password)
--------------------------------------------------------------------------
1. Google Account -> Security -> turn ON 2-Step Verification.
2. Then Google Account -> Security -> App passwords -> create one
   (name it "outreach"). You get a 16-character password like  abcd efgh ijkl mnop
3. Set it for this session:
       export GMAIL_APP_PASSWORD='abcdefghijklmnop'      # macOS / Linux
       setx  GMAIL_APP_PASSWORD "abcdefghijklmnop"       # Windows (new shell)
   (or just let the script prompt you — it will not echo what you type)
4. Fill in the CONFIG block in email_kit.py (name, company, booking link...).

--------------------------------------------------------------------------
RUNNING IT
--------------------------------------------------------------------------
   python3 send_emails.py                      # DRY RUN: writes preview emails, sends nothing
   python3 send_emails.py --test you@gmail.com # sends the 5 variants to yourself only
   python3 send_emails.py --send --limit 10    # first real 10
   python3 send_emails.py --send               # everything left (resumes, never double-sends)
   python3 send_emails.py --send --only A,B --country UAE

Every attempt is appended to sent_log.csv, so re-running skips anyone already
sent. Ctrl-C is safe: nothing is lost.
"""

import argparse, csv, getpass, hashlib, os, random, smtplib, ssl, sys, time
from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid

import email_kit

LEADS = "leads_sendlist.csv"   # regenerated automatically when you upload a CSV in the dashboard
LOG   = "sent_log.csv"
SMTP_HOST, SMTP_PORT = "smtp.gmail.com", 587


# --------------------------------------------------------------------- utils
def die(msg):
    print(f"\n  ✗ {msg}\n")
    sys.exit(1)


def check_config(force=False):
    bad = [k for k, v in email_kit.CONFIG.items()
           if isinstance(v, str) and v.startswith("YOUR_")]
    if bad and not force:
        die("email_kit.py still has placeholders: " + ", ".join(bad) +
            "\n    Fill them in (or re-run with --force if you know what you are doing).")
    return not bad


def load_sent():
    sent = set()
    if os.path.exists(LOG):
        with open(LOG, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                if row.get("status") == "SENT":
                    sent.add(row["email"].lower())
    return sent


def log_result(lead, subject, status, detail=""):
    new = not os.path.exists(LOG)
    with open(LOG, "a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["timestamp", "n", "organisation", "email", "subject", "status", "detail"])
        w.writerow([datetime.now().isoformat(timespec="seconds"), lead.get("n", ""),
                    lead.get("organisation", ""), lead.get("email", ""), subject, status, detail])


def build_message(lead, cfg, to_addr=None, variant_offset=0):
    subject, body = email_kit.render(lead, cfg, variant_offset=variant_offset)
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr((cfg["sender_name"], cfg["from_email"]))
    msg["To"] = to_addr or lead["email"]
    if cfg.get("reply_to"):
        msg["Reply-To"] = cfg["reply_to"]
    if cfg.get("bcc_self") and not to_addr:
        msg["Bcc"] = cfg["from_email"]
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=cfg["from_email"].split("@")[-1])
    # one-click opt-out — Gmail and Outlook read this as a sign of a legitimate sender
    msg["List-Unsubscribe"] = f"<mailto:{cfg['from_email']}?subject=unsubscribe>"
    msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    msg.set_content(body)
    return msg


def send_one(smtp, msg, to_addr):
    smtp.send_message(msg, to_addrs=[to_addr] + ([msg["Bcc"]] if msg["Bcc"] else []))


# ---------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--send", action="store_true", help="actually deliver (default is a dry run)")
    ap.add_argument("--limit", type=int, default=0, help="max emails this run")
    ap.add_argument("--start", type=int, default=0, help="skip the first N leads")
    ap.add_argument("--only", default="", help="archetypes to include, e.g. A,B (blank = all)")
    ap.add_argument("--country", default="", help="e.g. UAE / Qatar / 'Saudi Arabia'")
    ap.add_argument("--test", default="", help="send the variants to this address only")
    ap.add_argument("--delay-min", type=float, default=45, help="seconds between sends (min)")
    ap.add_argument("--delay-max", type=float, default=90, help="seconds between sends (max)")
    ap.add_argument("--force", action="store_true", help="send even with placeholder config")
    args = ap.parse_args()

    cfg = email_kit.CONFIG
    filled = check_config(args.force or not args.send)
    if not filled and not args.send:
        print("  ! Note: email_kit.py still has YOUR_* placeholders — fine for a dry run,")
        print("    but fill them in before the real send.\n")

    if not os.path.exists(LEADS):
        die(f"{LEADS} not found — keep it next to this script.")

    leads = list(csv.DictReader(open(LEADS, newline="", encoding="utf-8")))
    if args.only:
        keep = {a.strip().upper() for a in args.only.split(",")}
        leads = [l for l in leads if l["archetype"].upper() in keep]
    if args.country:
        leads = [l for l in leads if args.country.lower() in l["country"].lower()]
    leads = leads[args.start:]

    # ---------------------------------------------------------------- test mode
    if args.test:
        print(f"\n  TEST MODE → {args.test}: one email per pitch angle (5 total)\n")
        seen, picked = set(), []
        for l in leads:
            if l["archetype"] not in seen:
                seen.add(l["archetype"]); picked.append(l)
        pwd = os.environ.get("GMAIL_APP_PASSWORD") or getpass.getpass("Gmail app password: ")
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(cfg["from_email"], pwd.replace(" ", ""))
            for l in picked:
                msg = build_message(l, cfg, to_addr=args.test)
                send_one(smtp, msg, args.test)
                print(f"  ✓ sent to {args.test}: {msg['Subject']}")
                time.sleep(3)
        print("\n  Check the inbox, then run:  python3 send_emails.py --send --limit 10\n")
        return

    # ---------------------------------------------------------------- selection
    sent = load_sent()
    todo = [l for l in leads if l["email"].lower() not in sent]
    if args.limit:
        todo = todo[:args.limit]

    print(f"\n  From        : {cfg['from_email']}")
    print(f"  In list     : {len(leads)}   already sent: {len(leads) - len(todo) if not args.limit else len(sent)}")
    print(f"  This run    : {len(todo)}")
    print(f"  Pace        : {args.delay_min:.0f}-{args.delay_max:.0f}s between sends")
    print(f"  Mode        : {'LIVE SEND' if args.send else 'DRY RUN (nothing is sent)'}\n")

    if not args.send:
        os.makedirs("previews", exist_ok=True)
        for l in todo[:5]:
            subject, body = email_kit.render(l)
            fn = f"previews/{l['n']:0>3}_{l['email'].replace('@','_at_')}.txt"
            open(fn, "w", encoding="utf-8").write(f"To: {l['email']}\nSubject: {subject}\n\n{body}\n")
        print(f"  Wrote {min(5, len(todo))} sample emails to ./previews/")
        print("  Next:  python3 send_emails.py --test you@gmail.com\n")
        return

    # ------------------------------------------------------------------- send
    pwd = os.environ.get("GMAIL_APP_PASSWORD") or getpass.getpass("Gmail app password: ")
    pwd = pwd.replace(" ", "")
    ok = fail = 0
    seen_bodies = set()
    try:
        smtp = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=45)
        smtp.starttls(context=ssl.create_default_context())
        smtp.login(cfg["from_email"], pwd)
    except smtplib.SMTPAuthenticationError:
        die("Gmail rejected the login. Use an APP PASSWORD (16 chars), not your normal password,\n"
            "    and make sure 2-Step Verification is switched on.")
    except (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError, OSError) as e:
        die("Gmail closed the connection while signing in — the app password is probably wrong,\n"
            "    revoked, or from a different account. Create a new one at\n"
            "    Google Account -> Security -> App passwords. Nothing was sent.\n"
            f"    [{type(e).__name__}]")
    except Exception as e:
        die(f"Could not reach Gmail: {e}")

    with smtp:
        for i, l in enumerate(todo, 1):
            # if this body was already sent in this run, rotate the wording
            for offset in range(6):
                msg = build_message(l, cfg, variant_offset=offset)
                fp = hashlib.md5(msg.get_content().encode("utf-8")).hexdigest()
                if fp not in seen_bodies:
                    break
            seen_bodies.add(fp)
            for attempt in range(3):
                try:
                    send_one(smtp, msg, l["email"])
                    ok += 1
                    log_result(l, msg["Subject"], "SENT")
                    print(f"  [{i:>3}/{len(todo)}] ✓ {l['email']:<42} {msg['Subject'][:45]}")
                    break
                except (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError) as e:
                    print(f"  [{i:>3}/{len(todo)}] … reconnecting ({e})")
                    time.sleep(20)
                    smtp.connect(SMTP_HOST, SMTP_PORT)
                    smtp.starttls(context=ssl.create_default_context())
                    smtp.login(cfg["from_email"], pwd)
                except Exception as e:
                    fail += 1
                    log_result(l, msg["Subject"], "FAILED", str(e)[:200])
                    print(f"  [{i:>3}/{len(todo)}] ✗ {l['email']:<42} {e}")
                    break
            if i < len(todo):
                time.sleep(random.uniform(args.delay_min, args.delay_max))

    print(f"\n  Done. sent={ok}  failed={fail}  (log: {LOG})\n")
    print("  Deliverability tips: send 30-50/day max, keep the same subject style,")
    print("  and reply to anyone who answers from the same inbox — that is what keeps")
    print("  Gmail happy with cold outreach.\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n  Stopped by you. Progress is saved in sent_log.csv — just re-run.\n")
