"""
Content for the Daily Maths UK Instagram / Facebook bot.

- story_question(rng)     -> 3-option quick question for stories and reels
- carousel_puzzles(rng)   -> five mental-maths puzzles, one per level
- captions + hashtags     -> warm, human captions (English)

Every answer is calculated by the code, so it is always correct.
All puzzles are designed to be solved in your head (no calculator).
"""

import math
import random
from fractions import Fraction


def fmt(n):
    """Nice number formatting: 1100 -> '1,100', 2.5 -> '2.5', -3 -> '−3'."""
    if isinstance(n, Fraction):
        n = float(n)
    if isinstance(n, float) and n.is_integer():
        n = int(n)
    s = f"{n:,}" if isinstance(n, int) else f"{n:,.2f}".rstrip("0").rstrip(".")
    return s.replace("-", "−")


def money(x):
    return f"£{x:,.2f}"


def norm(s):
    """Normalise an answer/comment token for comparison."""
    s = str(s).lower().replace("£", "").replace(",", "").replace("−", "-").strip()
    s = s.rstrip(".")
    try:
        f = float(s)
        return str(int(f)) if f.is_integer() else str(round(f, 4))
    except ValueError:
        return s.replace(" ", "")


# ============================================================ STORY / REEL ==
# Each returns (question, correct, [wrong1, wrong2], why). Wrong answers are
# typical mistakes, so the question feels fair.

def _s_percent(r):
    p = r.choice([10, 20, 25, 50, 5, 15])
    n = r.choice([40, 60, 80, 120, 200, 240, 360])
    ans = n * p // 100 if n * p % 100 == 0 else n * p / 100
    wrong = [n * p / 10 if p != 10 else n / 2, n * (p + 5) / 100]
    why = {10: f"10% means ÷ 10 → {fmt(n)} ÷ 10",
           20: f"10% is {fmt(n/10)}, so 20% is double",
           25: f"25% is a quarter → {fmt(n)} ÷ 4",
           50: f"50% is half of {fmt(n)}",
           5: f"10% is {fmt(n/10)}, 5% is half of that",
           15: f"10% ({fmt(n/10)}) + 5% ({fmt(n/20)})"}[p]
    return f"What is {p}% of {fmt(n)}?", ans, wrong, why


def _s_times(r):
    a, b = r.randint(6, 12), r.randint(6, 12)
    return f"What is {a} × {b}?", a * b, [a * b + a, a * b - b], f"{a} × {b} = {a*b}"


def _s_order(r):
    a, b, c = r.randint(2, 9), r.randint(2, 6), r.randint(2, 6)
    return (f"What is {a} + {b} × {c}?", a + b * c, [(a + b) * c, a + b + c],
            f"Multiply first: {b} × {c} = {b*c}, then + {a}")


def _s_missing(r):
    a, x = r.randint(3, 12), r.randint(4, 12)
    return f"? × {a} = {a*x}", x, [x + 1, a * x - a], f"{a*x} ÷ {a} = {x}"


def _s_sequence(r):
    start, k = r.randint(1, 5), r.choice([2, 3])
    seq = [start * k ** i for i in range(4)]
    nxt = seq[-1] * k
    return (f"What comes next?  {', '.join(map(str, seq))}, ?", nxt,
            [seq[-1] + (seq[-1] - seq[-2]), nxt + k],
            f"Each number is × {k}")


def _s_half_double(r):
    if r.random() < 0.5:
        n = r.choice([3.5, 4.5, 7.5, 12.5, 25.5])
        return f"Double {fmt(n)}?", n * 2, [n * 2 + 1, n * 2 - 1], f"{fmt(n)} + {fmt(n)} = {fmt(n*2)}"
    n = r.choice([150, 250, 350, 170, 190, 330])
    return f"Half of {n}?", n / 2, [n / 2 + 10, n / 2 - 5], f"Half of {n} is {fmt(n/2)}"


def _s_divide_half(r):
    n = r.choice([6, 8, 12, 15, 20, 25])
    return (f"What is {n} ÷ 0.5?", n * 2, [n / 2, n + 0.5],
            f"÷ 0.5 means 'how many halves?' → {n} × 2")


