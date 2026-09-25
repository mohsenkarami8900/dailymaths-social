"""
Renders Instagram / Facebook media for Daily Maths UK.

- render_story(q, out_mp4)       -> 1080x1920 ~12 s video: question, countdown, reveal + confetti
- render_carousel(puzzles, dir)  -> 6 JPEG slides (1080x1350): 5 level puzzles + answers

HTML templates are rendered to PNG with headless Chromium (Playwright);
the video is assembled with ffmpeg.
"""

import asyncio
import html
import math
import os
import random
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent
FONTS = ROOT / "fonts"
ASSETS = ROOT / "assets"

W, H = 1080, 1920          # story
CW, CH = 1080, 1350        # carousel
FPS = 30

NAVY_BG = "radial-gradient(circle at 25% 15%, #1E3A8A 0%, #0F172A 55%, #0B1120 100%)"
CONFETTI = [(249, 115, 22), (16, 185, 129), (59, 130, 246), (139, 92, 246),
            (239, 68, 68), (250, 204, 21), (255, 255, 255)]

LEVELS = {
    "ks1": ("KS1", "Years 1–2", "#F97316"),
    "ks2": ("KS2", "Years 3–6", "#10B981"),
    "ks3": ("KS3", "Years 7–9", "#3B82F6"),
    "gcse_foundation": ("GCSE Foundation", "Grades 1–5", "#8B5CF6"),
    "gcse_higher": ("GCSE Higher", "Grades 4–9", "#EF4444"),
}


def _fonts_css():
    return "\n".join(
        f"@font-face{{font-family:V;src:url('file://{FONTS}/Vazirmatn-{n}.ttf');font-weight:{w}}}"
        for n, w in [("Regular", 400), ("Medium", 500), ("Bold", 700), ("Black", 900)])


def _e(s):
    return html.escape(str(s))


# --------------------------------------------------------------- story ----

