"""
email_kit.py — the copy engine.

Two ideas do the heavy lifting here:

1. EVERY ROW GETS THE EMAIL IT NEEDS
   The opening paragraph and the bullets come from that row's own PITCH ANGLE
   (A–E). A language school hears about levels and self-paced lessons; a safety
   trainer hears about completion records that survive an audit.

2. NO TWO EMAILS ARE THE SAME
   Greeting, opener, pain paragraph, bullet framing, call-to-action, subject
   pattern and sign-off are each drawn from several variants, picked
   deterministically from the recipient's address. Same lead always renders the
   same message (so previews are honest), but two different leads essentially
   never receive identical text — which is the single biggest thing that keeps
   cold mail out of the spam folder.

Everything is plain text: no HTML, no images, no tracking pixels, no more than
two links, no spam-trigger vocabulary.
"""

import re

CONFIG = {
    # ---- who is sending ------------------------------------------------
    "sender_name":   "Titraoui Habib",
    "sender_title":  "Software Engineer",
    "company_name":  "EduFormation",
    "website":       "https://formation-agency.vercel.app/",
    "demo_link":     "https://formation-agency.vercel.app/",
    "whatsapp":      "+213 667 807 146",
    "phone":         "+213 667 807 146",
    "calendar_link": "",                     # optional; blank = CTA asks for a reply
    "postal_address": "Setif, Algeria",      # a real place makes the footer legitimate

    # ---- sending -------------------------------------------------------
    "from_email":    "maisterhb@gmail.com",
    "reply_to":      "maisterhb@gmail.com",
    "bcc_self":      True,
    "bilingual":     False,     # True adds a short Arabic paragraph to each email

    # subject patterns — {org}, {hook}, {city}, {country}, {segment}
    "subject_patterns": [
        "{org} — {hook}",
        "{hook} — {org}",
        "{org}: {hook}",
    ],
}

# ======================================================================= A–E
# Pain paragraph, 2–3 variants per angle. The solution paragraph is fixed,
# because the product facts must stay accurate.
PAIN = {
    "Replace WhatsApp/Drive video sharing: private courses, progress tracking, auto certificates (EN/AR RTL UI)": [
        "Most training centres at your scale still run private and in-house courses through "
        "WhatsApp groups and shared Drive folders. Videos get forwarded, nobody can say who "
        "actually finished, and certificates get prepared by hand.",

        "If your in-house courses go out as WhatsApp files or a shared Drive link, you already "
        "know how it ends: the file is forwarded, completion is a guess, and certificates are "
        "typed out one by one.",

        "Running private courses over WhatsApp and Drive works fine right up to the moment you "
        "need to know who watched, who finished, and who is owed a certificate. Then it becomes "
        "guesswork.",
    ],
    "Self-paced video lessons per level, EN/AR interface, level-completion certificates": [
        "What decides how many students finish a level is usually what happens between classes: "
        "a recorded lesson shared as a file, watched once, never revisited — and no simple way "
        "to see who is falling behind.",

        "Recorded lessons are usually the weakest link in a language course. They get sent as "
        "files, watched once, and by exam week nobody can say who actually did the work.",

        "Between classes is where language students quietly disappear. The lesson was sent, but "
        "nobody tracked whether it was watched, replayed, or skipped straight through.",
    ],
    "Staff/client compliance training portal: completion tracking and branded certificates for audits": [
        "The hard part of compliance training is not delivering the course, it is proving it: "
        "who completed what, when, and how long they actually spent on it.",

        "Compliance training is easy to deliver and hard to evidence. When a client or a "
        "regulator asks who completed what, the answer usually comes from a spreadsheet that is "
        "three weeks out of date.",

        "Running safety and compliance training for staff or client companies usually means "
        "chasing spreadsheets to find out who has actually finished — right before an audit.",
    ],
    "White-label alternative: signed private playback + per-viewer watermark to protect paid content": [
        "Selling recorded training means trusting every buyer not to reshare it. On a generic "
        "platform, one screen recording can undo months of work.",

        "If your paid content sits on a generic platform, it is one screen recording away from "
        "being resold — and your students watch it under someone else's logo.",
    ],
    "Branded e-learning portal with admin analytics and category certificates": [
        "Training providers rarely get a clear picture of what happens after a video is sent: "
        "who watched, how far, how long — and what it produced.",

        "Once a course leaves your hands, visibility usually stops. That makes it hard to prove "
        "value to a client, or to improve the next cohort.",
    ],
}