def _s_negative(r):
    a, b = r.randint(2, 9), r.randint(2, 9)
    return f"What is −{a} − {b}?", -(a + b), [a + b, b - a if b != a else -(a + b) + 2], f"Start at −{a}, go down {b} more"


def _s_time(r):
    h = r.choice([1.5, 2.5, 3.5, 1.25, 2.25, 0.75])
    m = int(h * 60)
    return f"How many minutes in {fmt(h)} hours?", m, [int(h * 100), m + 10], f"{fmt(h)} × 60 = {m}"


def _s_change(r):
    price = r.choice([1.35, 2.45, 3.65, 4.15, 2.85, 1.75])
    return (f"You pay £5 for something that costs {money(price)}. Your change?",
            money(5 - price), [money(5 - price + 0.10), money(5 - price - 0.10)],
            f"£5 − {money(price)} = {money(5 - price)}")


def _s_units(r):
    v = r.choice([1.5, 2.5, 0.75, 3.2, 0.4])
    return f"{fmt(v)} km in metres?", int(v * 1000), [int(v * 100), int(v * 10000)], f"1 km = 1,000 m"


def _s_angles(r):
    a, b = r.randint(35, 80), r.randint(35, 80)
    c = 180 - a - b
    return (f"A triangle has angles {a}° and {b}°. The third angle?", f"{c}°",
            [f"{c+10}°", f"{360-a-b}°"], f"Angles in a triangle add to 180°")


def _s_square(r):
    n = r.randint(11, 15)
    return f"What is {n}²?", n * n, [n * 2, n * n + n], f"{n} × {n} = {n*n}"


def _s_fraction_of(r):
    d = r.choice([3, 4, 5, 8])
    k = r.randint(2, d - 1)
    while math.gcd(k, d) != 1:
        k = r.randint(2, d - 1) if d > 2 else 1
    n = d * r.randint(4, 12)
    return (f"What is {k}/{d} of {n}?", n // d * k, [n // d, n - n // d * k],
            f"{n} ÷ {d} = {n//d}, then × {k}")


def _s_average(r):
    m = r.randint(5, 15)
    a, b = m - r.randint(1, 4), m + r.randint(1, 3)
    c = 3 * m - a - b
    return (f"What is the mean of {a}, {b} and {c}?", m, [a + b + c, m + 1],
            f"Total {a+b+c} ÷ 3 = {m}")


STORY_GENERATORS = [_s_percent, _s_times, _s_order, _s_missing, _s_sequence,
                    _s_half_double, _s_divide_half, _s_negative, _s_time,
                    _s_change, _s_units, _s_angles, _s_square, _s_fraction_of, _s_average]


def story_question(rng):
    """Returns dict: question, options[3], answer(index), why, accept[list]."""
    for _ in range(50):
        gen = rng.choice(STORY_GENERATORS)
        q, correct, wrong, why = gen(rng)
        opts = [correct] + list(wrong)
        shown = [x if isinstance(x, str) else fmt(x) for x in opts]
        if len({norm(s) for s in shown}) == 3:
            break
    order = [0, 1, 2]
    rng.shuffle(order)
    options = [shown[i] for i in order]
    answer = order.index(0)
    return {"question": q, "options": options, "answer": answer, "why": why,
            "letter": "ABC"[answer], "accept": [norm(shown[0])],
            "wrong": [norm(s) for s in shown[1:]]}


# =============================================================== CAROUSEL ==
# Each returns dict: q (text, [[...]] = keep maths together), a (display),
# accept (normalised answers), why, hint (optional)

def P(q, a, why, hint=None, accept=None):
    d = {"q": q, "a": fmt(a) if not isinstance(a, str) else a, "why": why,
         "accept": accept or [norm(a)]}
    if hint:
        d["hint"] = hint
    return d


# ---------- KS1
def k1_think(r):
    x, k = r.randint(3, 12), r.randint(1, 6)
    return P(f"I think of a number, double it and add {k}. I get {2*x+k}. What is my number?",
             x, f"{2*x+k} − {k} = {2*x}, and half of {2*x} is {x}")