def _story_html(q, phase, count=5):
    """phase: 'ask' (question + countdown number) or 'reveal'."""
    opts = ""
    for i, opt in enumerate(q["options"]):
        letter = "ABC"[i]
        correct = i == q["answer"]
        if phase == "reveal":
            cls = "opt ok" if correct else "opt dim"
        else:
            cls = "opt"
        tick = '<span class="tick">✓</span>' if phase == "reveal" and correct else ""
        opts += f'<div class="{cls}"><span class="l">{letter}</span><span class="t">{_e(opt)}</span>{tick}</div>'

    if phase == "ask":
        # ring progress: remaining fraction
        frac = count / 5
        circ = 2 * math.pi * 88
        middle = f'''
        <div class="timer">
          <svg width="220" height="220" viewBox="0 0 220 220">
            <circle cx="110" cy="110" r="88" stroke="rgba(255,255,255,.15)" stroke-width="16" fill="none"/>
            <circle cx="110" cy="110" r="88" stroke="#FACC15" stroke-width="16" fill="none"
              stroke-linecap="round" stroke-dasharray="{circ:.1f}" stroke-dashoffset="{circ*(1-frac):.1f}"
              transform="rotate(-90 110 110)"/>
          </svg>
          <div class="num">{count}</div>
        </div>
        <div class="think">Think…</div>'''
    else:
        middle = f'''
        <div class="yay">Did you get it?</div>
        <div class="why">{_e(q.get("why", ""))}</div>'''

    return f"""<html><head><meta charset="utf-8"><style>{_fonts_css()}
    body{{margin:0}}
    .c{{width:{W}px;height:{H}px;background:{NAVY_BG};font-family:V;color:#F1F5F9;position:relative;overflow:hidden}}
    .brand{{position:absolute;top:250px;left:0;right:0;text-align:center}}
    .pill{{display:inline-block;font-size:34px;font-weight:700;letter-spacing:3px;border:2px solid rgba(255,255,255,.25);
      border-radius:999px;padding:10px 34px;color:#CBD5E1}}
    .q{{position:absolute;top:400px;left:80px;right:80px;text-align:center;font-size:84px;font-weight:900;line-height:1.2}}
    .opts{{position:absolute;top:760px;left:110px;right:110px;display:flex;flex-direction:column;gap:34px}}
    .opt{{display:flex;align-items:center;gap:34px;background:rgba(255,255,255,.08);border:3px solid rgba(255,255,255,.18);
      border-radius:36px;padding:26px 40px;font-size:66px;font-weight:700}}
    .opt .l{{width:92px;height:92px;border-radius:50%;background:rgba(255,255,255,.14);display:flex;align-items:center;
      justify-content:center;font-size:50px;font-weight:900;flex-shrink:0}}
    .opt .t{{flex:1}}
    .opt.ok{{background:#16A34A;border-color:#4ADE80;box-shadow:0 0 60px rgba(74,222,128,.55)}}
    .opt.ok .l{{background:#fff;color:#16A34A}}
    .opt.dim{{opacity:.35}}
    .tick{{font-size:72px;font-weight:900}}
    .timer{{position:absolute;top:1290px;left:0;right:0;display:flex;justify-content:center}}
    .num{{position:absolute;top:0;left:0;right:0;height:220px;display:flex;align-items:center;justify-content:center;
      font-size:110px;font-weight:900}}
    .think{{position:absolute;top:1530px;left:0;right:0;text-align:center;font-size:44px;font-weight:500;color:#94A3B8}}
    .yay{{position:absolute;top:1300px;left:0;right:0;text-align:center;font-size:96px;font-weight:900;color:#FACC15}}
    .why{{position:absolute;top:1440px;left:90px;right:90px;text-align:center;font-size:44px;font-weight:500;color:#CBD5E1}}
    .foot{{position:absolute;bottom:260px;left:0;right:0;text-align:center;font-size:34px;font-weight:500;color:#94A3B8}}
    </style></head><body><div class="c">
      <div class="brand"><span class="pill">DAILY MATHS UK · QUESTION OF THE DAY</span></div>
      <div class="q">{_e(q["question"])}</div>
      <div class="opts">{opts}</div>
      {middle}
      <div class="foot">Follow @dailymathsuk for a new puzzle every day</div>
    </div></body></html>"""


async def _shots(pages, size, workdir):
    """pages: list of (name, html). Returns list of PNG paths."""
    out = []
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": size[0], "height": size[1]})
        for name, h in pages:
            f = Path(workdir) / f"{name}.html"
            f.write_text(h, encoding="utf-8")
            await pg.goto(f"file://{f}")
            await pg.wait_for_timeout(250)
            png = Path(workdir) / f"{name}.png"
            await pg.screenshot(path=str(png))
            out.append(png)
        await b.close()
    return out


def _confetti_layer(t, parts):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for p in parts:
        tt = t - p["delay"]
        if tt < 0:
            continue
        x = p["x"] + p["vx"] * tt + 30 * math.sin(p["wob"] + tt * 4)
        y = p["y"] + p["vy"] * tt + 0.5 * 1400 * tt * tt
        if y > H + 40:
            continue
        ang = p["rot"] + p["spin"] * tt
        w, h = p["w"], p["h"] * abs(math.cos(ang * 1.7)) + 2
        ca, sa = math.cos(ang), math.sin(ang)
        pts = [(x + dx * ca - dy * sa, y + dx * sa + dy * ca)
               for dx, dy in [(-w, -h), (w, -h), (w, h), (-w, h)]]
        d.polygon(pts, fill=p["c"] + (255,))
    return layer


