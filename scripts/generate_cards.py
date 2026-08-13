#!/usr/bin/env python3
"""Generate professional SVG cards for GitHub profile README."""

import json
import urllib.request
import os

# ── Theme Colors ──────────────────────────────────────────────
BG = "#0d1117"
CARD_BG = "#161b22"
CARD_BORDER = "#1e3a5f"
PRIMARY = "#00b4d8"
SECONDARY = "#0077b6"
LIGHT = "#48cae4"
LIGHTER = "#90e0ef"
DARK_ACCENT = "#0d4175"
TEXT = "#e0e0e0"
TEXT_SEC = "#8b949e"

W = 995
CARD_W = 225
CARD_H = 160
GAP = 14
PAD = 24


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "GitHub-Profile-Generator"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def get_github_data(username):
    user = fetch_json(f"https://api.github.com/users/{username}")
    repos = fetch_json(f"https://api.github.com/users/{username}/repos?per_page=100&sort=updated")

    total_stars = sum(r.get("stargazers_count", 0) for r in repos)
    langs = {}
    for r in repos:
        lang = r.get("language")
        if lang:
            langs[lang] = langs.get(lang, 0) + 1

    sorted_langs = sorted(langs.items(), key=lambda x: -x[1])[:6]
    total_repos = len(repos)

    return {
        "username": username,
        "name": user.get("name", username),
        "public_repos": user.get("public_repos", total_repos),
        "followers": user.get("followers", 0),
        "total_stars": total_stars,
        "total_repos": total_repos,
        "languages": sorted_langs,
    }


def svg_header(w, h):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
<defs>
  <linearGradient id="blueGrad" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0%" stop-color="{SECONDARY}"/>
    <stop offset="100%" stop-color="{PRIMARY}"/>
  </linearGradient>
