#!/usr/bin/env python3
"""Render the profile's animated SVG cards.

A GitHub README is sanitized: no style, no script, no class, no id. An
<img src="*.svg"> is not, and keeps its own stylesheet. So every animation
here lives inside the SVG as CSS keyframes. Stdlib only.

Motion budget: the header loops forever (it is the banner), while the
terminal and guestbook play once per page load and hold their end state.
Every animated card answers prefers-reduced-motion by rendering finished.
"""
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone

USER = "raxjinn"
OUT = "charts"

BG = "#0d0221"
SURFACE = "#150a2e"
INK = "#e6e1ff"
DIM = "#7d6f9c"
CYAN = "#2de2e6"
PINK = "#f6019d"
RED = "#ff3864"
VIOLET = "#791e94"
GOLD = "#ffd319"
MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, 'DejaVu Sans Mono', monospace"

# Edit these to change what the cards say.
TAGLINES = ["healthcare interoperability", "agentic tooling", "data plumbing that holds"]
NEOFETCH = [
    ("focus", "medical imaging pipelines"),
    ("stack", "C# / .NET, Python, TypeScript"),
    ("data", "PostgreSQL, DICOM, HL7v2"),
    ("editor", "Neovim, Visual Studio"),
    ("shell", "pwsh, bash"),
    ("motto", "boring code, loud alerts"),
]

CH = 0.551  # measured monospace advance as a fraction of font size


def esc(s):
    """XML-escape and defang. Guestbook text is written by strangers."""
    s = re.sub(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]", "", str(s))
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;").replace("'", "&apos;"))


def api(path):
    req = urllib.request.Request(
        "https://api.github.com" + path,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "profile-render"},
    )
    tok = os.environ.get("GITHUB_TOKEN")
    if tok:
        req.add_header("Authorization", "Bearer " + tok)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


CONTRIB_QUERY = """
query($login:String!) {
  user(login:$login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def contributions():
    """Daily contribution counts for the last year, via GraphQL.

    Needs a user token rather than the Actions token, which cannot read a
    person's contribution collection. Private work is counted here only
    because "Include private contributions on my profile" is enabled; the
    counts arrive with no repository attached, which is the point.
    """
    tok = os.environ.get("GRAPHQL_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": CONTRIB_QUERY, "variables": {"login": USER}}).encode(),
        headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json",
                 "User-Agent": "profile-render"},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        payload = json.load(r)
    if "errors" in payload:
        raise RuntimeError(payload["errors"][0].get("message", "graphql error"))

    cal = payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    weeks = [[(d["date"], d["contributionCount"]) for d in w["contributionDays"]]
             for w in cal["weeks"]]
    days = [d for w in weeks for d in w]

    # Today reads 0 until the first push lands, which would otherwise break a
    # live streak the moment the cron runs, so an empty final day is skipped.
    tail = days[:-1] if days and days[-1][1] == 0 else days
    current = 0
    for _, n in reversed(tail):
        if n == 0:
            break
        current += 1

    longest = run = 0
    for _, n in days:
        run = run + 1 if n else 0
        longest = max(longest, run)

    busiest = max(days, key=lambda d: d[1]) if days else ("", 0)
    return {
        "total": cal["totalContributions"],
        "current": current,
        "longest": longest,
        "busiest": busiest,
        "weekly": [sum(n for _, n in w) for w in weeks],
    }


def write(name, body):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(body)
    print("wrote %s (%d bytes)" % (path, len(body)))


def defs(extra=""):
    """Shared gradients, textures and filters."""
    return """<defs>
  <linearGradient id="edge" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="%(v)s"/><stop offset=".5" stop-color="%(p)s"/>
    <stop offset="1" stop-color="%(c)s"/>
  </linearGradient>
  <linearGradient id="rule" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="%(v)s" stop-opacity="0"/>
    <stop offset=".5" stop-color="%(p)s"/>
    <stop offset="1" stop-color="%(c)s" stop-opacity="0"/>
  </linearGradient>
  <pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse">
    <rect width="4" height="1" fill="#ffffff" opacity=".035"/>
  </pattern>
  <filter id="glow" x="-40%%" y="-40%%" width="180%%" height="180%%">
    <feGaussianBlur stdDeviation="3" result="b"/>
    <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