def k1_birds(r):
    a, b, c = r.randint(9, 15), r.randint(2, 6), r.randint(2, 5)
    return P(f"There are {a} birds in a tree. {b} fly away, then {c} more land. How many birds are in the tree now?",
             a - b + c, f"{a} − {b} = {a-b}, then + {c} = {a-b+c}")

def k1_bags(r):
    g, e = r.randint(3, 5), r.choice([2, 5, 10])
    return P(f"Sam has {g} bags with {e} sweets in each bag. He eats 2. How many sweets are left?",
             g * e - 2, f"{g} × {e} = {g*e}, then − 2 = {g*e-2}")

def k1_half(r):
    n = r.randint(6, 15)
    return P(f"Half of my number is {n}. What is double my number?", 4 * n,
             f"My number is {2*n}, and double {2*n} is {4*n}")

def k1_legs(r):
    d, c = r.randint(2, 4), r.randint(2, 4)
    return P(f"In a farm there are {d} ducks and {c} cows. How many legs altogether?",
             2 * d + 4 * c, f"Ducks: {d} × 2 = {2*d}, cows: {c} × 4 = {4*c}")

def k1_coins(r):
    t, f = r.randint(1, 3), r.randint(1, 3)
    pl = lambda n: "coin" if n == 1 else "coins"
    return P(f"Mia has {t} ten-pence {pl(t)} and {f} five-pence {pl(f)}. How much money does she have (in p)?",
             10 * t + 5 * f, f"{t} × 10p + {f} × 5p = {10*t+5*f}p",
             accept=[norm(10 * t + 5 * f), norm(f"{10*t+5*f}p")])


# ---------- KS2
def k2_pizza(r):
    s = r.choice([8, 12])
    q = s // 4
    e = r.randint(1, s - q - 1)
    return P(f"A pizza has {s} slices. Tom eats a quarter of it and Sara eats {e} slices. How many slices are left?",
             s - q - e, f"A quarter of {s} = {q}; {s} − {q} − {e} = {s-q-e}")

def k2_99(r):
    n = r.randint(3, 9)
    return P(f"What is [[99 × {n}]]?", 99 * n, f"100 × {n} = {100*n}, then − {n} = {99*n}",
             hint="Hint: 99 is 100 − 1")

def k2_books(r):
    p = r.choice([1.25, 1.75, 2.25, 3.75, 2.50])
    n = r.choice([4, 6, 8])
    return P(f"A notebook costs {money(p)}. How much do {n} notebooks cost?", money(p * n),
             f"{money(p)} × {n} = {money(p*n)}", accept=[norm(p * n)])

def k2_think(r):
    x, m, s = r.randint(4, 12), r.randint(3, 6), r.randint(2, 9)
    return P(f"I multiply a number by {m}, then take away {s}. The answer is {m*x-s}. What was the number?",
             x, f"{m*x-s} + {s} = {m*x}, then ÷ {m} = {x}")

def k2_sum(r):
    n = r.choice([10, 12, 20])
    return P(f"What do you get if you add up all the whole numbers from 1 to {n}?", n * (n + 1) // 2,
             f"Pair them: 1 + {n}, 2 + {n-1}… that's {n//2} pairs of {n+1}",
             hint="Hint: try pairing the numbers")

def k2_minutes(r):
    h, q = r.randint(1, 3), r.choice([15, 35, 45])
    return P(f"A film lasts {h} hour{'s' if h > 1 else ''} and {q} minutes. How many minutes is that altogether?",
             60 * h + q, f"{h} × 60 = {60*h}, then + {q} = {60*h+q}")

def k2_percent(r):
    a, b = r.choice([40, 80, 120]), r.choice([30, 50, 70])
    return P(f"What is 25% of {a} plus 10% of {b}?", a // 4 + b / 10,
             f"25% of {a} = {a//4}, 10% of {b} = {fmt(b/10)}")


# ---------- KS3
def k3_25(r):
    n = r.choice([12, 16, 24, 28, 32, 36, 44, 48])
    return P(f"What is [[25 × {n}]]?", 25 * n, f"25 × {n} = 25 × 4 × {n//4} = 100 × {n//4}",
             hint="Hint: 25 × 4 = 100")