SOLUTION = {
    "Replace WhatsApp/Drive video sharing: private courses, progress tracking, auto certificates (EN/AR RTL UI)":
        "EduFormation replaces that with a private learning portal under your own brand: videos "
        "stored privately and streamed over short-lived signed links, progress and watch time "
        "tracked per learner automatically, and certificates issued the moment someone completes "
        "a category — each with a unique certificate code. The interface runs in English, French "
        "and Arabic with full right-to-left layout.",

    "Self-paced video lessons per level, EN/AR interface, level-completion certificates":
        "EduFormation gives a language school its own self-paced video classroom: lessons "
        "organised by level and category, students resuming exactly where they stopped, a "
        "personal dashboard with completion percentage and total time spent, and level-completion "
        "certificates with a unique code issued automatically. Arabic (RTL), English and French, "
        "on desktop and mobile.",

    "Staff/client compliance training portal: completion tracking and branded certificates for audits":
        "EduFormation turns that into a compliance portal under your own brand: completed modules, "
        "progress percentage, watch time and last activity for every learner in one admin view, "
        "plus certificate templates carrying your issuer name, signature and accent colour. "
        "Completion records are ready to hand over when someone asks.",

    "White-label alternative: signed private playback + per-viewer watermark to protect paid content":
        "EduFormation is the white-label alternative: private storage with short-lived signed "
        "playback links, a per-viewer forensic watermark over every stream, and active deterrents "
        "— download, right-click, drag and copy, printing, picture-in-picture, casting and "
        "browser screen sharing are blocked, and playback pauses and is covered when a capture "
        "attempt is detected. A DRM-ready architecture sits underneath if you want the strongest "
        "protection later.",

    "Branded e-learning portal with admin analytics and category certificates":
        "EduFormation gives you a branded e-learning portal with real analytics: total learners, "
        "videos, categories, completions and watch hours, plus each learner's completed modules, "
        "progress percentage and last activity. Certificates are issued automatically per "
        "category, and the whole portal runs in your branding, in light or dark mode.",
}

BULLETS = {
    "Replace WhatsApp/Drive video sharing: private courses, progress tracking, auto certificates (EN/AR RTL UI)": [
        "Private video storage, streamed over short-lived signed links — nothing to forward",
        "Learners resume each video exactly where they stopped",
        "Progress, completed modules and watch time tracked per learner",
        "Certificates with a unique code issued automatically per category",
        "Your branding, in English, French and Arabic (RTL), on mobile and dark mode",
    ],
    "Self-paced video lessons per level, EN/AR interface, level-completion certificates": [
        "Lessons organised by level, category and tags, and searchable",
        "Students continue from their last position, on any device",
        "Personal dashboard: completion percentage, completed videos, total time spent",
        "Notes pinned to a specific video and timestamp",
        "Level-completion certificates with a unique code, issued automatically",
    ],
    "Staff/client compliance training portal: completion tracking and branded certificates for audits": [
        "Completed modules, progress percentage and watch time per learner, in one admin view",
        "Last activity tracked, so nothing sits half-finished unnoticed",
        "Certificate templates: your issuer name, signature and accent colour",
        "Separate admin and learner accounts, so each client company sees only its own people",
        "Uploads go straight to cloud storage, so file size is never the limit",
    ],
    "White-label alternative: signed private playback + per-viewer watermark to protect paid content": [
        "Private storage with short-lived signed playback links — no permanent public URLs",
        "A per-viewer forensic watermark rendered over the video",
        "Download, right-click, drag and copy, print, picture-in-picture and casting blocked",
        "Playback pauses and is covered when screen sharing or capture is detected",
        "DRM-ready architecture available for maximum protection",
    ],
    "Branded e-learning portal with admin analytics and category certificates": [
        "Totals at a glance: learners, videos, categories, completions, watch hours",
        "Per-learner drill-down: modules completed, progress, watch time, last activity",
        "Categories and learning paths that you define yourself",
        "Certificates issued automatically per category, with your branding",
        "Light and dark mode, desktop and mobile",
    ],
}

# Short subject tail per angle.
HOOKS = {
    "Replace WhatsApp/Drive video sharing: private courses, progress tracking, auto certificates (EN/AR RTL UI)":
        ["private courses without WhatsApp or Drive",
         "a private portal for your in-house courses",
         "tracking who actually finishes your courses"],
    "Self-paced video lessons per level, EN/AR interface, level-completion certificates":
        ["self-paced lessons and level certificates",
         "the lessons students actually finish",
         "between-class learning that gets tracked"],
    "Staff/client compliance training portal: completion tracking and branded certificates for audits":
        ["completion records that hold up in an audit",
         "proof of who completed the training",
         "compliance records without the spreadsheet"],
    "White-label alternative: signed private playback + per-viewer watermark to protect paid content":
        ["video that cannot be screen-recorded away",
         "protecting your paid content",
         "your courses, under your own brand"],
    "Branded e-learning portal with admin analytics and category certificates":
        ["a training portal you actually own",
         "seeing what happens after the video is sent",
         "analytics for your recorded courses"],
}

