"""
csv_import.py — turns any lead CSV into the shape this kit sends from.

Used by both the dashboard (Upload CSV button / drag-drop) and the CLI, so a
list you export next month works without touching any code.

Handles: any column names (fuzzy-matched), missing columns, no pitch-angle
column, Excel/BOM/newline mess, duplicate and invalid emails.
"""

import csv, io, re

# ---------------------------------------------------------------- columns --
FIELD_SYNONYMS = {
    "n":            ["#", "no", "no.", "num", "n", "id", "index", "row"],
    "organisation": ["organisation", "organization", "org", "company", "company name",
                     "business", "name", "academy", "school", "client", "account"],
    "segment":      ["segment", "category", "type", "industry", "sector", "kind", "niche"],
    "country":      ["country", "nation", "market"],
    "city":         ["city", "town", "location", "area", "emirate"],
    "phone":        ["phone", "phone number", "tel", "telephone", "mobile", "whatsapp",
                     "contact number", "number"],
    "email":        ["email", "e-mail", "email address", "mail", "contact email",
                     "email id", "e mail"],
    "website":      ["website", "web", "url", "site", "domain", "homepage"],
    "instagram":    ["instagram", "insta", "ig", "instagram handle", "social"],
    "rating":       ["google rating", "rating", "stars", "google stars", "score", "google maps rating"],
    "reviews":      ["reviews", "review", "review count", "reviews count", "google reviews",
                     "num reviews", "ratings"],
    "priority":     ["priority", "tier", "rank", "score priority", "lead priority"],
    "pitch_angle":  ["pitch angle", "pitch", "angle", "hook", "needs", "pain point",
                     "opportunity", "remarks"],
    "status":       ["status", "stage", "state", "progress"],
    "notes":        ["notes", "extra notes", "internal notes", "description", "details"],
}
FIELD_ORDER = ["n", "organisation", "segment", "country", "city", "phone", "email",
               "website", "instagram", "rating", "reviews", "priority",
               "archetype", "pitch_angle", "status", "notes"]

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")

# ------------------------------------------------------- angle inference ---
# Keywords from a lead's own row -> the pitch angle that fits it.
ANGLE_RULES = [
    ("D", ["protect", "protection", "watermark", "drm", "piracy", "white-label", "white label",
           "signed", "premium content", "screen record", "resell", "leak", "own the platform"]),
    ("C", ["compliance", "audit", "certification", "certificate for audit", "ohs", "hse", "safety",
           "iso", "staff training", "onboarding", "corporate training", "compliance training"]),
    ("B", ["language", "english", "arabic", "french", "spanish", "ielts", "toefl", "level",
           "self-paced", "self paced", "per level", "conversation", "quran", "tutoring"]),
    ("E", ["analytics", "reporting", "lms", "e-learning", "elearning", "online academy",
           "digital course", "dashboard"]),
    ("A", ["whatsapp", "drive", "video", "course", "training centre", "training center",
           "academy", "institute", "private course", "portal"]),
]


def _norm(s):
    return re.sub(r"[\s_\-]+", " ", (s or "").strip().lower())


def detect_columns(headers):
    """headers -> {standard field: original header}. Fuzzy, order-aware."""
    out, used = {}, set()
    normed = [(_norm(h), h) for h in headers]
    for field, names in FIELD_SYNONYMS.items():
        for want in names:
            hit = next((h for nh, h in normed if nh == want and h not in used), None)
            if not hit:
                hit = next((h for nh, h in normed
                            if h not in used and (nh.startswith(want) or want in nh)), None)
            if hit:
                out[field] = hit
                used.add(hit)
                break
    return out


def infer_angle(row, extra=""):
    """Pick the pitch angle that matches this row's own words.

    Looks at segment / priority / status / notes / organisation plus any extra
    text (a pasted pitch or a free-text needs column).
    """
    blob = " ".join(_norm(row.get(k, "")) for k in
                    ("segment", "pitch_angle", "priority", "status", "notes", "organisation"))
    blob += " " + _norm(extra)
    for code, words in ANGLE_RULES:
        if any(w in blob for w in words):
            return code
    return "A"