def render_story(q, out_mp4, workdir="/tmp/story_work", seed=1):
    os.makedirs(workdir, exist_ok=True)
    pages = [(f"ask{n}", _story_html(q, "ask", n)) for n in (5, 4, 3, 2, 1)]
    pages.append(("reveal", _story_html(q, "reveal")))
    pngs = asyncio.run(_shots(pages, (W, H), workdir))
    ask = [Image.open(p).convert("RGB") for p in pngs[:5]]
    reveal = Image.open(pngs[5]).convert("RGBA")

    rnd = random.Random(seed)
    parts = [dict(x=rnd.uniform(-50, W + 50), y=rnd.uniform(-900, -20), vx=rnd.uniform(-120, 120),
                  vy=rnd.uniform(-200, 250), w=rnd.uniform(8, 16), h=rnd.uniform(14, 26),
                  rot=rnd.uniform(0, 6.28), spin=rnd.uniform(-8, 8), wob=rnd.uniform(0, 6.28),
                  delay=rnd.uniform(0, 0.6), c=rnd.choice(CONFETTI)) for _ in range(260)]

    intro, count_s, reveal_s = 1.0, 5.0, 5.5
    total = int((intro + count_s + reveal_s) * FPS)
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
           "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-profile:v", "high",
           "-preset", "medium", "-crf", "20", "-movflags", "+faststart",
           "-c:a", "aac", "-b:a", "128k", str(out_mp4)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    black = Image.new("RGB", (W, H), (11, 17, 32))
    for f in range(total):
        t = f / FPS
        if t < intro:                                  # fade in on "5"
            frame = Image.blend(black, ask[0], min(1, t / 0.5))
        elif t < intro + count_s:                      # countdown 5..1
            frame = ask[min(4, int(t - intro))]
        else:                                          # reveal + confetti
            tr = t - intro - count_s
            frame = reveal.copy()
            frame.alpha_composite(_confetti_layer(tr, parts))
            frame = frame.convert("RGB")
        proc.stdin.write(frame.tobytes())
    proc.stdin.close()
    proc.wait()
    return out_mp4


# ------------------------------------------------------------ carousel ---

def _math(s):
    """Escape text; parts wrapped in [[...]] are kept on one line and highlighted."""
    out, rest = "", str(s)
    while "[[" in rest and "]]" in rest:
        a, b = rest.split("[[", 1)
        m, rest = b.split("]]", 1)
        out += _e(a) + f'<span class="m">{_e(m)}</span>'
    return out + _e(rest)


def _slide_html(idx, total, level_key, puzzle):
    name, sub, color = LEVELS[level_key]
    if idx == 1:
        hook = '<div class="hook">5 puzzles · 5 levels · How far can you get? <b>Swipe →</b></div>'
    elif idx == total:
        hook = '<div class="hook">Got your answers? <b>Swipe to check them →</b></div>'
    else:
        hook = '<div class="hook">Swipe for the next level →</div>'
    return f"""<html><head><meta charset="utf-8"><style>{_fonts_css()}
    body{{margin:0}}
    .c{{width:{CW}px;height:{CH}px;background:{NAVY_BG};font-family:V;color:#F1F5F9;position:relative;overflow:hidden;
       box-sizing:border-box;padding:80px 84px}}
    .top{{display:flex;align-items:center;justify-content:space-between}}
    .lv{{display:flex;align-items:center;gap:22px}}
    .lv img{{width:110px;height:110px;border-radius:50%}}
    .lv b{{font-size:52px;font-weight:900;display:block;line-height:1}}
    .lv span{{font-size:30px;font-weight:500;color:{color}}}
    .n{{font-size:32px;font-weight:700;color:#94A3B8;border:2px solid rgba(255,255,255,.2);border-radius:999px;padding:8px 26px}}
    .bar{{height:10px;background:rgba(255,255,255,.1);border-radius:9px;margin:46px 0 0}}
    .bar i{{display:block;height:100%;width:{idx/5*100:.0f}%;background:{color};border-radius:9px}}
    .mid{{position:absolute;left:84px;right:84px;top:300px;bottom:220px;display:flex;flex-direction:column;justify-content:center}}
    .p{{font-size:76px;font-weight:900;line-height:1.25;letter-spacing:-.5px}}
    .p .m{{white-space:nowrap;color:#FACC15}}
    .hint{{margin-top:40px;font-size:38px;font-weight:500;color:#94A3B8}}
    .hook{{position:absolute;left:84px;right:84px;bottom:150px;font-size:34px;font-weight:500;color:#CBD5E1}}
    .hook b{{color:#FACC15}}
    .foot{{position:absolute;left:84px;right:84px;bottom:74px;display:flex;justify-content:space-between;
      font-size:28px;font-weight:700;color:#64748B;letter-spacing:1px}}
    </style></head><body><div class="c">
      <div class="top"><div class="lv"><img src="file://{ASSETS}/{level_key}.png"><div><b>{_e(name)}</b><span>{_e(sub)}</span></div></div>
        <div class="n">{idx} / {total}</div></div>
      <div class="bar"><i></i></div>
      <div class="mid"><div class="p">{_math(puzzle["q"])}</div>
      <div class="hint">{_e(puzzle.get("hint", "No calculator. Just your brain."))}</div></div>
      {hook}
      <div class="foot"><span>DAILY MATHS UK</span><span>dailymathsuk.com</span></div>
    </div></body></html>"""