# ============================================================ variant pools
GREETINGS = [
    "Hello {org} team,",
    "Hi {org} team,",
    "Hello {org},",
    "Good morning {org} team,",
    "Hello,",
]

OPENERS = [
    "I came across {org} while mapping {seg} around {where}{proof}.",
    "{org} came up while I was looking at {seg} in {where}{proof}.",
    "I was going through {seg} in {where} and {org} stood out{proof2}.",
    "While mapping {seg} across {where}, {org} was one of the names that kept coming up{proof2}.",
    "I found {org} while researching {seg} in {where}{proof}.",
]

TRANSITIONS = [
    "Here is the short version.",
    "That is the part I would like to fix.",
    "There is a simpler way to run it.",
    "This is the problem I work on.",
]

BULLET_INTROS = [
    "In practice that means:",
    "Concretely:",
    "What that looks like:",
    "A few specifics:",
    "The detail, briefly:",
]

CTAS = [
    "Worth 15 minutes this week? Reply to this email and I will show you your own courses running inside it.",
    "Can I show you this on your own content? Reply with a course name and I will set the demo up around it.",
    "If this is useful, reply and I will walk you through it in 15 minutes, using your own material.",
    "Shall I show you? A short reply is enough and I will send a walkthrough recorded with a training centre like yours.",
    "Happy to show you the platform on your own courses — just reply and we will pick a time.",
]

DEMO_LINES = [
    "You can also look at the live demo first: {demo}",
    "The live demo is here if you prefer to look before talking: {demo}",
]

SIGNOFFS = ["Best regards,", "Kind regards,", "Best,", "Regards,"]

FOOTER = ("You are receiving this one-off email because {org} is publicly listed as a training "
          "provider in {country}. If you would prefer not to hear from me again, reply with "
          "\"stop\" and I will remove you and confirm.")

ARABIC_BLOCK = (
    "منصّة EduFormation تمنحكم بوابة تدريب خاصة بعلامتكم: فيديوهات محمية بروابط موقّعة قصيرة الأجل، "
    "ومتابعة تلقائية لتقدّم المتدرّبين ووقت المشاهدة، وشهادات تُصدر تلقائياً برمز فريد. "
    "الواجهة بالعربية (RTL) والفرنسية والإنجليزية."
)

SEG_PLURAL = {
    "training centre": "training centres",
    "language school": "language schools",
    "corporate / certification": "corporate training providers",
    "online / tech academy": "online academies",
    "public institution": "public training institutions",
}


# ================================================================ helpers
def _clean(v):
    return (v or "").strip()


def _num(s):
    try:
        return int(str(s or "").replace(",", "").strip() or 0)
    except ValueError:
        return 0


def _pick(pool, seed, salt=0):
    """Deterministic choice, so the same lead always renders the same email."""
    return pool[(seed * 31 + salt * 17 + 7) % len(pool)]


def _seed(lead):
    """Stable per-recipient seed from the email address."""
    key = (_clean(lead.get("email")) or _clean(lead.get("organisation"))).lower()
    h = 0
    for ch in key:
        h = (h * 131 + ord(ch)) % 1_000_003
    return h


def _bullets_text(bullets):
    return "\n".join(f"  -  {b}" for b in bullets)


def lint(subject, body):
    """Cheap pre-flight check: the things that actually move spam scores."""
    issues = []
    links = len(re.findall(r"https?://\S+", body))
    if links == 0:
        issues.append(("info", "No link in the body — lowest spam risk, but no instant demo either."))
    if links > 2:
        issues.append(("warn", f"{links} links in the body. Keep it to 1–2."))
    spam_words = ["free", "guarantee", "risk-free", "act now", "limited time", "click here",
                  "buy now", "cheap", "discount", "offer", "urgent", "winner", "cash",
                  "100%", "no obligation", "special promotion"]
    low = body.lower()
    hits = sorted({w for w in spam_words if w in low})
    if hits:
        issues.append(("warn", "Spam-trigger words present: " + ", ".join(hits)))
    caps = re.findall(r"\b[A-Z]{4,}\b", body)
    if caps:
        issues.append(("info", "All-caps words: " + ", ".join(sorted(set(caps))[:5])))
    if "!" in subject:
        issues.append(("warn", "Exclamation mark in the subject."))
    if len(subject) > 78:
        issues.append(("info", f"Subject is {len(subject)} characters — under 60 reads best on mobile."))
    if re.search(r"!{2,}|\?{2,}", body):
        issues.append(("warn", "Repeated ! or ? in the body."))
    first_line = body.strip().splitlines()[0] if body.strip() else ""
    if "http" in first_line:
        issues.append(("warn", "A link in the very first line is a classic spam signal."))
    if "unsubscribe" not in low and "stop" not in low:
        issues.append(("warn", "No opt-out sentence in the footer."))
    if re.search(r"\b(attached|attachment|invoice|payment|wire|transfer)\b", low):
        issues.append(("warn", "Attachment/payment vocabulary invites filters."))
    if not issues:
        issues.append(("ok", "No spam triggers found — clean plain-text message."))
    return [{"level": lv, "msg": m} for lv, m in issues]