%(extra)s</defs>""" % {"v": VIOLET, "p": PINK, "c": CYAN, "extra": extra}


def chrome(w, h, title):
    """Window frame: surface, scanlines, animated top rule, traffic lights."""
    return """<rect width="%(w)d" height="%(h)d" rx="12" fill="%(bg)s"/>
<rect width="%(w)d" height="%(h)d" rx="12" fill="url(#scan)"/>
<g clip-path="inset(0 round 12px)">
  <rect id="beam" x="0" y="0" width="%(w)d" height="3" fill="url(#edge)"/>
</g>
<text x="20" y="30" font-family="%(mono)s" font-size="12" fill="%(dim)s">%(title)s</text>
<circle class="led" cx="%(d1)d" cy="25" r="5" fill="%(red)s"/>
<circle class="led" cx="%(d2)d" cy="25" r="5" fill="%(pink)s"/>
<circle class="led" cx="%(d3)d" cy="25" r="5" fill="%(cyan)s"/>
<rect x="1.5" y="1.5" width="%(iw)d" height="%(ih)d" rx="11" fill="none"
      stroke="%(violet)s" stroke-opacity=".5"/>""" % {
        "w": w, "h": h, "iw": w - 3, "ih": h - 3, "bg": BG, "mono": MONO, "dim": DIM,
        "title": esc(title), "red": RED, "pink": PINK, "cyan": CYAN, "violet": VIOLET,
        "d1": w - 50, "d2": w - 34, "d3": w - 18,
    }


CHROME_CSS = """
  @keyframes sweep { 0% { transform: translateX(-100%); } 100% { transform: translateX(100%); } }
  @keyframes bl { 0%,49% { opacity: 1; } 50%,100% { opacity: 0; } }
  @keyframes ledup { 0% { opacity: .15; } 100% { opacity: .85; } }
  #beam { animation: sweep 6s linear infinite; }
  .led { opacity: .85; animation: ledup .5s ease-out both; }
"""


def header():
    """Banner: gradient wordmark with pulsing bloom, taglines typed on a loop."""
    w, h, fs = 860, 210, 17
    total = 4.0 * len(TAGLINES)
    adv = fs * CH

    # The typewriter animates SVG geometry -- a clip rect's `width` and the cursor's
    # `x` -- rather than `clip-path: inset()` or `transform`. Two reasons: Chrome
    # resolves inset() percentages on SVG <text> against a zero-size reference box
    # and clips the glyphs away entirely, and transform/opacity animations run on
    # the compositor where they cannot be verified by a headless screenshot.
    # steps(n) subdivides the on -> typed interval into one jump per character.
    clips, css, body = [], [], []
    slot = 100.0 / len(TAGLINES)
    for i, line in enumerate(TAGLINES):
        n = max(len(line), 1)
        run = n * adv                      # rendered width of the line in monospace
        on = i * slot + 0.001              # strictly increasing: a degenerate
        typed = i * slot + slot * 0.45     # keyframe pair makes Chrome drop the rest
        hold = (i + 1) * slot - 0.002
        off = (i + 1) * slot - 0.001
        clips.append('  <clipPath id="w%d"><rect id="m%d" x="24" y="%d" width="0" height="%d"/></clipPath>'
                     % (i, i, 152 - fs, fs + 6))
        css.append("""
    #m%(i)d { animation: type%(i)d %(t).1fs steps(%(n)d) infinite; }
    #c%(i)d { animation: run%(i)d %(t).1fs steps(%(n)d) infinite; }
    @keyframes type%(i)d {
      0%%,%(on).3f%% { width: 0px; }
      %(typed).3f%%,%(hold).3f%% { width: %(run).1fpx; }
      %(off).3f%%,100%% { width: 0px; }
    }
    @keyframes run%(i)d {
      0%%,%(on).3f%% { x: 24px; width: 0px; }
      %(on2).3f%% { x: 24px; width: %(adv).1fpx; }
      %(typed).3f%%,%(hold).3f%% { x: %(end).1fpx; width: %(adv).1fpx; }
      %(off).3f%%,100%% { x: %(end).1fpx; width: 0px; }
    }""" % {"i": i, "t": total, "n": n, "run": run, "adv": adv, "end": 24 + run + 3,
            "on": on, "on2": on + 0.001, "typed": typed, "hold": hold, "off": off})
        body.append(
            '<text x="24" y="152" font-family="%s" font-size="%d" fill="%s" clip-path="url(#w%d)">%s</text>'
            '<rect id="c%d" x="24" y="%d" width="0" height="%d" fill="%s"/>'
            % (MONO, fs, CYAN, i, esc(line), i, 152 - fs + 3, fs, PINK)
        )

    extra = """  <linearGradient id="word" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="%(c)s"/><stop offset=".55" stop-color="%(p)s"/>
    <stop offset="1" stop-color="%(r)s"/>
  </linearGradient>
  <pattern id="grid" width="34" height="34" patternUnits="userSpaceOnUse">
    <path d="M34 0H0v34" fill="none" stroke="%(v)s" stroke-opacity=".22"/>
  </pattern>
  <filter id="bloom" x="-25%%" y="-25%%" width="150%%" height="150%%">
    <feGaussianBlur stdDeviation="6" result="b"/>
    <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
