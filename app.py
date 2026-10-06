#!/usr/bin/env python3
"""
app.py — Outreach dashboard for the Gulf training-centre campaign.

A tiny stdlib-only web app: lead table, per-lead email preview, editable
templates, and a send engine that talks straight to Gmail SMTP.

    python3 app.py                 # http://localhost:8000

The Gmail app password is only ever held in memory for the duration of a run:
it is never written to disk, never logged, and never returned by any endpoint.
"""

import csv, hashlib, json, os, random, re, smtplib, ssl, threading, time, traceback
from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import csv_import
import email_kit

HERE = os.path.dirname(os.path.abspath(__file__))
LEADS_ALL = os.path.join(HERE, "leads_full.csv")
LEADS_SEND = os.path.join(HERE, "leads_sendlist.csv")
DATASET_FILE = os.path.join(HERE, "dataset.json")
DEFAULT_DATASET = {
    "file": "leads_active.csv",
    "label": "EduFormation_Leads-Gulf Leads.csv",
    "uploaded": "",
    "report": {},
}
LOG = os.path.join(HERE, "sent_log.csv")
SETTINGS_FILE = os.path.join(HERE, "ui_settings.json")
TEMPLATES_FILE = os.path.join(HERE, "ui_templates.json")
OVERRIDES_FILE = os.path.join(HERE, "ui_overrides.json")
SECRET_FILE = os.path.join(HERE, ".gmail_app_password")   # 0600, opt-in, deletable any time
UI_FILE = os.path.join(HERE, "ui", "index.html")

SMTP_HOST, SMTP_PORT = "smtp.gmail.com", 587
EMAIL_RE = re.compile(r"^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}$")

DEFAULT_SETTINGS = {
    "sender_name": "Titraoui Habib",
    "sender_title": "Software Engineer",
    "company_name": "EduFormation",
    "website": "https://formation-agency.vercel.app/",
    "demo_link": "https://formation-agency.vercel.app/",
    "whatsapp": "+213 667 807 146",
    "phone": "+213 667 807 146",
    "postal_address": "Setif, Algeria",
    "calendar_link": "",
    "from_email": "maisterhb@gmail.com",
    "reply_to": "maisterhb@gmail.com",
    "bcc_self": True,
    "bilingual": False,
    "subject_template": "",
    "subject_patterns": ["{org} — {hook}", "{hook} — {org}", "{org}: {hook}"],
    "delay_min": 45,
    "delay_max": 90,
}

class AuthProblem(Exception):
    """Login to Gmail failed — shown to the user verbatim."""


LOCK = threading.Lock()
STATE = {
    "running": False, "mode": None, "total": 0, "index": 0, "ok": 0, "fail": 0,
    "skipped": 0, "current": "", "started": None, "finished": None,
    "log": [], "error": None, "stop": False,
}
PASSWORD = None  # memory only


# --------------------------------------------------------------------- data
def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        return [r for r in csv.DictReader(fh)]


def load_settings():
    s = dict(DEFAULT_SETTINGS)
    s["subject_patterns"] = list(DEFAULT_SETTINGS["subject_patterns"])
    if os.path.exists(SETTINGS_FILE):
        try:
            s.update(json.load(open(SETTINGS_FILE, encoding="utf-8")))
        except Exception:
            pass
    email_kit.CONFIG.update({k: v for k, v in s.items() if k in email_kit.CONFIG})
    email_kit.CONFIG["from_email"] = s.get("from_email") or DEFAULT_SETTINGS["from_email"]
    email_kit.CONFIG["reply_to"] = s.get("reply_to") or DEFAULT_SETTINGS["reply_to"]
    email_kit.CONFIG["bcc_self"] = bool(s.get("bcc_self"))
    email_kit.CONFIG["bilingual"] = bool(s.get("bilingual"))
    for key in ("sender_name", "sender_title", "company_name", "website", "demo_link",
                "whatsapp", "phone", "calendar_link", "postal_address"):
        if s.get(key) is not None:
            email_kit.CONFIG[key] = s[key]
    if isinstance(s.get("subject_patterns"), list) and s["subject_patterns"]:
        email_kit.CONFIG["subject_patterns"] = [p for p in s["subject_patterns"] if p.strip()]
    return s


