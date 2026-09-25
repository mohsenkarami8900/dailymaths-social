"""
Checks new comments on recent posts and replies / likes.

- correct answer  -> like + 👏 reply
- wrong answer    -> "have another go" reply
- irrelevant      -> nothing
Comments younger than MIN_AGE minutes are left for the next run, so replies feel natural.
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import meta as M
from checker import check_carousel, check_reel

ROOT = Path(__file__).resolve().parent
POSTS = ROOT / "data" / "posts.json"
DONE = ROOT / "data" / "replied.json"
MIN_AGE = timedelta(minutes=20)
MAX_POST_AGE = timedelta(days=7)
MAX_REPLIES_PER_RUN = 40


def load(p, d):
    try:
        return json.loads(p.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return d


def parse_time(s):
    s = s.replace("Z", "+00:00")
    if len(s) > 5 and s[-5] in "+-" and s[-3] != ":":
        s = s[:-2] + ":" + s[-2:]
    return datetime.fromisoformat(s)


def main():
    posts = load(POSTS, [])
    done = set(load(DONE, []))
    now = datetime.now(timezone.utc)
    replies = 0
    errors = []

    for post in posts:
        if now - parse_time(post["time"]) > MAX_POST_AGE:
            continue
        try:
            comments = M.ig_comments(post["id"]) if post["platform"] == "ig" else M.fb_comments(post["id"])
        except Exception as e:
            errors.append(str(e))
            continue
        for c in comments:
            cid = c["id"]
            if cid in done or replies >= MAX_REPLIES_PER_RUN:
                continue
            if post["platform"] == "ig":
                text, when, own = c.get("text", ""), c.get("timestamp"), c.get("username") == M.IG_USERNAME
            else:
                text, when = c.get("message", ""), c.get("created_time")
                own = (c.get("from") or {}).get("id") == M.PAGE_ID
            if own:
                done.add(cid)
                continue
            if when and now - parse_time(when) < MIN_AGE:
                continue
            check = check_reel if post["kind"] == "reel" else check_carousel
            verdict, reply = check(text, {**post, "id": cid})
            print(f"[{post['platform']}] {text[:60]!r} -> {verdict}")
            done.add(cid)
            if verdict == "ignore":
                continue
            try:
                if verdict in ("correct", "partial", "score"):
                    try:
                        (M.ig_like if post["platform"] == "ig" else M.fb_like)(cid)
                    except Exception as e:
                        print("  like failed:", e)
                (M.ig_reply if post["platform"] == "ig" else M.fb_reply)(cid, reply)
                replies += 1
            except Exception as e:
                errors.append(str(e))

    DONE.parent.mkdir(exist_ok=True)
    DONE.write_text(json.dumps(sorted(done)[-5000:]))
    print(f"Replied to {replies} comments.")
    if errors:
        print("Errors:\n" + "\n".join(errors[:10]))
        if len(errors) > 3:
            M.telegram("⚠️ Comment bot had problems:\n" + "\n".join(errors[:5])[:3500])
            sys.exit(1)


if __name__ == "__main__":
    main()