def k3_equation(r):
    x, a, b = r.randint(3, 12), r.randint(2, 7), r.randint(2, 15)
    return P(f"Solve in your head: [[{a}x + {b} = {a*x+b}]]", x,
             f"{a*x+b} − {b} = {a*x}, then ÷ {a}", accept=[norm(x), f"x={x}"])

def k3_nth(r):
    d, s = r.randint(3, 7), r.randint(1, 6)
    n = r.choice([10, 20, 50])
    seq = [s + d * i for i in range(4)]
    return P(f"The sequence goes {', '.join(map(str, seq))}, … What is the {n}th term?",
             s + d * (n - 1), f"nth term = {d}n {'+' if s-d>=0 else '−'} {abs(s-d)}, so {d}×{n} {'+' if s-d>=0 else '−'} {abs(s-d)}")

def k3_polygon(r):
    n, name = r.choice([(5, "pentagon"), (6, "hexagon"), (8, "octagon"), (10, "decagon")])
    return P(f"What is one interior angle of a regular {name}?", f"{180-360//n}°",
             f"Exterior = 360 ÷ {n} = {360//n}°, interior = 180 − {360//n}",
             accept=[norm(180 - 360 // n), norm(f"{180-360//n}°")])

def k3_ratio(r):
    a, b = r.choice([(2, 3), (3, 5), (1, 4), (3, 7)])
    k = r.randint(4, 12)
    tot = (a + b) * k
    return P(f"Share £{tot} in the ratio {a}:{b}. How much is the bigger share?", f"£{b*k}",
             f"{a}+{b} = {a+b} parts, 1 part = £{k}, so {b} parts = £{b*k}", accept=[norm(b * k)])

def k3_squares(r):
    a, b = r.randint(3, 9), r.randint(2, 5)
    return P(f"What is [[(−{a})² − {b}²]]?", a * a - b * b,
             f"(−{a})² = {a*a} (a negative squared is positive), minus {b*b}")

def k3_percent(r):
    n = r.choice([160, 240, 320, 180, 260])
    return P(f"What is 15% of {n}?", n * 15 / 100, f"10% = {fmt(n/10)}, 5% = {fmt(n/20)}, add them")


# ---------- GCSE Foundation
def gf_discount(r):
    p, d = r.choice([40, 50, 80, 60]), r.choice([10, 20])
    new = p * (1 - d / 100) ** 2
    return P(f"A £{p} jumper is reduced by {d}%, then by another {d}%. What is the new price?", money(new),
             f"£{p} → {money(p*(1-d/100))} → {money(new)} (not {money(p*(1-2*d/100))}!)", accept=[norm(new)])

def gf_speed(r):
    s, t = r.choice([40, 50, 60, 80]), r.choice([1.5, 2.5, 3.5])
    return P(f"A car travels {fmt(s*t)} km in {fmt(t)} hours. What is its average speed in km/h?", s,
             f"{fmt(s*t)} ÷ {fmt(t)} = {s}")

def gf_pythag(r):
    a, b, c = r.choice([(3, 4, 5), (6, 8, 10), (5, 12, 13), (9, 12, 15), (8, 15, 17)])
    return P(f"A right-angled triangle has shorter sides {a} cm and {b} cm. How long is the longest side?",
             f"{c} cm", f"√({a}² + {b}²) = √{c*c} = {c}", accept=[norm(c), norm(f"{c}cm")])

def gf_increase(r):
    p, i = r.choice([80, 60, 120, 40]), r.choice([15, 25, 5])
    return P(f"Increase £{p} by {i}%.", money(p * (1 + i / 100)),
             f"{i}% of £{p} = {money(p*i/100)}, add it on", accept=[norm(p * (1 + i / 100))])

def gf_expand(r):
    a, b = r.randint(2, 7), r.randint(2, 7)
    return P(f"Expand [[(x + {a})(x + {b})]]. What number goes in front of the x?", a + b,
             f"x² + {a}x + {b}x + {a*b} = x² + {a+b}x + {a*b}")

def gf_probability(r):
    red, blue = r.randint(2, 5), r.randint(3, 7)
    f = Fraction(red, red + blue)
    return P(f"A bag has {red} red and {blue} blue counters. You pick one. What's the probability it's red?",
             f"{f.numerator}/{f.denominator}", f"{red} red out of {red+blue} counters",
             accept=[f"{f.numerator}/{f.denominator}", norm(round(float(f), 4))])

def gf_triangle(r):
    b, h = r.choice([8, 10, 12, 14]), r.choice([5, 7, 9])
    return P(f"A triangle has base {b} cm and height {h} cm. What is its area in cm²?", b * h // 2,
             f"½ × {b} × {h} = {b*h//2}")


# ---------- GCSE Higher
def gh_recip(r):
    k = r.randint(3, 6)
    return P(f"If [[x + 1/x = {k}]], what is [[x² + 1/x²]]?", k * k - 2,
             f"Square it: x² + 2 + 1/x² = {k*k}, so {k*k} − 2 = {k*k-2}")

ORD = {2: "square", 3: "cube", 4: "fourth", 5: "fifth"}


def gh_powers(r):
    b, top, bot = r.choice([(8, 2, 3), (27, 2, 3), (16, 3, 4), (32, 2, 5), (64, 2, 3)])
    root = round(b ** (1 / bot))
    return P(f"What is [[{b}^({top}/{bot})]]?", root ** top,
             f"The {ORD[bot]} root of {b} is {root}, then {root}^{top} = {root**top}")

def gh_roots(r):
    p, q = r.randint(2, 6), r.randint(2, 7)
    return P(f"What is the sum of the solutions of [[x² − {p+q}x + {p*q} = 0]]?", p + q,
             f"It factorises to (x − {p})(x − {q}), so {p} + {q} = {p+q}")

def gh_surds(r):
    a, b = r.choice([(5, 3), (4, 3), (6, 2), (5, 4)])
    return P(f"[[√{2*a*a} + √{2*b*b} = k√2]]. What is k?", a + b,
             f"√{2*a*a} = {a}√2 and √{2*b*b} = {b}√2")

def gh_simul(r):
    x, y = r.randint(4, 12), r.randint(1, 5)
    return P(f"[[x + y = {x+y}]] and [[x − y = {x-y}]]. What is x?", x,
             f"Add them: 2x = {2*x}, so x = {x}", accept=[norm(x), f"x={x}"])

def gh_ff(r):
    a, b, s = r.randint(2, 3), r.randint(1, 5), r.randint(1, 3)
    inner = a * s + b
    return P(f"If [[f(x) = {a}x + {b}]], what is [[f(f({s}))]]?", a * inner + b,
             f"f({s}) = {inner}, then f({inner}) = {a*inner+b}")

def gh_gradient(r):
    m, c = r.randint(2, 6), r.randint(-3, 5)
    x1, x2 = r.randint(0, 2), r.randint(3, 6)
    return P(f"What is the gradient of the line through [[({x1}, {m*x1+c})]] and [[({x2}, {m*x2+c})]]?", m,
             f"({m*x2+c} − {m*x1+c}) ÷ ({x2} − {x1}) = {m}")


LEVEL_GENS = {
    "ks1": [k1_think, k1_birds, k1_bags, k1_half, k1_legs, k1_coins],
    "ks2": [k2_pizza, k2_99, k2_books, k2_think, k2_sum, k2_percent, k2_minutes],
    "ks3": [k3_25, k3_equation, k3_nth, k3_polygon, k3_ratio, k3_squares, k3_percent],
    "gcse_foundation": [gf_discount, gf_speed, gf_pythag, gf_increase, gf_expand, gf_probability, gf_triangle],
    "gcse_higher": [gh_recip, gh_powers, gh_roots, gh_surds, gh_simul, gh_ff, gh_gradient],
}
LEVEL_ORDER = ["ks1", "ks2", "ks3", "gcse_foundation", "gcse_higher"]


def carousel_puzzles(rng, avoid=None):
    """One puzzle per level. `avoid` = set of generator names used recently."""
    avoid = avoid or set()
    out, used = [], []
    for lvl in LEVEL_ORDER:
        gens = [g for g in LEVEL_GENS[lvl] if g.__name__ not in avoid] or LEVEL_GENS[lvl]
        g = rng.choice(gens)
        used.append(g.__name__)
        out.append((lvl, g(rng)))
    return out, used


# =============================================================== CAPTIONS ==

CORE_TAGS = ["#mathspuzzle", "#mentalmaths"]
EXTRA_TAGS = ["#gcsemaths", "#ks2maths", "#ks3maths", "#brainteaser", "#mathsquiz", "#sats",
              "#11plus", "#mathsuk", "#learnmaths", "#homeschooluk", "#mathschallenge", "#gcse"]


def hashtags(rng, n=5):
    return " ".join(CORE_TAGS + rng.sample(EXTRA_TAGS, n - len(CORE_TAGS)))


CAROUSEL_OPENERS = [
    "Five quick puzzles today, one for every level from KS1 all the way up to GCSE Higher 🧠",
    "Right, brain warm-up time! 5 puzzles, 5 levels, KS1 to GCSE 🧠",
    "How far can you get today? Start easy with KS1 and see if you can make it to GCSE Higher 🚀",
    "New set of puzzles is here! One for each level, KS1 to GCSE 🧩",
]
CAROUSEL_MIDDLES = [
    "No calculator, no paper if you can, just your brain.",
    "All of them can be done in your head, promise 😄",
    "Take your time, every one of them is doable without a calculator.",
]
CAROUSEL_ASKS = [
    "Pop your answers in the comments before you check the last slide (like \"KS3: 1100\") and I'll tell you how you did 👇",
    "Comment your answers before you swipe to the end (e.g. \"KS2: 3\"), or just your score out of 5, and I'll check them for you 👇",
    "Drop your answers below, like \"KS1: 5\", and I'll reply and let you know if you got it 👇",
]
CAROUSEL_TAGS = [
    "Tag a friend who loves a challenge!",
    "Send this to someone who thinks they're good at maths 😉",
    "Share it with a friend and see who gets further!",
]


def carousel_caption(rng):
    return "\n\n".join([rng.choice(CAROUSEL_OPENERS) + " " + rng.choice(CAROUSEL_MIDDLES),
                        rng.choice(CAROUSEL_ASKS), rng.choice(CAROUSEL_TAGS),
                        "Free daily practice for UK pupils 👉 dailymathsuk.com", hashtags(rng)])


REEL_OPENERS = [
    "Can you get this one in 5 seconds? ⏱️",
    "Quick one, no calculator! ⏱️",
    "5 seconds on the clock. Go! ⏱️",
    "Think you're fast at mental maths? Try this 👀",
]


def reel_caption(rng, q):
    ask = rng.choice([
        "Pause it, pick A, B or C, and tell me in the comments 👇",
        "Comment your answer (A, B or C) before the reveal! 👇",
        "What did you go for? A, B or C? Comment below 👇",
    ])
    return "\n\n".join([rng.choice(REEL_OPENERS), q["question"], ask,
                        rng.choice(CAROUSEL_TAGS), "Daily maths for UK pupils 👉 dailymathsuk.com",
                        hashtags(rng)])


# ========================================================= COMMENT REPLIES ==

CORRECT = ["👏👏 Spot on!", "👏 Yes! Nailed it!", "👏👏 Correct, well done!", "👏 That's it! Great thinking.",
           "👏👏 Brilliant, you got it!", "👏 Correct! Love it."]
WRONG = ["So close! Have another go 💪", "Not quite, have another look 🤔", "Nearly! Give it one more try 💪",
         "Hmm, not this time. Try again? 🙂"]
SCORE = {5: ["👏👏👏 5/5! Absolute legend!", "5/5 👏👏 Top marks!"],
         4: ["👏👏 4/5, so close to perfect!", "4/5 👏 Great work!"],
         3: ["👏 3/5, nice one! Can you get 4 next time?", "3/5 👏 Good going!"],
         2: ["2/5, good effort! 💪 Have another look at the others", "2/5 👍 Keep going!"],
         1: ["1/5, well done for trying! 💪 Next time you'll get more", "1/5, keep at it! 💪"],
         0: ["Good effort! 💪 Have another look, you can do it", "Keep going! 💪 Try again"]}
