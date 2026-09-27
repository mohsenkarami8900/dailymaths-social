"""
Original background music for the story / reel video (no copyright issues).

A playful pizzicato "thinking" tune with a soft clock tick on each countdown number.
On the reveal it switches to a happy major key with a glockenspiel and fades out to the end.

Timeline matches render_story():
  0 - 1 s     intro
  1 - 6 s     countdown (the melody gets a little busier at the end)
  6 - 11.5 s  reveal + confetti, fading out

make_track(path, seed) writes a WAV file. The seed changes the key and melody a little.
"""

import random
import wave

import numpy as np
from scipy.signal import butter, fftconvolve, sosfilt

SR = 44100
INTRO, COUNT, REVEAL = 1.0, 5.0, 5.5
TOTAL = INTRO + COUNT + REVEAL
BEAT = 60 / 96                      # 0.625 s -> the countdown is exactly 8 beats


def _hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def _t(dur):
    return np.arange(int(dur * SR)) / SR


def _lp(x, cut):
    return sosfilt(butter(2, cut, "low", fs=SR, output="sos"), x)


def _add(buf, start, sig, gain=1.0):
    i = int(start * SR)
    if 0 <= i < len(buf):
        sig = sig[: len(buf) - i]
        buf[i: i + len(sig)] += sig * gain


def _beats(start, n, sub=1):
    return [start + i * BEAT / sub for i in range(n * sub)]


def _pizz(m, dur=0.35):
    t = _t(dur)
    f = _hz(m)
    s = sum(np.sin(2 * np.pi * f * k * t) / k ** 1.3 * np.exp(-t * k / 0.15) for k in range(1, 7))
    return s * np.minimum(1, t / 0.004) * np.exp(-t / 0.09)


def _glock(m, dur=1.2):
    t = _t(dur)
    f = _hz(m)
    s = np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-t / 0.15)
    return s * np.minimum(1, t / 0.002) * np.exp(-t / 0.5)


def _woodtick(pitch):
    t = _t(0.05)
    return np.sin(2 * np.pi * pitch * t) * np.exp(-t / 0.01)


def _reverb(x, rng, secs=0.8, wet=0.08):
    """Light stereo room reverb."""
    t = _t(secs)
    out = []
    for ch in range(2):
        ir = _lp(rng.standard_normal(len(t)) * np.exp(-t / (secs / 5)), 5000)
        ir /= np.sqrt((ir ** 2).sum())
        out.append(x * (1 - wet) + wet * fftconvolve(x, ir)[: len(x)])
    return np.stack(out, axis=1)


def _tune(buf, root, rng):
    c0 = INTRO
    walk = [0, 3, 5, 7, 8, 7, 5, 3]                      # tiptoe bass line
    mel = [12, 15, 14, 12, 10, 12, 7, 0]
    _add(buf, 0.4, _pizz(root - 12), 0.2)
    for i, t in enumerate(_beats(c0, 8)):
        _add(buf, t, _pizz(root - 24 + walk[i]), 0.30)
        if i < 6:                                        # melody on the off-beats...
            _add(buf, t + BEAT / 2, _pizz(root + mel[i]), 0.16)
        else:                                            # ...twice as busy in the last 2 beats
            for j, tt in enumerate(_beats(t, 1, 4)):
                _add(buf, tt, _pizz(root + [12, 15, 19, 22][j] + (i - 6) * 2), 0.15)
    for i in range(5):
        _add(buf, c0 + i, _woodtick(700), 0.06)
    # reveal: same tiptoe tune in a happy major key
    r0 = c0 + COUNT
    _add(buf, r0, _glock(root + 24, 1.5), 0.10)
    _add(buf, r0 + 0.08, _glock(root + 28, 1.5), 0.08)
    bass = [0, 4, 7, 4, 5, 4, 2, 4, 0]
    tune = rng.choice([[16, 19, 24, 19, 17, 16, 14, 16, 12],
                       [12, 16, 19, 16, 17, 14, 11, 14, 12],
                       [19, 16, 12, 16, 17, 16, 14, 11, 12]])
    for k, t in enumerate(_beats(r0, 9)):
        _add(buf, t, _pizz(root - 24 + bass[k]), 0.26)
        _add(buf, t + BEAT / 2, _pizz(root + tune[k]), 0.15)


def make_track(path, seed=1, style=None):
    rng = random.Random(seed)
    nrng = np.random.default_rng(seed)
    root = 60 + rng.choice([0, 2, -3, 5, -5])            # C, D, A, F or G
    buf = np.zeros(int((TOTAL + 1) * SR))
    _tune(buf, root, rng)
    buf = _lp(buf, 6500)[: int(TOTAL * SR)]
    fo = int(REVEAL * SR)                                # fade out from the reveal to the end
    buf[-fo:] *= np.linspace(1, 0, fo) ** 1.2
    fi = int(0.05 * SR)
    buf[:fi] *= np.linspace(0, 1, fi)
    st = _reverb(buf, nrng)
    st *= 0.09 / (np.sqrt((st ** 2).mean()) + 1e-9)     # soft, about -21 dB
    st = np.clip(st, -0.7, 0.7)
    pcm = (st * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return path


if __name__ == "__main__":
    make_track("music_test.wav")
    print("music_test.wav written")