def render(lead, cfg=None, variant_offset=0):
    """lead -> (subject, body). Plain text, unique per recipient."""
    cfg = dict(CONFIG if cfg is None else cfg)
    org = _clean(lead.get("organisation")) or "your team"
    city = _clean(lead.get("city"))
    country = _clean(lead.get("country"))
    reviews, rating = _clean(lead.get("reviews")), _clean(lead.get("rating"))
    angle = _clean(lead.get("pitch_angle")) or next(iter(PAIN))
    if angle not in PAIN:                      # tolerate an unknown angle string
        angle = next(iter(PAIN))

    seed = _seed(lead) + variant_offset * 977
    greeting = _pick(GREETINGS, seed, 1).format(org=org)
    seg_txt = SEG_PLURAL.get(_clean(lead.get("segment")).lower(),
                             _clean(lead.get("segment")) or "training providers")
    where = f"{city}, {country}" if city and country else (city or country or "the Gulf")

    n = _num(reviews)
    if n >= 1000:
        proof = f" — the {reviews} Google reviews are not an accident"
        proof2 = f" — partly on the strength of {reviews} Google reviews"
    elif n >= 100 and rating:
        proof = f" — {reviews} reviews at {rating} stars is a reputation that was earned"
        proof2 = f", largely because of {reviews} reviews at {rating} stars"
    elif rating:
        proof = f" — a {rating}-star record on Google says something about the standard"
        proof2 = f", with a {rating}-star Google record behind it"
    else:
        proof = proof2 = ""

    parts = [_pick(OPENERS, seed, 2).format(org=org, seg=seg_txt, where=where,
                                            proof=proof, proof2=proof2)]
    parts.append(_pick(PAIN[angle], seed, 3))
    parts.append(SOLUTION[angle])

    bullets = BULLETS.get(angle, [])
    if bullets:
        parts.append(_pick(BULLET_INTROS, seed, 4) + "\n" + _bullets_text(bullets))

    parts.append("We set the portal up under your own brand, migrate the videos you already "
                 "have, and have it running in about a week.")

    if cfg.get("bilingual"):
        parts.append(ARABIC_BLOCK)

    cta = _pick(CTAS, seed, 5)
    demo = _clean(cfg.get("demo_link")) or _clean(cfg.get("website"))
    booking = _clean(cfg.get("calendar_link"))
    if booking:
        cta += f" Or take a slot directly: {booking}"
    if demo:
        cta += "\n" + _pick(DEMO_LINES, seed, 6).format(demo=demo)
    parts.append(cta)

    sign = [_pick(SIGNOFFS, seed, 7), _clean(cfg.get("sender_name"))]
    role = ", ".join(x for x in (_clean(cfg.get("sender_title")),
                                 _clean(cfg.get("company_name"))) if x)
    if role:
        sign.append(role)
    contact = "  ·  ".join(x for x in (
        f"WhatsApp {_clean(cfg.get('whatsapp'))}" if cfg.get("whatsapp") else "",
        _clean(cfg.get("from_email"))) if x)
    if contact:
        sign.append(contact)

    body = greeting + "\n\n" + "\n\n".join(parts) + "\n\n" + "\n".join(sign)
    body += "\n\n" + FOOTER.format(org=org, country=country or "the Gulf")
    footer_co = " · ".join(x for x in (_clean(cfg.get("company_name")),
                                       _clean(cfg.get("postal_address"))) if x)
    if footer_co:
        body += "\n" + footer_co

    hook = _pick(HOOKS.get(angle, ["a quick idea for your courses"]), seed, 8)
    pattern = (cfg.get("subject_patterns") or CONFIG["subject_patterns"])
    subject = _pick(pattern, seed, 9).format(org=org, hook=hook, city=city,
                                            country=country, segment=seg_txt)
    return subject, body


if __name__ == "__main__":
    import csv, sys
    path = sys.argv[2] if len(sys.argv) > 2 else "leads_sendlist.csv"
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    lead = rows[int(sys.argv[1])] if len(sys.argv) > 1 else rows[0]
    s, b = render(lead)
    print("TO     :", lead["email"])
    print("SUBJECT:", s)
    print("-" * 72)
    print(b)
    print("-" * 72)
    for c in lint(s, b):
        print(f"  [{c['level']}] {c['msg']}")
