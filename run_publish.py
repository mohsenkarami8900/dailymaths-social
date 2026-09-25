"""
Daily publisher for Instagram + Facebook.

Steps (called one by one from .github/workflows/publish.yml):
  python run_publish.py plan      decide what to post today  -> GITHUB_OUTPUT go/kinds
  python run_publish.py build     render media into site/    -> build.json
  python run_publish.py wait      sleep until 16:00 UK time (scheduled runs only)
  python run_publish.py publish   post to Instagram/Facebook (or preview to Telegram)

Schedule (UK time, 16:00):
  every day      story (video)
  Mon/Wed/Fri    carousel (5 puzzles + answers)
  Tue/Thu/Sat    reel (countdown video)
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
POST_HOUR = 16
WINDOW_MIN = 40

CAROUSEL_DAYS = {0, 2, 4}   # Mon, Wed, Fri
REEL_DAYS = {1, 3, 5}       # Tue, Thu, Sat


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
    today = now.date().isoformat()
    state = load(STATE, {"done": {}})
    if manual():
        kinds = os.environ.get("KINDS", "story").replace(" ", "")
        if kinds == "auto":
            kinds = ",".join(todays_kinds(now))
        return out(go="true", kinds=kinds, day=today)
    target = now.replace(hour=POST_HOUR, minute=0, second=0, microsecond=0)
    if now < target and (target - now).total_seconds() > WINDOW_MIN * 60:
        print("Too early; the other scheduled run will post.")
        return out(go="false")
    kinds = [k for k in todays_kinds(now) if state["done"].get(k) != today]
    if not kinds:
        print("Already posted today.")
        return out(go="false")
    out(go="true", kinds=",".join(kinds), day=today)


def todays_kinds(now):
    k = ["story"]
    if now.weekday() in CAROUSEL_DAYS:
        k.append("carousel")
    if now.weekday() in REEL_DAYS:
        k.append("reel")
    return k


def wait():
    if manual():
        return
    now = datetime.now(TZ)
    target = now.replace(hour=POST_HOUR, minute=0, second=0, microsecond=0)
    if now < target:
        s = (target - now).total_seconds()
        print(f"Waiting {s/60:.1f} min until {POST_HOUR}:00 UK time…")
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
    if "story" in items:
        try:
            mid = M.ig_story_video(base + items["story"]["file"])
            print("IG story:", mid)
            state["done"]["story"] = b["day"]
        except Exception as e:
            errors.append(f"Story: {e}")

    if "reel" in items:
        r = items["reel"]
        q = r["q"]
        key = {"letter": q["letter"], "accept": q["accept"], "wrong": q["wrong"]}
        try:
            mid = M.ig_reel(base + r["file"], r["caption"])
            posts.append({"platform": "ig", "kind": "reel", "id": mid, "time": now, **key})
            print("IG reel:", mid)
            state["done"]["reel"] = b["day"]
        except Exception as e:
            errors.append(f"Reel (Instagram): {e}")
        try:
            vid = M.fb_video(base + r["file"], r["caption"])
            posts.append({"platform": "fb", "kind": "reel", "id": vid, "time": now, **key})
            print("FB video:", vid)
        except Exception as e:
            errors.append(f"Reel (Facebook): {e}")

    if "carousel" in items:
        c = items["carousel"]
        urls = [base + f for f in c["files"]]
        key = {"accepts": [p["accept"] for _, p in c["puzzles"]]}
        try:
            mid = M.ig_carousel(urls, c["caption"])
            posts.append({"platform": "ig", "kind": "carousel", "id": mid, "time": now, **key})
            print("IG carousel:", mid)
            state["done"]["carousel"] = b["day"]
            state["recent_gens"] = (state.get("recent_gens", []) + c["used"])[-15:]
        except Exception as e:
            errors.append(f"Carousel (Instagram): {e}")
        try:
            pid = M.fb_photos_post(urls, c["caption"])
            posts.append({"platform": "fb", "kind": "carousel", "id": pid, "time": now, **key})
            print("FB post:", pid)
        except Exception as e:
            errors.append(f"Carousel (Facebook): {e}")

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