%(clips)s
""" % {"c": CYAN, "p": PINK, "r": RED, "v": VIOLET, "clips": "\n".join(clips)}

    # With motion off, show the first tagline finished and drop the rest.
    first = max(len(TAGLINES[0]), 1)
    still = ("    #m0 { animation: none; width: %.1fpx; }\n"
             "    #c0 { animation: none; width: 0px; }\n"
             "    %s { animation: none; width: 0px; }\n"
             % (first * adv,
                ", ".join("#m%d, #c%d" % (i, i) for i in range(1, len(TAGLINES)))))

    return """<svg xmlns="http://www.w3.org/2000/svg" width="%(w)d" height="%(h)d" viewBox="0 0 %(w)d %(h)d" role="img" aria-label="evan: %(alt)s">
%(defs)s
<style>
  @keyframes bl { 0%%,49%% { opacity: 1; } 50%%,100%% { opacity: 0; } }
  @keyframes sweep { 0%% { transform: translateX(-100%%); } 100%% { transform: translateX(100%%); } }
  @keyframes pulse { 0%%,100%% { opacity: .5; } 50%% { opacity: 1; } }
  @keyframes drift { 0%% { transform: translateY(0); } 100%% { transform: translateY(-34px); } }
  @keyframes drawin { 0%% { stroke-dashoffset: 60; } 100%% { stroke-dashoffset: 0; } }
  #shine { animation: sweep 7s linear infinite; }
  #halo { animation: pulse 4s ease-in-out infinite; }
  #mesh { animation: drift 8s linear infinite; }
  .tick { stroke-dasharray: 60; animation: drawin 1.4s ease-out both; }
  [id^="c"] { animation: bl 1s steps(1) infinite; }
  @media (prefers-reduced-motion: reduce) {
    #shine, #halo, #mesh, .tick { animation: none; }
    #halo { opacity: .7; }
    .tick { stroke-dashoffset: 0; }
%(still)s  }%(css)s
</style>
<rect width="%(w)d" height="%(h)d" rx="14" fill="%(bg)s"/>
<g clip-path="inset(0 round 14px)">
  <rect id="mesh" x="0" y="0" width="%(w)d" height="%(h2)d" fill="url(#grid)"/>
  <rect id="shine" x="-%(w)d" width="%(w)d" height="%(h)d" fill="url(#rule)" opacity=".18"/>
</g>
<rect width="%(w)d" height="%(h)d" rx="14" fill="url(#scan)"/>
<text id="halo" x="24" y="104" font-family="%(mono)s" font-size="76" font-weight="700"
      fill="url(#word)" filter="url(#bloom)" letter-spacing="-2">evan</text>
<text x="24" y="104" font-family="%(mono)s" font-size="76" font-weight="700"
      fill="url(#word)" letter-spacing="-2">evan</text>