def _answers_html(puzzles):
    rows = ""
    for i, (lk, pz) in enumerate(puzzles, 1):
        name, _, color = LEVELS[lk]
        rows += f"""<div class="r"><div class="k" style="background:{color}">{i}</div>
          <div><div class="h"><span>{_e(name)}</span> {_e(pz["a"])}</div><div class="w">{_e(pz.get("why",""))}</div></div></div>"""
    return f"""<html><head><meta charset="utf-8"><style>{_fonts_css()}
    body{{margin:0}}
    .c{{width:{CW}px;height:{CH}px;background:{NAVY_BG};font-family:V;color:#F1F5F9;position:relative;overflow:hidden;
       box-sizing:border-box;padding:80px 84px}}
    h1{{font-size:76px;font-weight:900;margin:0 0 50px}}
    .r{{display:flex;gap:28px;align-items:flex-start;margin-bottom:38px}}
    .k{{width:64px;height:64px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:34px;
       font-weight:900;flex-shrink:0}}
    .h{{font-size:44px;font-weight:900}} .h span{{font-size:28px;font-weight:700;color:#94A3B8;margin-right:10px}}
    .w{{font-size:30px;font-weight:500;color:#CBD5E1;margin-top:4px}}
    .q{{position:absolute;left:84px;right:84px;bottom:150px;font-size:36px;font-weight:700;color:#FACC15}}
    .foot{{position:absolute;left:84px;right:84px;bottom:74px;display:flex;justify-content:space-between;
      font-size:28px;font-weight:700;color:#64748B;letter-spacing:1px}}
    </style></head><body><div class="c"><h1>Answers</h1>{rows}
      <div class="q">How many did you get? Comment your score, like 4/5!</div>
      <div class="foot"><span>DAILY MATHS UK</span><span>dailymathsuk.com</span></div>
    </div></body></html>"""


def render_carousel(puzzles, out_dir, workdir="/tmp/carousel_work"):
    """puzzles: list of (level_key, {"q","a","why","hint"?}) in KS1..GCSE H order."""
    os.makedirs(workdir, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)
    pages = [(f"s{i}", _slide_html(i, len(puzzles), lk, pz)) for i, (lk, pz) in enumerate(puzzles, 1)]
    pages.append(("s6", _answers_html(puzzles)))
    pngs = asyncio.run(_shots(pages, (CW, CH), workdir))
    out = []
    for i, p in enumerate(pngs, 1):
        jpg = Path(out_dir) / f"slide{i}.jpg"
        Image.open(p).convert("RGB").save(jpg, "JPEG", quality=92)   # Instagram API needs JPEG
        out.append(jpg)
    return out
