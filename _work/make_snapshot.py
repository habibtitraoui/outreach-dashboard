"""dashboard_snapshot.html — the same interface with everything embedded.""" 
import json, os, sys, hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
import app

state = {"leads": [], "stats": {}, "angles": {}, "settings": app.load_settings(),
         "has_password": False, "running": False, "overrides": 0,
         "dataset": app.dataset(), "duplicate_bodies": 0,
         "has_password": False, "password_source": None, "sent_today": 0,
         "daily_cap": 35, "one_click_ready": False}
sent = app.sent_map()
for r in app.all_leads():
    state["leads"].append({
        "n": r.get("n"), "organisation": r.get("organisation"), "segment": r.get("segment"),
        "country": r.get("country"), "city": r.get("city"), "phone": r.get("phone"),
        "email": r.get("email"), "website": r.get("website"), "rating": r.get("rating"),
        "reviews": r.get("reviews"), "priority": r.get("priority"),
        "archetype": r.get("archetype"), "status": r.get("status"),
        "sendable": r.get("sendable", False), "sent": r.get("email", "").lower() in sent,
        "custom": False})
state["stats"] = {"total": len(state["leads"]),
                  "sendable": sum(1 for r in state["leads"] if r["sendable"]),
                  "no_email": sum(1 for r in state["leads"] if not r["sendable"]),
                  "sent": 0,
                  "countries": sorted({r["country"] for r in state["leads"] if r["country"]})}
for r in state["leads"]:
    a = r["archetype"] or "?"
    state["angles"].setdefault(a, {"count": 0, "angle": a})
    state["angles"][a]["count"] += 1

fps = {}
for r in state["leads"]:
    if r["sendable"]:
        fps.setdefault(hashlib.md5(app.render(r)[1].encode()).hexdigest(), []).append(r["organisation"])
state["duplicate_bodies"] = sum(1 for v in fps.values() if len(v) > 1)

previews = {}
for r in state["leads"]:
    if not r["sendable"]:
        continue
    s, b = app.render(r)
    checks = app.email_kit.lint(s, b)
    checks.append({"level": "ok", "msg": "Unique — no other lead receives this exact message."})
    previews[str(r["n"])] = {"n": str(r["n"]), "to": r["email"], "from": state["settings"]["from_email"],
                             "organisation": r["organisation"], "subject": s, "body": b,
                             "angle": r["archetype"], "custom": False, "checks": checks}

html = open("ui/index.html", encoding="utf-8").read()
inject = ("<script>window.__SNAPSHOT_DATA__ = " + json.dumps(state, ensure_ascii=False) +
          ";\nwindow.__SNAPSHOT_PREVIEWS__ = " + json.dumps(previews, ensure_ascii=False) + ";</script>\n")
open("dashboard_snapshot.html", "w", encoding="utf-8").write(html.replace("</head>", inject + "</head>", 1))
print("dashboard_snapshot.html:", round(len(html)/1024), "KB ·", len(previews), "previews ·",
      state["duplicate_bodies"], "duplicate bodies")
