"""Small helpers for the Meta Graph API (Instagram + Facebook Page) and Telegram alerts."""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

GRAPH = "https://graph.facebook.com/v26.0"
TOKEN = os.environ.get("META_PAGE_TOKEN", "").strip()
PAGE_ID = os.environ.get("FB_PAGE_ID", "1335276076335713")
IG_ID = os.environ.get("IG_USER_ID", "17841417559276103")
IG_USERNAME = "dailymathsuk"


class MetaError(Exception):
    pass


def api(method, path, **params):
    params["access_token"] = TOKEN
    url = f"{GRAPH}/{path.lstrip('/')}"
    data = None
    if method == "GET":
        url += "?" + urllib.parse.urlencode(params)
    else:
        data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data, method=method)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")
            if e.code >= 500 and attempt < 2:
                time.sleep(5 * (attempt + 1))
                continue
            raise MetaError(f"{method} {path} → HTTP {e.code}: {body[:500]}")
        except urllib.error.URLError as e:
            if attempt < 2:
                time.sleep(5)
                continue
            raise MetaError(f"{method} {path} → {e}")


# ------------------------------------------------------------ Instagram --

def _wait_container(cid, timeout=600):
    t0 = time.time()
    while time.time() - t0 < timeout:
        st = api("GET", cid, fields="status_code,status")
        code = st.get("status_code")
        if code == "FINISHED":
            return
        if code in ("ERROR", "EXPIRED"):
            raise MetaError(f"Container {cid} failed: {st}")
        time.sleep(8)
    raise MetaError(f"Container {cid} not ready after {timeout}s")


def _publish(cid):
    _wait_container(cid)
    return api("POST", f"{IG_ID}/media_publish", creation_id=cid)["id"]


def ig_story_video(video_url):
    cid = api("POST", f"{IG_ID}/media", media_type="STORIES", video_url=video_url)["id"]
    return _publish(cid)


def ig_reel(video_url, caption):
    cid = api("POST", f"{IG_ID}/media", media_type="REELS", video_url=video_url,
              caption=caption, share_to_feed="true")["id"]
    return _publish(cid)


def ig_carousel(image_urls, caption):
    children = []
    for u in image_urls:
        c = api("POST", f"{IG_ID}/media", image_url=u, is_carousel_item="true")["id"]
        _wait_container(c)
        children.append(c)
    cid = api("POST", f"{IG_ID}/media", media_type="CAROUSEL", children=",".join(children),
              caption=caption)["id"]
    return _publish(cid)


def ig_comments(media_id):
    res = api("GET", f"{media_id}/comments", fields="id,text,username,timestamp", limit=50)
    return res.get("data", [])


def ig_reply(comment_id, message):
    return api("POST", f"{comment_id}/replies", message=message)


def ig_like(comment_id):
    """Like a comment (needs instagram_manage_engagement). Best effort."""
    return api("POST", f"{IG_ID}/likes", comment_id=comment_id)


# ------------------------------------------------------------- Facebook --

def fb_photos_post(image_urls, message):
    ids = [api("POST", f"{PAGE_ID}/photos", url=u, published="false")["id"] for u in image_urls]
    params = {"message": message}
    for i, pid in enumerate(ids):
        params[f"attached_media[{i}]"] = json.dumps({"media_fbid": pid})
    return api("POST", f"{PAGE_ID}/feed", **params)["id"]


def fb_video(video_url, description):
    return api("POST", f"{PAGE_ID}/videos", file_url=video_url, description=description)["id"]


def fb_comments(obj_id):
    res = api("GET", f"{obj_id}/comments", fields="id,message,from,created_time", filter="toplevel", limit=50)
    return res.get("data", [])


def fb_reply(comment_id, message):
    return api("POST", f"{comment_id}/comments", message=message)


def fb_like(comment_id):
    return api("POST", f"{comment_id}/likes")


# ----------------------------------------------------------------- token --

def token_info():
    return api("GET", "debug_token", input_token=TOKEN).get("data", {})


# -------------------------------------------------------------- telegram --

def telegram(text=None, photo=None, video=None, media_group=None):
    tok = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_ALERT_CHAT_ID", "").strip()
    if not tok or not chat:
        print("(telegram not configured)", text)
        return
    if media_group:
        method, params = "sendMediaGroup", {"media": json.dumps(media_group)}
    elif video:
        method, params = "sendVideo", {"video": video, "caption": (text or "")[:1000]}
    elif photo:
        method, params = "sendPhoto", {"photo": photo, "caption": (text or "")[:1000]}
    else:
        method, params = "sendMessage", {"text": text[:4000]}
    params["chat_id"] = chat
    try:
        urllib.request.urlopen(f"https://api.telegram.org/bot{tok}/{method}",
                               data=urllib.parse.urlencode(params).encode(), timeout=60)
    except Exception as e:
        print("Telegram error:", e)