%(body)s
<rect x="24" y="176" width="%(rw)d" height="2" fill="url(#rule)"/>
<path class="tick" d="M12 44V16h28" fill="none" stroke="%(cyan)s" stroke-opacity=".6" stroke-width="2"/>
<path class="tick" d="M%(bx)d %(by)dv28h-28" fill="none" stroke="%(pink)s" stroke-opacity=".6" stroke-width="2"/>
<rect x="1" y="1" width="%(iw)d" height="%(ih)d" rx="13" fill="none" stroke="%(violet)s" stroke-opacity=".55"/>
</svg>
""" % {"w": w, "h": h, "h2": h + 34, "iw": w - 2, "ih": h - 2, "rw": w - 48, "bx": w - 12,
       "by": h - 44, "bg": BG, "mono": MONO, "cyan": CYAN, "pink": PINK, "violet": VIOLET,
       "defs": defs(extra), "css": "".join(css), "body": "\n".join(body),
       "still": still, "alt": esc(", ".join(TAGLINES))}


def terminal():
    """neofetch readout that types itself out once, then holds."""
    try:
        u = api("/users/" + USER)
        born = datetime.strptime(u["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        years = (datetime.now(timezone.utc) - born).days / 365.25
        facts = [("uptime", "%.1f years on github" % years),
                 ("public", "%d repos" % u.get("public_repos", 0))]
    except Exception as e:  # a dead API must not break the card
        print("warn: profile fetch failed (%s)" % e, file=sys.stderr)
        facts = []

    rows = NEOFETCH + facts
    w = 520
    h = 96 + len(rows) * 22 + 34
    step = 0.16  # seconds between rows appearing

    body = ['<text x="20" y="54" font-family="%s" font-size="13" fill="%s">'
            '<tspan fill="%s">$</tspan> neofetch</text>' % (MONO, CYAN, PINK)]
    css = []
    y = 82
    for n, (k, v) in enumerate(rows):
        delay = 0.5 + n * step
        css.append("  #row%d { animation: rowin .35s ease-out %.2fs both; }" % (n, delay))
        body.append(
            '<g id="row%d">'
            '<rect x="20" y="%d" width="8" height="8" fill="%s" opacity=".7"/>'
            '<text x="38" y="%d" font-family="%s" font-size="13" fill="%s">%s</text>'
            '<text x="112" y="%d" font-family="%s" font-size="13" fill="%s">%s</text>'
            '</g>'
            % (n, y - 10, CYAN, y, MONO, DIM, esc(k), y, MONO, INK, esc(v))
        )
        y += 22
    prompt_delay = 0.5 + len(rows) * step + 0.2
    css.append("  #prompt { animation: rowin .3s ease-out %.2fs both; }" % prompt_delay)
    body.append('<g id="prompt"><text x="20" y="%d" font-family="%s" font-size="13" fill="%s">'
                '<tspan fill="%s">$</tspan> <tspan id="cur" fill="%s">&#9608;</tspan></text></g>'
                % (y + 16, MONO, CYAN, PINK, PINK))

    return """<svg xmlns="http://www.w3.org/2000/svg" width="%(w)d" height="%(h)d" viewBox="0 0 %(w)d %(h)d" role="img" aria-label="Terminal readout of stack and focus">
%(defs)s
<style>%(chrome)s
  @keyframes rowin { 0%% { opacity: 0; transform: translateX(-8px); } 100%% { opacity: 1; transform: translateX(0); } }
  #cur { animation: bl 1.1s steps(1) infinite; }
%(css)s
  @media (prefers-reduced-motion: reduce) {
    #beam, #cur, .led, #prompt, [id^="row"] { animation: none; opacity: 1; transform: none; }
  }
