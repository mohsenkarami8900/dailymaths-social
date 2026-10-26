"""
Daily publisher for Instagram + Facebook.

Steps (called one by one from .github/workflows/publish.yml):
  python run_publish.py plan      decide what to post today  -> GITHUB_OUTPUT go/kinds
  python run_publish.py build     render media into site/    -> build.json
  python run_publish.py wait      sleep until the posting time (scheduled runs only)
  python run_publish.py publish   post to Instagram/Facebook (or preview to Telegram)

Schedule (UK time): Thursday 18:00 and Saturday 05:00, each time
  story (video) + reel (countdown video) + carousel (5 puzzles + answers)

GitHub sometimes starts scheduled runs hours late, so the workflow runs every
10 minutes in the hour after each slot; the FIRST run after the slot time posts
(a late run may still post up to LATE_HOURS later) and data/state.json stops
any second post. If nothing went out ALERT_AFTER_MIN after the slot, the admin
gets one Telegram alert with a link to run the workflow by hand.
"""

import json
import os
import random
import sys
import time
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
SITE = ROOT / "site"
STATE = DATA / "state.json"
POSTS = DATA / "posts.json"
BUILD = ROOT / "build.json"
TZ = ZoneInfo("Europe/London")
POST_SLOTS = {3: 18, 5: 5}       # Thursday 18:00, Saturday 05:00 (UK time)
LATE_HOURS = 5                   # a late GitHub run may still post up to 5 h after the slot
ALERT_AFTER_MIN = 40             # alert the admin if nothing was posted 40 min after the slot
ALL_KINDS = ["story", "reel", "carousel"]
WORKFLOW_URL = "https://github.com/mohsenkarami8900/dailymaths-social/actions/workflows/publish.yml"


def load(p, default):
    try:
        return json.loads(p.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=1, ensure_ascii=False) + "\n")


def out(**kw):
    f = os.environ.get("GITHUB_OUTPUT")
    for k, v in kw.items():
        print(f"{k}={v}")
        if f:
            with open(f, "a") as fh:
                fh.write(f"{k}={v}\n")


def manual():
    return os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"


def dry_run():
    return os.environ.get("DRY_RUN", "").lower() == "true"


# ------------------------------------------------------------------ plan --

def plan():
    now = datetime.now(TZ)
    go = False
    try:
        go = _plan(now)
    finally:
        if not go:                   # this run won't post: tell the admin if today was missed
            alert_if_missed()


def _plan(now):
    today = now.date().isoformat()
    state = load(STATE, {"done": {}})
    if manual():
        kinds = os.environ.get("KINDS", "auto").replace(" ", "")
        if kinds == "auto":          # the "Run workflow" button: post whatever is still missing today
            kinds = ",".join(k for k in ALL_KINDS if state["done"].get(k) != today)
        if not kinds:
            print("Everything was already posted today.")
            return out(go="false")
        out(go="true", kinds=kinds, day=today)
        return True
    pending = [k for k in todays_kinds(now) if state["done"].get(k) != today]
    if not pending:
        print("Nothing left to post today.")
        return out(go="false")
    target = target_time(now, pending[0])
    if now < target:
        print("Too early; a later scheduled run will post:", ", ".join(pending))
        return out(go="false")
    if now >= target + timedelta(hours=LATE_HOURS):
        print("Too late to post today:", ", ".join(pending))
        return out(go="false")
    out(go="true", kinds=",".join(pending), day=today)
    return True


def alert_if_missed():
    """Send the admin ONE Telegram alert a day if today's slot has not been posted."""
    if dry_run():
        return
    now = datetime.now(TZ)
    if now.weekday() not in POST_SLOTS:
        return
    today = now.date().isoformat()
    state = load(STATE, {"done": {}})
    missing = [k for k in ALL_KINDS if state["done"].get(k) != today]
    if not missing or state.get("alerted") == today:
        return
    if now < target_time(now, "story") + timedelta(minutes=ALERT_AFTER_MIN):
        return
    try:
        import meta as M
        M.telegram(f"⚠️ Daily Maths UK: today's Instagram/Facebook posts have NOT gone out yet "
                   f"({now:%A %H:%M} UK time). Missing: {', '.join(missing)}.\n\n"
                   f"Open this page and press the green “Run workflow” button "
                   f"(no need to change anything):\n{WORKFLOW_URL}")
        state["alerted"] = today
        save(STATE, state)
        print("Alert sent to the admin.")
    except Exception as e:
        print("Alert failed:", e)