def save_settings(new):
    s = load_settings()
    s.update({k: v for k, v in new.items() if k in DEFAULT_SETTINGS})
    json.dump(s, open(SETTINGS_FILE, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    return load_settings()


def load_templates():
    """Applied on top of email_kit's defaults."""
    t = {}
    if os.path.exists(TEMPLATES_FILE):
        try:
            t = json.load(open(TEMPLATES_FILE, encoding="utf-8"))
        except Exception:
            t = {}
    return t


def apply_templates():
    """Overlay ui_templates.json on top of the shipped copy."""
    t = load_templates()
    for angle, val in t.items():
        if not isinstance(val, dict):
            continue
        if val.get("pain"):
            email_kit.PAIN[angle] = [p for p in val["pain"] if p.strip()] or email_kit.PAIN[angle]
        if val.get("solution"):
            email_kit.SOLUTION[angle] = val["solution"]
        if val.get("bullets"):
            email_kit.BULLETS[angle] = [b for b in val["bullets"] if b.strip()]
        if val.get("hooks"):
            email_kit.HOOKS[angle] = [h for h in val["hooks"] if h.strip()] or email_kit.HOOKS[angle]
    return t


def save_templates(new):
    json.dump(new, open(TEMPLATES_FILE, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    return load_templates()


def get_secret():
    """The saved app password, if the user chose to remember it. Env var wins."""
    env = (os.environ.get("GMAIL_APP_PASSWORD") or "").strip()
    if env:
        return env.replace(" ", ""), "environment"
    if os.path.exists(SECRET_FILE):
        try:
            pwd = open(SECRET_FILE, encoding="utf-8").read().strip().replace(" ", "")
            return (pwd, "saved") if pwd else (None, None)
        except Exception:
            return None, None
    return None, None


def save_secret(pwd):
    """Write with owner-only permissions (0600 where the OS honours it)."""
    pwd = (pwd or "").replace(" ", "").strip()
    fd = os.open(SECRET_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(pwd)
    try:
        os.chmod(SECRET_FILE, 0o600)
    except Exception:
        pass
    return True


def clear_secret():
    if os.path.exists(SECRET_FILE):
        os.remove(SECRET_FILE)
    return True


def sent_today():
    today = datetime.now().strftime("%Y-%m-%d")
    return sum(1 for r in read_csv(LOG)
               if r.get("status") == "SENT" and (r.get("timestamp") or "").startswith(today))


def load_overrides():
    """{row number: {"subject":..., "body":...}} — rows you edited by hand win."""
    if os.path.exists(OVERRIDES_FILE):
        try:
            return json.load(open(OVERRIDES_FILE, encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_overrides(data):
    json.dump(data, open(OVERRIDES_FILE, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    return data


def dataset():
    d = dict(DEFAULT_DATASET)
    if os.path.exists(DATASET_FILE):
        try:
            d.update(json.load(open(DATASET_FILE, encoding="utf-8")))
        except Exception:
            pass
    return d


def save_dataset(d):
    json.dump(d, open(DATASET_FILE, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    return d


def leads_path():
    return os.path.join(HERE, dataset().get("file") or "leads_active.csv")


def all_leads():
    rows = read_csv(leads_path())
    for r in rows:
        r["sendable"] = bool(EMAIL_RE.match(r.get("email", "")))
    return rows


def body_fingerprint(lead):
    """md5 of the rendered body — used to prove two leads are not getting the same text."""
    _, body = render(lead)
    return hashlib.md5(body.encode("utf-8")).hexdigest()


def sent_map():
    out = {}
    if os.path.exists(LOG):
        for row in read_csv(LOG):
            if row.get("status") in ("SENT", "TEST"):
                out[row["email"].lower()] = row
    return out


def render(lead):
    ov = load_overrides().get(str(lead.get("n")))
    if ov and (ov.get("subject") or ov.get("body")):
        subject = ov.get("subject") or email_kit.render(lead)[0]
        return subject, ov.get("body") or ""

    cfg = dict(email_kit.CONFIG)
    cfg.update(load_settings())
    cfg["bcc_self"] = bool(cfg.get("bcc_self"))
    cfg["bilingual"] = bool(cfg.get("bilingual"))
    sp = cfg.get("subject_patterns")
    if isinstance(sp, list) and sp:
        cfg["subject_patterns"] = sp
    apply_templates()
    subject, body = email_kit.render(lead, cfg)
    tpl = (cfg.get("subject_template") or "").strip()
    if tpl and "{" in tpl and "org" in tpl:      # optional hand-written pattern wins
        angle = (lead.get("pitch_angle") or "").strip()
        hook = (email_kit.HOOKS.get(angle) or [""])[0]
        try:
            subject = tpl.format(org=lead.get("organisation", ""), city=lead.get("city", ""),
                                 country=lead.get("country", ""), hook=hook,
                                 segment=lead.get("segment", ""))
        except Exception:
            pass
    return subject, body


def log_row(lead, subject, status, detail=""):
    new = not os.path.exists(LOG)
    with open(LOG, "a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["timestamp", "n", "organisation", "email", "subject", "status", "detail"])
        w.writerow([datetime.now().isoformat(timespec="seconds"), lead.get("n", ""),
                    lead.get("organisation", ""), lead.get("email", ""), subject, status, detail])


def build_message(lead, to_addr=None):
    cfg = dict(email_kit.CONFIG)
    cfg.update(load_settings())
    subject, body = render(lead)
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr((cfg.get("sender_name") or cfg["from_email"], cfg["from_email"]))
    msg["To"] = to_addr or lead["email"]
    if cfg.get("reply_to"):
        msg["Reply-To"] = cfg["reply_to"]
    if cfg.get("bcc_self") and not to_addr:
        msg["Bcc"] = cfg["from_email"]
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=cfg["from_email"].split("@")[-1])
    # one-click opt-out: Gmail and Outlook treat this as a sign of a legitimate sender
    msg["List-Unsubscribe"] = f"<mailto:{cfg['from_email']}?subject=unsubscribe>"
    msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    msg.set_content(body)
    return msg


# ------------------------------------------------------------------- sender
def slog(line, level="info"):
    with LOCK:
        STATE["log"].append({"t": datetime.now().strftime("%H:%M:%S"), "msg": line, "level": level})
        STATE["log"] = STATE["log"][-400:]


def worker(mode, limit, only, country, dmin, dmax, password, test_to):
    global PASSWORD
    try:
        leads = [r for r in all_leads() if r["sendable"]]
        if only:
            keep = {a.strip().upper() for a in only}
            leads = [l for l in leads if (l.get("archetype") or "").upper() in keep]
        if country:
            leads = [l for l in leads if country.lower() in l["country"].lower()]

        already = sent_map()
        if mode == "live":
            leads = [l for l in leads if l["email"].lower() not in already]
        if mode == "test":
            seen, picked = set(), []
            for l in leads:
                if l["archetype"] not in seen:
                    seen.add(l["archetype"]); picked.append(l)
            leads = picked
        if limit:
            leads = leads[:int(limit)]

        with LOCK:
            STATE.update({"running": True, "mode": mode, "total": len(leads), "index": 0,
                          "ok": 0, "fail": 0, "skipped": 0, "current": "", "error": None,
                          "stop": False, "started": datetime.now().isoformat(timespec="seconds"),
                          "finished": None})
        slog(f"Started {mode} run — {len(leads)} message(s).", "info")

        smtp = None
        if mode in ("live", "test"):
            slog("Connecting to smtp.gmail.com:587 …")
            try:
                smtp = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=45)
                smtp.starttls(context=ssl.create_default_context())
                smtp.login(email_kit.CONFIG["from_email"], password)
            except smtplib.SMTPAuthenticationError:
                raise AuthProblem("Gmail rejected that app password. Create a fresh one at "
                                  "Google Account → Security → App passwords, then paste it in and "
                                  "press “Test password”.")
            except (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError, OSError) as e:
                raise AuthProblem(
                    "Gmail closed the connection while signing in — that almost always means the app "
                    "password is wrong, revoked, or belongs to a different account. Create a new app "
                    "password (old ones are revoked whenever your Google password changes), paste it "
                    "in, and press “Test password” first. Nothing was sent. [" + type(e).__name__ + "]")
            slog("Authenticated. Sending.", "ok")

        for i, lead in enumerate(leads, 1):
            if STATE["stop"]:
                slog("Stopped by user.", "warn"); break
            to = test_to if mode == "test" else lead["email"]
            try:
                msg = build_message(lead, to_addr=test_to if mode == "test" else None)
            except Exception as e:
                with LOCK:
                    STATE["index"] = i; STATE["fail"] += 1
                slog(f"✗ render failed {lead['email']}: {e}", "err")
                continue
            with LOCK:
                STATE["index"] = i
                STATE["current"] = f"{lead['organisation']} <{lead['email']}>"

            if mode == "dry":
                slog(f"[dry {i}/{len(leads)}] would send → {lead['email']} · {msg['Subject'][:60]}")
            else:
                for attempt in range(3):
                    try:
                        smtp.send_message(msg, to_addrs=[to] + ([msg["Bcc"]] if msg["Bcc"] else []))
                        log_row(lead, msg["Subject"], "TEST" if mode == "test" else "SENT")
                        with LOCK:
                            STATE["ok"] += 1
                        slog(f"✓ {i}/{len(leads)} → {to}", "ok")
                        break
                    except (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError) as e:
                        slog(f"… reconnecting ({e})", "warn")
                        time.sleep(15)
                        try:
                            smtp.connect(SMTP_HOST, SMTP_PORT)
                            smtp.starttls(context=ssl.create_default_context())
                            smtp.login(email_kit.CONFIG["from_email"], password)
                        except Exception as e2:
                            slog(f"reconnect failed: {e2}", "err")
                    except Exception as e:
                        log_row(lead, msg["Subject"], "FAILED", str(e)[:200])
                        with LOCK:
                            STATE["fail"] += 1
                        slog(f"✗ {to} — {e}", "err")
                        break
            if i < len(leads):
                nap = random.uniform(float(dmin), float(dmax))
                slog(f"waiting {nap:.0f}s …")
                slept = 0
                while slept < nap and not STATE["stop"]:
                    time.sleep(min(1, nap - slept)); slept += 1

        if smtp:
            try: smtp.quit()
            except Exception: pass
        with LOCK:
            STATE["running"] = False
            STATE["finished"] = datetime.now().isoformat(timespec="seconds")
            STATE["current"] = ""
        slog(f"Run finished — sent {STATE['ok']}, failed {STATE['fail']}.", "ok")
    except AuthProblem as e:
        slog(str(e), "err")
        with LOCK:
            STATE["running"] = False
            STATE["error"] = "auth"
    except Exception as e:
        slog(f"Fatal: {e}", "err")
        with LOCK:
            STATE["running"] = False; STATE["error"] = str(e)
        traceback.print_exc()
    finally:
        PASSWORD = None
        password = None


# ------------------------------------------------------------------- server
class Handler(BaseHTTPRequestHandler):
    server_version = "OutreachUI/1.0"

    def log_message(self, fmt, *args):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:
            return {}

    def _file(self, path, ctype):
        if not os.path.exists(path):
            self.send_error(404); return
        data = open(path, "rb").read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    # ------------------------------------------------------------------ GET
    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)

        if u.path in ("/", "/index.html"):
            return self._file(UI_FILE, "text/html; charset=utf-8")

        if u.path == "/api/state":
            sent = sent_map()
            overrides = load_overrides()
            rows = []
            for r in all_leads():
                rows.append({
                    "n": r.get("n"), "organisation": r.get("organisation"),
                    "segment": r.get("segment"), "country": r.get("country"),
                    "city": r.get("city"), "phone": r.get("phone"), "email": r.get("email"),
                    "website": r.get("website"), "rating": r.get("rating"),
                    "reviews": r.get("reviews"), "priority": r.get("priority"),
                    "archetype": r.get("archetype"), "status": r.get("status"),
                    "sendable": r.get("sendable", False),
                    "sent": r.get("email", "").lower() in sent,
                    "custom": str(r.get("n")) in overrides,
                })
            angles = {}
            for r in rows:
                a = r["archetype"] or "?"
                angles.setdefault(a, {"count": 0, "angle": r["archetype"]})
                angles[a]["count"] += 1
            fps = {}
            for r in rows:
                if r["sendable"]:
                    fps.setdefault(body_fingerprint(r), []).append(r["n"])
            dup_fp = {k: v for k, v in fps.items() if len(v) > 1}
            return self._json({
                "leads": rows,
                "overrides": len(overrides),
                "dataset": dataset(),
                "duplicate_bodies": len(dup_fp),
                "stats": {
                    "total": len(rows),
                    "sendable": sum(1 for r in rows if r["sendable"]),
                    "no_email": sum(1 for r in rows if not r["sendable"]),
                    "sent": sum(1 for r in rows if r["sent"]),
                    "countries": sorted({r["country"] for r in rows if r["country"]}),
                },
                "angles": angles,
                "settings": load_settings(),
                "has_password": bool(get_secret()[0]),
                "password_source": get_secret()[1],
                "sent_today": sent_today(),
                "daily_cap": int(load_settings().get("daily_cap") or 35),
                "one_click_ready": bool(get_secret()[0]),
                "running": STATE["running"],
            })

        if u.path == "/api/preview":
            n = (q.get("n") or [""])[0]
            lead = next((r for r in all_leads() if r.get("n") == n), None)
            if not lead:
                return self._json({"error": "not found"}, 404)
            subject, body = render(lead)
            checks = email_kit.lint(subject, body)
            fp = hashlib.md5(body.encode("utf-8")).hexdigest()
            twins = []
            if lead.get("email"):
                for other in all_leads():
                    if other.get("n") != n and other.get("email"):
                        if body_fingerprint(other) == fp:
                            twins.append(other.get("organisation"))
            checks.append({
                "level": "warn" if twins else "ok",
                "msg": ("Identical body to: " + ", ".join(twins[:3])) if twins
                       else "Unique — no other lead receives this exact message.",
            })
            return self._json({"n": n, "to": lead.get("email") or "",
                               "from": load_settings()["from_email"],
                               "organisation": lead.get("organisation"),
                               "subject": subject, "body": body,
                               "angle": lead.get("archetype", ""),
                               "custom": str(n) in load_overrides(),
                               "checks": checks})

        if u.path == "/api/templates":
            apply_templates()
            return self._json({
                "angles": [{"key": k, "pains": email_kit.PAIN.get(k, []),
                            "solution": email_kit.SOLUTION.get(k, ""),
                            "bullets": email_kit.BULLETS.get(k, []),
                            "hooks": email_kit.HOOKS.get(k, [])}
                           for k in email_kit.PAIN]
            })

        if u.path == "/api/progress":
            with LOCK:
                return self._json(dict(STATE))

        if u.path == "/api/activity":
            rows = read_csv(LOG)
            for r in rows:
                r.pop("detail", None)
            return self._json({"rows": rows[-300:][::-1]})

        self.send_error(404)

    # ----------------------------------------------------------------- POST
    def do_POST(self):
        u = urlparse(self.path)
        data = self._body()

        if u.path == "/api/smtp-check":
            pwd = (data.get("password") or "").replace(" ", "")
            if not pwd and not data.get("use_saved"):
                return self._json({"ok": False, "msg": "No password entered."})
            if not pwd:
                pwd, _src = get_secret()
                if not pwd:
                    return self._json({"ok": False, "msg": "No saved password to test."})
            if len(pwd) != 16:
                return self._json({"ok": False, "short": True, "msg":
                    f"That is {len(pwd)} characters. Google app passwords are exactly 16 — this looks "
                    "like an account password, which Google refuses for SMTP. Create one at Google "
                    "Account -> Security -> App passwords."})
            try:
                smtp = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=25)
                smtp.starttls(context=ssl.create_default_context())
                smtp.login(email_kit.CONFIG["from_email"], pwd)
                smtp.quit()
                remembered = ""
                if data.get("remember"):
                    save_secret(pwd)
                    remembered = (" It is now saved on this computer (owner-only file) so future "
                                  "sends are one click — press Forget to remove it.")
                return self._json({"ok": True, "saved": os.path.exists(SECRET_FILE), "msg":
                    "Signed in successfully — this app password works and is ready to send from "
                    + email_kit.CONFIG["from_email"] + "." + remembered})
            except smtplib.SMTPAuthenticationError:
                return self._json({"ok": False, "msg":
                    "Gmail rejected that app password. Regenerate it at Google Account -> Security -> "
                    "App passwords (old ones are revoked when you change your Google password)."})
            except Exception as e:
                return self._json({"ok": False, "msg": f"Could not reach Gmail: {e}"})

        if u.path == "/api/upload":
            filename = (data.get("filename") or "leads.csv").strip()
            text = data.get("csv") or ""
            if not text.strip():
                return self._json({"error": "The file came through empty."}, 400)
            try:
                rows, report = csv_import.parse_csv_text(text, filename)
            except Exception as e:
                return self._json({"error": f"Could not read that CSV: {e}"}, 400)
            if not rows:
                return self._json({"error": "No usable rows found — is that the right file?"}, 400)

            out = os.path.join(HERE, "leads_active.csv")
            csv_import.to_csv(rows, out)
            # keep the CLI in sync too
            csv_import.to_csv([r for r in rows if EMAIL_RE.match(r.get("email", ""))], LEADS_SEND)
            csv_import.to_csv(rows, LEADS_ALL)
            save_dataset({"file": "leads_active.csv", "label": filename,
                          "uploaded": datetime.now().isoformat(timespec="seconds"),
                          "report": {k: v for k, v in report.items()
                                     if k in ("rows", "emailable", "duplicates_merged",
                                              "invalid_emails", "angles_inferred", "unmapped",
                                              "delimiter")}})
            return self._json({"ok": True, "report": report,
                               "dataset": dataset()})

        if u.path == "/api/settings":
            return self._json({"ok": True, "settings": save_settings(data)})

        if u.path == "/api/templates":
            return self._json({"ok": True, "templates": save_templates(data.get("templates", {}))})

        if u.path == "/api/override":
            n = str(data.get("n") or "").strip()
            if not n:
                return self._json({"error": "row number required"}, 400)
            ov = load_overrides()
            if data.get("clear"):
                ov.pop(n, None)
            else:
                ov[n] = {"subject": (data.get("subject") or "").strip(),
                         "body": (data.get("body") or "").strip(),
                         "saved_at": datetime.now().isoformat(timespec="seconds")}
            save_overrides(ov)
            return self._json({"ok": True, "custom": n in ov})

        if u.path == "/api/secret":
            if data.get("clear"):
                clear_secret()
                return self._json({"ok": True, "saved": False})
            pwd = (data.get("password") or "").replace(" ", "")
            if len(pwd) != 16:
                return self._json({"error": "App passwords are exactly 16 characters."}, 400)
            save_secret(pwd)
            return self._json({"ok": True, "saved": True})

        if u.path == "/api/send":
            global PASSWORD
            if STATE["running"]:
                return self._json({"error": "already running"}, 409)
            mode = data.get("mode", "dry")
            pwd = (data.get("password") or "").replace(" ", "")
            source = "entered"
            if not pwd:
                pwd, source = get_secret()
                if pwd:
                    source = source or "saved"
            if mode in ("live", "test") and not pwd:
                return self._json({"error":
                    "No app password yet. Paste it once in the send panel (tick “remember on this "
                    "computer”) and every send after that is one click. Google app password, 16 "
                    "characters — not your account password."}, 400)
            if mode in ("live", "test") and len(pwd) != 16:
                return self._json({"error":
                    f"That password is {len(pwd)} characters — Google app passwords are exactly 16 "
                    "and account passwords are refused for SMTP. Create an app password at Google "
                    "Account -> Security -> App passwords (2-Step Verification first). Nothing was sent."},
                    400)
            if mode == "test" and not data.get("test_to"):
                return self._json({"error": "test recipient required"}, 400)
            if data.get("remember") and pwd and source == "entered":
                save_secret(pwd)
            PASSWORD = pwd or None
            limit = data.get("limit")
            if limit in (None, "", 0):
                limit = 0 if mode != "live" else max(
                    0, int(load_settings().get("daily_cap") or 35) - sent_today())
            slog(f"Using the {'saved ' if source == 'saved' else ''}app password "
                 f"({source}).", "info")
            threading.Thread(
                target=worker,
                args=(mode, limit, data.get("only") or [],
                      (data.get("country") or "").strip(),
                      data.get("delay_min") or 45, data.get("delay_max") or 90,
                      pwd or None, data.get("test_to") or ""),
                daemon=True).start()
            return self._json({"ok": True})

        if u.path == "/api/stop":
            with LOCK:
                STATE["stop"] = True
            return self._json({"ok": True})

        self.send_error(404)


def main():
    load_settings()
    apply_templates()
    port = int(os.environ.get("PORT", "8000"))
    httpd = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"\n  Outreach dashboard → http://localhost:{port}\n"
          f"  from: {email_kit.CONFIG['from_email']}   leads: {len(all_leads())}\n", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