def parse_csv_text(text, filename=""):
    """CSV text -> (rows, report). rows use the standard field names."""
    text = text.replace("\x00", "")
    if text.startswith("\ufeff"):
        text = text[1:]
    try:
        dialect = csv.Sniffer().sniff(text[:4000], delimiters=",;\t|")
        delim = dialect.delimiter
    except Exception:
        delim = "," if text.count(",") >= text.count(";") else ";"
    reader = csv.DictReader(io.StringIO(text), delimiter=delim)
    headers = [h for h in (reader.fieldnames or []) if h is not None]
    cmap = detect_columns(headers)

    report = {"filename": filename, "delimiter": delim, "detected": cmap,
              "headers": headers, "unmapped": [h for h in headers if h not in cmap.values()]}

    raw = list(reader)
    rows, seen_emails, bad_emails, dups, inferred = [], {}, [], 0, 0

    for i, r in enumerate(raw, 1):
        row = {}
        for field in FIELD_ORDER:
            src = cmap.get(field)
            row[field] = (r.get(src) or "").strip() if src else ""
        if not row["organisation"] and not row["email"]:
            continue
        try:
            row["n"] = str(int(float(row["n"]))) if row["n"] else str(i)
        except ValueError:
            row["n"] = str(i)
        if not row["segment"]:
            row["segment"] = "Training centre"

        # angle: keep the sheet's own, otherwise infer from the row
        if row["pitch_angle"]:
            code = angle_code(row["pitch_angle"])
        else:
            code = infer_angle(row, extra=row.get("notes", "")) or "A"
            row["pitch_angle"] = canonical_angle(code)
            inferred += 1
        row["archetype"] = code or "A"

        email = row["email"].replace(" ", "").lower()
        row["email"] = email
        if email:
            if not EMAIL_RE.match(email):
                bad_emails.append(email)
                row["email"] = ""
            elif email in seen_emails:
                dups += 1
        row["reviews"] = re.sub(r"[^\d,]", "", row["reviews"])
        row["rating"] = re.sub(r"[^\d.]", "", row["rating"])
        m = re.search(r"(High|Medium|Low)", row["priority"], re.I)
        row["priority"] = m.group(1).title() if m else row["priority"]

        rows.append(row)
        if email and EMAIL_RE.match(email):
            seen_emails.setdefault(email, row["n"])

    # drop duplicate emails, keep the best (highest priority, then most reviews)
    rank = {"High": 0, "Medium": 1, "Low": 2, "": 3}
    kept = {}
    for row in rows:
        e = row["email"]
        if not e:
            kept.setdefault(f"__nonemail_{row['n']}", row)
            continue
        cur = kept.get(e)
        if cur is None:
            kept[e] = row
        else:
            better = (rank.get(row["priority"], 3), -int((row["reviews"] or "0").replace(",", "") or 0))
            worse = (rank.get(cur["priority"], 3), -int((cur["reviews"] or "0").replace(",", "") or 0))
            if better < worse:
                kept[e] = row
    rows = list(kept.values())
    rows.sort(key=lambda r: int(r["n"]) if r["n"].isdigit() else 0)

    report.update({"rows": len(rows), "emailable": len(seen_emails), "duplicates_merged": dups,
                   "invalid_emails": bad_emails, "angles_inferred": inferred})
    return rows, report


# --------------------------------------------------------------- angles ----
CANON = {
    "A": "Replace WhatsApp/Drive video sharing: private courses, progress tracking, auto certificates (EN/AR RTL UI)",
    "B": "Self-paced video lessons per level, EN/AR interface, level-completion certificates",
    "C": "Staff/client compliance training portal: completion tracking and branded certificates for audits",
    "D": "White-label alternative: signed private playback + per-viewer watermark to protect paid content",
    "E": "Branded e-learning portal with admin analytics and category certificates",
}


def angle_code(pitch):
    p = _norm(pitch)
    if not p:
        return None
    if "whatsapp" in p or "auto certificate" in p or "rtl ui" in p:
        return "A"
    if "self-paced" in p or "level-" in p or "level " in p or "level-completion" in p:
        return "B"
    if "compliance" in p or "audit" in p:
        return "C"
    if "watermark" in p or "white-label" in p or "signed private" in p:
        return "D"
    if "e-learning portal" in p or "admin analytics" in p or "analytics" in p:
        return "E"
    # fall back to keyword inference rather than guessing blindly
    return infer_angle({}, extra=pitch) or "A"


def canonical_angle(code):
    return CANON.get(code, CANON["A"])


def to_csv(rows, path):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELD_ORDER, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