def target_time(now, kind):
    return now.replace(hour=POST_SLOTS.get(now.weekday(), 0), minute=0, second=0, microsecond=0)


def todays_kinds(now):
    return ["story", "reel", "carousel"] if now.weekday() in POST_SLOTS else []


def wait():
    if manual():
        return
    now = datetime.now(TZ)
    kinds = list(load(BUILD, {"items": {}})["items"]) or ["story"]
    target = max(target_time(now, k) for k in kinds)
    if now < target:
        s = (target - now).total_seconds()
        print(f"Waiting {s/60:.1f} min until {target:%H:%M} UK time…")
        time.sleep(s)


# ----------------------------------------------------------------- build --

def build():
    import content as C
    from render import render_carousel, render_story

    kinds = os.environ["KINDS"].split(",")
    day = os.environ.get("DAY") or datetime.now(TZ).date().isoformat()
    state = load(STATE, {"done": {}})
    media = SITE / "media" / day
    media.mkdir(parents=True, exist_ok=True)
    (SITE / "index.html").write_text(
        '<meta http-equiv="refresh" content="0; url=https://dailymathsuk.com/">')
    b = {"day": day, "items": {}}
    stamp = datetime.now(TZ).strftime("%H%M%S")

    if "story" in kinds:
        rng = random.Random(f"story-{day}")
        q = C.story_question(rng)
        f = media / f"story-{stamp}.mp4"
        render_story(q, f, seed=hash(day) % 1000)
        b["items"]["story"] = {"file": str(f.relative_to(SITE)), "q": q}

    if "reel" in kinds:
        rng = random.Random(f"reel-{day}")
        q = C.story_question(rng)
        f = media / f"reel-{stamp}.mp4"
        render_story(q, f, seed=hash(day) % 1000 + 1)
        b["items"]["reel"] = {"file": str(f.relative_to(SITE)), "q": q, "caption": C.reel_caption(rng, q)}

    if "carousel" in kinds:
        rng = random.Random(f"carousel-{day}")
        puzzles, used = C.carousel_puzzles(rng, avoid=set(state.get("recent_gens", [])))
        files = render_carousel(puzzles, media / f"carousel-{stamp}")
        b["items"]["carousel"] = {"files": [str(p.relative_to(SITE)) for p in files],
                                  "puzzles": puzzles, "used": used, "caption": C.carousel_caption(rng)}
    save(BUILD, b)
    print(json.dumps({k: list(v) for k, v in b["items"].items()}))


# --------------------------------------------------------------- publish --

def wait_url(url, timeout=300):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                if r.status == 200:
                    return
        except Exception:
            pass
        time.sleep(10)
    raise RuntimeError(f"Media not reachable: {url}")


def publish():
    try:
        _publish()
    finally:
        alert_if_missed()