</style>
%(frame)s
%(body)s
</svg>
""" % {"w": w, "h": h, "defs": defs(), "chrome": CHROME_CSS, "css": "\n".join(css),
       "frame": chrome(w, h, "~/evan -- zsh"), "body": "\n".join(body)}


def guestbook():
    """Tiles for issues labelled `approved`. Unlabelled issues never render."""
    try:
        issues = api("/repos/%s/%s/issues?labels=approved&state=all&per_page=6"
                     "&sort=created&direction=desc" % (USER, USER))
    except Exception as e:
        print("warn: issue fetch failed (%s)" % e, file=sys.stderr)
        issues = []
    entries = [(i["user"]["login"], (i.get("title") or "")[:90])
               for i in issues if "pull_request" not in i]

    w, cols, tile_h = 520, 2, 74
    rows = max(1, -(-max(len(entries), 1) // cols))
    h = 60 + rows * (tile_h + 10) + 14
    tw = (w - 48) // cols
    body, css = [], []

    if not entries:
        body.append('<text x="%d" y="%d" text-anchor="middle" font-family="%s" font-size="13" '
                    'fill="%s">no signatures yet -- open an issue</text>'
                    % (w // 2, h // 2 + 8, MONO, DIM))

    for n, (who, msg) in enumerate(entries):
        cx = 20 + (n % cols) * ((w - 40) // cols + 4)
        cy = 56 + (n // cols) * (tile_h + 10)
        accent = [CYAN, PINK, RED, GOLD][n % 4]
        css.append("  #tile%d { animation: popin .45s cubic-bezier(.16,1,.3,1) %.2fs both; }"
                   % (n, 0.35 + n * 0.09))
        body.append(
            '<g id="tile%(n)d">'
            '<rect x="%(x)d" y="%(y)d" width="%(tw)d" height="%(th)d" rx="8" fill="%(surf)s" '
            'stroke="%(a)s" stroke-opacity=".55"/>'
            '<circle cx="%(ax)d" cy="%(ay)d" r="15" fill="none" stroke="%(a)s"/>'
            '<text x="%(ax)d" y="%(ty)d" text-anchor="middle" font-family="%(mono)s" '
            'font-size="14" fill="%(a)s">%(ini)s</text>'
            '<text x="%(mx)d" y="%(n1)d" font-family="%(mono)s" font-size="12" fill="%(ink)s">%(who)s</text>'
            '<text x="%(mx)d" y="%(n2)d" font-family="%(mono)s" font-size="10" fill="%(dim)s">%(l1)s</text>'
            '<text x="%(mx)d" y="%(n3)d" font-family="%(mono)s" font-size="10" fill="%(dim)s">%(l2)s</text>'
            '</g>' % {
                "n": n, "x": cx, "y": cy, "tw": tw, "th": tile_h, "surf": SURFACE, "a": accent,
                "ax": cx + 26, "ay": cy + 26, "ty": cy + 31, "mx": cx + 50, "n1": cy + 24,
                "n2": cy + 42, "n3": cy + 56, "mono": MONO, "ink": INK, "dim": DIM,
                "ini": esc((who[:1] or "?").upper()), "who": esc(who[:18]),
                "l1": esc(msg[:30]), "l2": esc(msg[30:60]),
            }
        )

    return """<svg xmlns="http://www.w3.org/2000/svg" width="%(w)d" height="%(h)d" viewBox="0 0 %(w)d %(h)d" role="img" aria-label="Visitor guestbook, %(n)d signed">
%(defs)s
<style>%(chrome)s
  @keyframes popin { 0%% { opacity: 0; transform: translateY(10px) scale(.96); } 100%% { opacity: 1; transform: translateY(0) scale(1); } }
%(css)s
  @media (prefers-reduced-motion: reduce) {
    #beam, .led, [id^="tile"] { animation: none; opacity: 1; transform: none; }
  }
</style>
%(frame)s
%(body)s
</svg>
""" % {"w": w, "h": h, "n": len(entries), "defs": defs(), "chrome": CHROME_CSS,
       "css": "\n".join(css), "frame": chrome(w, h, "guestbook -- %d signed" % len(entries)),
       "body": "\n".join(body)}


def streak():
    """Four stat tiles plus one sparkline of weekly totals.

    The tiles are hero numbers, not a chart -- four unrelated single values
    have no shared scale to plot against. The sparkline is the only thing
    here with a time axis, and being a single series it needs no legend:
    the card title names it. Labels stay in muted ink so no number relies
    on a series colour to be read. There is no hover layer because a README
    serves this through an <img>, where no script runs.
    """
    w, h = 520, 216
    try:
        c = contributions()
    except Exception as e:
        print("warn: contributions fetch failed (%s)" % e, file=sys.stderr)
        c = None

    if not c:
        body = ('<text x="%d" y="%d" text-anchor="middle" font-family="%s" font-size="13" '
                'fill="%s">contribution data unavailable</text>' % (w // 2, h // 2, MONO, DIM))
        return """<svg xmlns="http://www.w3.org/2000/svg" width="%(w)d" height="%(h)d" viewBox="0 0 %(w)d %(h)d" role="img" aria-label="Contribution statistics unavailable">