</defs>
<rect width="{w}" height="{h}" fill="{BG}" rx="12"/>
'''


def rounded_rect(x, y, w, h, color=CARD_BG, border=CARD_BORDER, rx=8):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{color}" stroke="{border}" stroke-width="1.5"/>\n'


def text_el(x, y, content, size=12, color=TEXT, anchor="middle", weight="normal"):
    return f'<text x="{x}" y="{y}" font-family="Segoe UI,Helvetica,Arial,sans-serif" font-size="{size}" fill="{color}" text-anchor="{anchor}" font-weight="{weight}">{content}</text>\n'


def progress_bar(x, y, w, h, pct, color=PRIMARY):
    filled = int(w * min(pct, 100) / 100)
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{h//2}" fill="{CARD_BG}"/>\n'
        f'<rect x="{x}" y="{y}" width="{filled}" height="{h}" rx="{h//2}" fill="{color}"/>\n'
    )


def circle_icon(x, y, r, color, label):
    """Draw a circle with a single character inside."""
    return (
        f'<circle cx="{x}" cy="{y}" r="{r}" fill="{color}" opacity="0.2"/>\n'
        f'<circle cx="{x}" cy="{y}" r="{r}" fill="none" stroke="{color}" stroke-width="1.5"/>\n'
        f'<text x="{x}" y="{y + 5}" font-family="Segoe UI,Helvetica,Arial,sans-serif" font-size="14" fill="{color}" text-anchor="middle" font-weight="bold">{label}</text>\n'
    )


# ── Milestones SVG ────────────────────────────────────────────
def generate_milestones(data):
    milestones = [
        ("T", "Commits", "Hyper Committer", 753, 78, PRIMARY),
        ("\u2605", "Stars", "First Star", 7, 67, SECONDARY),
        ("\u2665", "Followers", "First Friend", data["followers"], 11, LIGHT),
        ("!", "Issues", "First Issue", 4, 33, LIGHTER),
        ("+", "Pull Requests", "First Pull", 2, 11, DARK_ACCENT),
        ("\u25A0", "Repositories", "First Repository", data["total_repos"], 56, PRIMARY),
        ("\u25B2", "Experience", "Newbie", 5, 75, SECONDARY),
        ("\u25CF", "Reviews", "Unknown", 0, 0, DARK_ACCENT),
    ]

    rows = 2
    cols = 4
    h = PAD + rows * (CARD_H + GAP) + PAD

    svg = svg_header(W, h)

    for i, (icon, cat, rank, pts, pct, clr) in enumerate(milestones):
        row = i // cols
        col = i % cols
        cx = PAD + col * (CARD_W + GAP)
        cy = PAD + row * (CARD_H + GAP)

        svg += rounded_rect(cx, cy, CARD_W, CARD_H, border=clr)

        # Circle icon
        icon_x = cx + CARD_W // 2
        icon_y = cy + 28
        svg += circle_icon(icon_x, icon_y, 16, clr, icon)

        # Category name
        svg += text_el(cx + CARD_W // 2, cy + 58, cat, 13, clr, weight="bold")

        # Rank subtitle
        svg += text_el(cx + CARD_W // 2, cy + 73, rank, 10, TEXT_SEC)

        # Points
        svg += text_el(cx + CARD_W // 2, cy + 98, f"{pts}pt", 22, TEXT, weight="bold")

        # Progress bar
        bar_x = cx + 20
        bar_y = cy + 112
        bar_w = CARD_W - 40
        svg += progress_bar(bar_x, bar_y, bar_w, 7, pct, clr)

        # Rank label
        svg += text_el(cx + CARD_W // 2, cy + 140, f"RANK {pct}%", 10, TEXT_SEC)

    svg += "</svg>"
    return svg, h


# ── Stats SVG ─────────────────────────────────────────────────
def generate_stats(data):
    h = 310
    svg = svg_header(W, h)

    # ── Left card: GitHub Stats ──
    lx, ly, lw, lh = PAD, 0, 480, 300
    svg += rounded_rect(lx, ly, lw, lh)
    svg += text_el(lx + lw // 2, ly + 28, f"{data['username']}'s GitHub Stats", 15, PRIMARY, weight="bold")

    # Divider line
    svg += f'<line x1="{lx + 20}" y1="{ly + 40}" x2="{lx + lw - 20}" y2="{ly + 40}" stroke="{CARD_BORDER}" stroke-width="1"/>\n'

    stats = [
        ("\u2605", "Total Stars Earned", data["total_stars"]),
        ("\u25CF", "Total Commits (2026)", 755),
        ("\u2194", "Total PRs", 2),
        ("!", "Total Issues", 4),
        ("\u25A0", "Contributed to (last year)", data["total_repos"]),
    ]

    for i, (icon, label, val) in enumerate(stats):
        sy = ly + 65 + i * 36
        # Icon circle
        svg += f'<circle cx="{lx + 22}" cy="{sy - 4}" r="10" fill="{PRIMARY}" opacity="0.15"/>\n'
        svg += text_el(lx + 22, sy + 1, icon, 10, PRIMARY)
        # Label
        svg += text_el(lx + 58, sy, label, 13, TEXT_SEC, "start")
        # Value
        svg += text_el(lx + lw - 24, sy, str(val), 14, TEXT, "end", "bold")

    # Grade badge
    badge_cx = lx + lw // 2
    badge_cy = ly + lh - 35
    svg += f'<circle cx="{badge_cx}" cy="{badge_cy}" r="22" fill="{PRIMARY}" opacity="0.12"/>\n'
    svg += f'<circle cx="{badge_cx}" cy="{badge_cy}" r="22" fill="none" stroke="{PRIMARY}" stroke-width="2"/>\n'
    svg += text_el(badge_cx, badge_cy + 7, "A+", 22, PRIMARY, weight="bold")

    # ── Right card: Languages ──
    rx, ry, rw, rh = PAD + lw + GAP, 0, W - PAD * 2 - lw - GAP, 300
    svg += rounded_rect(rx, ry, rw, rh)
    svg += text_el(rx + rw // 2, ry + 28, "Most Used Languages", 15, PRIMARY, weight="bold")

    # Divider line
    svg += f'<line x1="{rx + 20}" y1="{ry + 40}" x2="{rx + rw - 20}" y2="{ry + 40}" stroke="{CARD_BORDER}" stroke-width="1"/>\n'

    total = sum(c for _, c in data["languages"])
    bar_colors = [PRIMARY, SECONDARY, LIGHT, LIGHTER, DARK_ACCENT, "#4a6fa5"]

    for i, (lang, count) in enumerate(data["languages"]):
        pct = (count / total * 100) if total else 0
        ly2 = ry + 65 + i * 38
        svg += text_el(rx + 20, ly2, lang, 12, TEXT, "start")
        bar_x = rx + 130
        bar_w = rw - 200
        svg += progress_bar(bar_x, ly2 - 8, bar_w, 10, pct, bar_colors[i % len(bar_colors)])
        svg += text_el(rx + rw - 20, ly2, f"{pct:.0f}%", 11, TEXT_SEC, "end")

    svg += "</svg>"
    return svg


# ── Main ──────────────────────────────────────────────────────
if __name__ == "__main__":
    username = os.environ.get("GITHUB_USER", "Doker367")
    out_dir = os.environ.get("OUT_DIR", "dist")
    os.makedirs(out_dir, exist_ok=True)

    print(f"Fetching data for {username}...")
    data = get_github_data(username)
    print(f"  Repos: {data['total_repos']}, Stars: {data['total_stars']}, Languages: {data['languages']}")

    milestones_svg, h = generate_milestones(data)
    with open(os.path.join(out_dir, "milestones.svg"), "w") as f:
        f.write(milestones_svg)
    print(f"  milestones.svg ({h}px)")

    stats_svg = generate_stats(data)
    with open(os.path.join(out_dir, "stats.svg"), "w") as f:
        f.write(stats_svg)
    print(f"  stats.svg")

    print("Done!")
