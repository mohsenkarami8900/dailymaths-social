"""
Decides how to respond to a comment.

check_reel(text, post)      -> ("correct"|"wrong"|"ignore", reply_text)
check_carousel(text, post)  -> ("correct"|"partial"|"wrong"|"score"|"ignore", reply_text)

"ignore" means: no reply and no like (irrelevant comment).
"""

import random
import re

from content import CORRECT, SCORE, WRONG, norm

LEVEL_ALIASES = [
    (r"ks\s*1|key\s*stage\s*1", 0), (r"ks\s*2|key\s*stage\s*2", 1), (r"ks\s*3|key\s*stage\s*3", 2),
    (r"gcse\s*f(?:oundation)?|foundation", 3), (r"gcse\s*h(?:igher)?|higher", 4),
]
LEVEL_NAMES = ["KS1", "KS2", "KS3", "GCSE Foundation", "GCSE Higher"]
VALUE = r"[£$]?-?−?\d[\d,]*(?:\.\d+)?(?:\s*/\s*\d+)?\s*(?:°|p|cm|km/h)?"


def _vals(text):
    return [norm(v.replace(" ", "")) for v in re.findall(VALUE, text)]


def _pick(options, key):
    return random.Random(key).choice(options)


# ------------------------------------------------------------------ reel --

def check_reel(text, post):
    t = text.lower().strip()
    key = post.get("id", "") + t
    letter = post["letter"].lower()
    m = (re.fullmatch(r"\(?([abc])\)?[\s!.)]*", t)
         or re.search(r"\b(?:answer|option|it'?s|its|is|go(?:ing)? (?:for|with)|pick)\s*:?\s*\(?([abc])\)?[.!]*\s*$", t)
         or re.search(r"\(([abc])\)", t) or re.search(r"^([abc])(?:[).!:]|\s*$)", t))
    if m:
        return ("correct", _pick(CORRECT, key)) if m.group(1) == letter else ("wrong", _pick(WRONG, key))
    vals = _vals(t)
    if any(v in post["accept"] for v in vals):
        return "correct", _pick(CORRECT, key)
    if any(v in post["wrong"] for v in vals):
        return "wrong", _pick(WRONG, key)
    return "ignore", None


# -------------------------------------------------------------- carousel --

def check_carousel(text, post):
    t = text.lower()
    key = post.get("id", "") + t
    accepts = [set(a) for a in post["accepts"]]           # 5 sets of accepted answers

    # 1) labelled answers: "KS3: 1100", "GCSE H = 7"
    given = {}
    for pat, idx in LEVEL_ALIASES:
        m = re.search(rf"(?:{pat})\s*[:=\-–)]?\s*(?:is\s*)?({VALUE})", t)
        if m:
            given[idx] = norm(m.group(1).replace(" ", ""))
    # 2) numbered answers: "1) 5  2) 3"
    if not given:
        for m in re.finditer(rf"(?<![\d/])([1-5])\s*[).:\-–]\s*({VALUE})", t):
            given[int(m.group(1)) - 1] = norm(m.group(2).replace(" ", ""))
        if len(given) < 2:
            given = {}
    # 3) a score: "4/5"
    if not given:
        m = re.search(r"(?<![\d/])([0-5])\s*(?:/|out of)\s*5(?![\d/])", t)
        if m:
            return "score", _pick(SCORE[int(m.group(1))], key)
    # 4) bare numbers
    if not given:
        vals = _vals(t)
        if not vals:
            return "ignore", None
        if len(vals) == 5:
            given = dict(enumerate(vals))
        else:
            hits = [i for i, a in enumerate(accepts) if any(v in a for v in vals)]
            if hits:
                if len(vals) == 1:
                    return "correct", f"{_pick(CORRECT, key)} ({LEVEL_NAMES[hits[0]]})"
                return "partial", f"👏 {len(set(hits))} right! Have another look at the rest 💪"
            return "wrong", _pick(WRONG, key)

    right = [i for i, v in given.items() if v in accepts[i]]
    wrong = [i for i in given if i not in right]
    if right and not wrong:
        if len(given) == 1:
            return "correct", f"{_pick(CORRECT, key)} ({LEVEL_NAMES[right[0]]})"
        return "correct", f"{_pick(CORRECT, key)} {len(right)}/{len(given)} 🎉"
    if right:
        names = ", ".join(LEVEL_NAMES[i] for i in sorted(wrong))
        return "partial", f"👏 {len(right)}/{len(given)} right! Have another look at {names} 😉"
    return "wrong", _pick(WRONG, key)