%(defs)s<style>%(chrome)s</style>
%(frame)s
%(body)s
</svg>
""" % {"w": w, "h": h, "defs": defs(), "chrome": CHROME_CSS,
       "frame": chrome(w, h, "contributions -- last 365 days"), "body": body}

    day = c["busiest"][0][5:] if c["busiest"][0] else "--"
    tiles = [("total", "%d" % c["total"], CYAN),
             ("current", "%dd" % c["current"], PINK),
             ("longest", "%dd" % c["longest"], GOLD),
             ("busiest", "%d" % c["busiest"][1], INK)]

    body, css = [], []
    tw = (w - 40 - 3 * 8) // 4
    for i, (label, value, color) in enumerate(tiles):
        x = 20 + i * (tw + 8)
        css.append("  #u%d { animation: grow .5s ease-out %.2fs both; }" % (i, 0.25 + i * 0.1))
        body.append(
            '<text x="%(x)d" y="%(vy)d" font-family="%(mono)s" font-size="23" font-weight="700" '
            'fill="%(c)s">%(v)s</text>'
            '<text x="%(x)d" y="%(ly)d" font-family="%(mono)s" font-size="10" fill="%(dim)s">%(l)s</text>'
            '<rect id="u%(i)d" x="%(x)d" y="%(uy)d" width="0" height="2" rx="1" fill="%(c)s" opacity=".55"/>'
            % {"x": x, "vy": 72, "ly": 88, "uy": 94, "i": i, "mono": MONO, "c": color,
               "v": esc(value), "l": esc(label), "dim": DIM}
        )
        css.append("  @keyframes grow { from { width: 0px; } to { width: %dpx; } }" % tw
                   if i == 0 else "")

    # Sparkline: 2px single-series line, recessive baseline, one direct label on
    # the peak rather than a number on every point.
    wk = c["weekly"] or [0]
    top = max(max(wk), 1)
    px0, px1, py0, py1 = 20, w - 20, 122, 190
    step = (px1 - px0) / max(len(wk) - 1, 1)
    pts = [(px0 + i * step, py1 - (v / top) * (py1 - py0)) for i, v in enumerate(wk)]
    path = "M" + " L".join("%.1f %.1f" % p for p in pts)
    peak = max(range(len(wk)), key=lambda i: wk[i])
    pk = pts[peak]
    label_anchor = "end" if pk[0] > w - 90 else "start"
    label_dx = -8 if label_anchor == "end" else 8

    body.append(
        '<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-opacity=".55"/>'
        '<path d="%s L%.1f %d L%.1f %d Z" fill="url(#under)"/>'
        '<path id="spark" d="%s" fill="none" stroke="%s" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
        '<circle id="pkdot" cx="%.1f" cy="%.1f" r="4" fill="%s" stroke="%s" stroke-width="2"/>'
        '<text x="%.1f" y="%.1f" text-anchor="%s" font-family="%s" font-size="10" fill="%s">'
        'peak %d</text>'
        '<text x="%d" y="%d" font-family="%s" font-size="10" fill="%s">weekly contributions</text>'
        % (px0, py1 + 1, px1, py1 + 1, VIOLET,
           path, pts[-1][0], py1, px0, py1,
           path, CYAN,
           pk[0], pk[1], CYAN, SURFACE,
           pk[0] + label_dx, pk[1] - 8, label_anchor, MONO, INK, wk[peak],
           px0, py1 + 16, MONO, DIM)
    )

    return """<svg xmlns="http://www.w3.org/2000/svg" width="%(w)d" height="%(h)d" viewBox="0 0 %(w)d %(h)d" role="img" aria-label="%(alt)s">
%(defs)s<style>%(chrome)s
  @keyframes draw { from { stroke-dashoffset: 1400; } to { stroke-dashoffset: 0; } }
  @keyframes dot { from { r: 0px; } to { r: 4px; } }
  #spark { stroke-dasharray: 1400; animation: draw 1.8s ease-out .3s both; }
  #pkdot { animation: dot .3s ease-out 2.0s both; }
%(css)s
  @media (prefers-reduced-motion: reduce) {
    #beam, .led, #spark, #pkdot, [id^="u"] { animation: none; }
    #spark { stroke-dashoffset: 0; }
  }
</style>
%(frame)s
%(body)s
</svg>
""" % {"w": w, "h": h, "defs": defs(
        '  <linearGradient id="under" x1="0" y1="0" x2="0" y2="1">\n'
        '    <stop offset="0" stop-color="%s" stop-opacity=".28"/>\n'
        '    <stop offset="1" stop-color="%s" stop-opacity="0"/>\n'
        '  </linearGradient>\n' % (CYAN, CYAN)),
       "chrome": CHROME_CSS, "css": "\n".join(x for x in css if x),
       "frame": chrome(w, h, "contributions -- last 365 days"),
       "body": "\n".join(body),
       "alt": esc("Contributions: %d total, %d day current streak, %d day longest streak"
                  % (c["total"], c["current"], c["longest"]))}


if __name__ == "__main__":
    cards = {"header": header, "terminal": terminal, "streak": streak, "guestbook": guestbook}
    for name in sys.argv[1:] or list(cards):
        write(name + ".svg", cards[name]())