def _publish():
    import meta as M
    base = os.environ["BASE_URL"].rstrip("/") + "/"
    b = load(BUILD, None)
    state = load(STATE, {"done": {}})
    posts = load(POSTS, [])
    items = b["items"]
    errors = []

    for it in items.values():
        for f in it.get("files", [it.get("file")]):
            wait_url(base + f)

    if dry_run():
        M.telegram("🧪 Preview of today's Instagram/Facebook posts (nothing was published):")
        if "story" in items:
            M.telegram(text="Story", video=base + items["story"]["file"])
        if "reel" in items:
            M.telegram(text="Reel caption:\n\n" + items["reel"]["caption"], video=base + items["reel"]["file"])
        if "carousel" in items:
            c = items["carousel"]
            M.telegram(media_group=[{"type": "photo", "media": base + f} for f in c["files"]])
            M.telegram("Carousel caption:\n\n" + c["caption"])
        print("Dry run: sent previews to Telegram.")
        return

    now = datetime.now(TZ).isoformat()
    day = b["day"]
    done = state["done"]

    def step(kind, plat, label, fn):
        """Run one post once per day per platform. A spam block is not retried today."""
        key = f"{kind}_{plat}"
        if done.get(key) == day:
            print(f"{label}: already done today, skipping")
            return
        try:
            fn()
            done[key] = day
        except Exception as e:
            msg = str(e)
            if "2207051" in msg or "action is blocked" in msg:
                done[key] = day          # don't hammer Instagram again today
                errors.append(f"{label}: Instagram blocked this post as possible spam "
                              f"(not retried today). Details: {msg[:300]}")
            else:
                errors.append(f"{label}: {msg}")

    if "story" in items:
        def _story():
            print("IG story:", M.ig_story_video(base + items["story"]["file"]))
        step("story", "ig", "Story", _story)

    if "reel" in items:
        r = items["reel"]
        q = r["q"]
        key = {"letter": q["letter"], "accept": q["accept"], "wrong": q["wrong"]}

        def _ig_reel():
            mid = M.ig_reel(base + r["file"], r["caption"])
            posts.append({"platform": "ig", "kind": "reel", "id": mid, "time": now, **key})
            print("IG reel:", mid)

        def _fb_reel():
            vid = M.fb_video(base + r["file"], r["caption"])
            posts.append({"platform": "fb", "kind": "reel", "id": vid, "time": now, **key})
            print("FB video:", vid)
        step("reel", "ig", "Reel (Instagram)", _ig_reel)
        step("reel", "fb", "Reel (Facebook)", _fb_reel)

    if "carousel" in items:
        c = items["carousel"]
        urls = [base + f for f in c["files"]]
        key = {"accepts": [p["accept"] for _, p in c["puzzles"]]}

        def _ig_carousel():
            mid = M.ig_carousel(urls, c["caption"])
            posts.append({"platform": "ig", "kind": "carousel", "id": mid, "time": now, **key})
            print("IG carousel:", mid)
            state["recent_gens"] = (state.get("recent_gens", []) + c["used"])[-15:]

        def _fb_carousel():
            pid = M.fb_photos_post(urls, c["caption"])
            posts.append({"platform": "fb", "kind": "carousel", "id": pid, "time": now, **key})
            print("FB post:", pid)
        step("carousel", "ig", "Carousel (Instagram)", _ig_carousel)
        step("carousel", "fb", "Carousel (Facebook)", _fb_carousel)

    # a kind is finished for today when every platform for it is done (or blocked)
    for kind, plats in (("story", ["ig"]), ("reel", ["ig", "fb"]), ("carousel", ["ig", "fb"])):
        if kind in items and all(done.get(f"{kind}_{p}") == day for p in plats):
            done[kind] = day

    cutoff = (datetime.now(TZ) - timedelta(days=10)).isoformat()
    save(POSTS, [p for p in posts if p["time"] >= cutoff])
    save(STATE, state)
    check_token(M)
    if errors:
        M.telegram("⚠️ Daily Maths UK – some posts failed today:\n\n" + "\n\n".join(errors)[:3500])
        print("\n".join(errors))
        sys.exit(1)


def check_token(M):
    try:
        info = M.token_info()
    except Exception as e:
        M.telegram(f"⚠️ Could not check the Meta token: {e}")
        return
    if not info.get("is_valid", True):
        M.telegram("⚠️ The Meta token is no longer valid. Please create a new Page token (see README).")
        return
    exp = info.get("data_access_expires_at")
    if exp:
        days = (exp - time.time()) / 86400
        print(f"Token data access expires in {days:.0f} days")
        if days < 14:
            M.telegram(f"⏰ The Instagram/Facebook token needs renewing in about {days:.0f} days. "
                       "Please generate a new Page token and update META_PAGE_TOKEN in GitHub (see README).")


if __name__ == "__main__":
    {"plan": plan, "build": build, "wait": wait, "publish": publish}[sys.argv[1]]()
