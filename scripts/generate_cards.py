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
WHITE = "#ffffff"

W = 995
CARD_W = 230
CARD_H = 170
GAP = 15
PAD = 20


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
  <linearGradient id="cardGrad" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="{CARD_BG}" stop-opacity="1"/>
    <stop offset="100%" stop-color="#0d1117" stop-opacity="1"/>
  </linearGradient>
  <linearGradient id="blueGrad" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0%" stop-color="{SECONDARY}"/>
    <stop offset="100%" stop-color="{PRIMARY}"/>
  </linearGradient>
  <linearGradient id="lightGrad" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0%" stop-color="{PRIMARY}"/>
    <stop offset="100%" stop-color="{LIGHT}"/>
  </linearGradient>
  <filter id="shadow" x="-5%" y="-5%" width="110%" height="110%">
    <feDropShadow dx="0" dy="2" stdDeviation="4" flood-color="{PRIMARY}" flood-opacity="0.15"/>
  </filter>
</defs>
<rect width="{w}" height="{h}" fill="{BG}" rx="12"/>
'''


def rounded_rect(x, y, w, h, color=CARD_BG, border=CARD_BORDER, rx=8):
    return f'''<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{color}" stroke="{border}" stroke-width="1.5"/>
'''


def text(x, y, content, size=12, color=TEXT, anchor="middle", weight="normal"):
    return f'<text x="{x}" y="{y}" font-family="Segoe UI,Helvetica,Arial,sans-serif" font-size="{size}" fill="{color}" text-anchor="{anchor}" font-weight="{weight}">{content}</text>\n'


def progress_bar(x, y, w, h, pct, color=PRIMARY):
    filled = int(w * min(pct, 100) / 100)
    empty = w - filled
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{h//2}" fill="{CARD_BG}"/>\n'
        f'<rect x="{x}" y="{y}" width="{filled}" height="{h}" rx="{h//2}" fill="{color}"/>\n'
    )


# ── Milestones SVG ────────────────────────────────────────────
def generate_milestones(data):
    milestones = [
        ("Trophy", "Commits", "Hyper Committer", 753, 78, PRIMARY),
        ("Star", "Stars", "First Star", 7, 67, SECONDARY),
        ("People", "Followers", "First Friend", data["followers"], 11, LIGHT),
        ("Alert", "Issues", "First Issue", 4, 33, LIGHTER),
        ("GitPullRequest", "Pull Requests", "First Pull", 2, 11, DARK_ACCENT),
        ("Repo", "Repositories", "First Repository", data["total_repos"], 56, PRIMARY),
        ("Graph", "Experience", "Newbie", 5, 75, SECONDARY),
        ("Eye", "Reviews", "Unknown", 0, 0, DARK_ACCENT),
    ]

    rows = 2
    cols = 4
    h = PAD + 50 + rows * (CARD_H + GAP) + PAD

    svg = svg_header(W, h)
    svg += text(W // 2, PAD + 28, "GitHub Milestones", 20, PRIMARY, weight="bold")

    for i, (icon, cat, rank, pts, pct, clr) in enumerate(milestones):
        row = i // cols
        col = i % cols
        cx = PAD + col * (CARD_W + GAP)
        cy = PAD + 50 + row * (CARD_H + GAP)

        svg += rounded_rect(cx, cy, CARD_W, CARD_H, border=clr)

        # Icon
        svg += text(cx + CARD_W // 2, cy + 30, icon, 22, clr)

        # Category
        svg += text(cx + CARD_W // 2, cy + 52, cat, 13, clr, weight="bold")

        # Rank
        svg += text(cx + CARD_W // 2, cy + 68, rank, 10, TEXT_SEC)

        # Points
        svg += text(cx + CARD_W // 2, cy + 92, f"{pts}pt", 20, TEXT, weight="bold")

        # Progress bar
        bar_x = cx + 20
        bar_y = cy + 105
        bar_w = CARD_W - 40
        svg += progress_bar(bar_x, bar_y, bar_w, 8, pct, clr)

        # Rank label
        svg += text(cx + CARD_W // 2, cy + 135, f"RANK {pct}%", 10, TEXT_SEC)

    svg += "</svg>"
    return svg, h


# ── Stats SVG ─────────────────────────────────────────────────
def generate_stats(data):
    h = 300
    svg = svg_header(W, h)
    svg += text(W // 2, 30, "Enterprise Development Analytics", 20, PRIMARY, weight="bold")

    # Left: Stats card
    lx, ly, lw, lh = PAD, 55, 480, 230
    svg += rounded_rect(lx, ly, lw, lh)
    svg += text(lx + lw // 2, ly + 28, f"{data['username']}'s GitHub Stats", 14, PRIMARY, weight="bold")

    stats = [
        ("Star", "Total Stars Earned", data["total_stars"]),
        ("Commit", "Total Commits (2026)", 755),
        ("GitPullRequest", "Total PRs", 2),
        ("Issue", "Total Issues", 4),
        ("People", "Contributed to (last year)", data["total_repos"]),
    ]

    for i, (icon, label, val) in enumerate(stats):
        sy = ly + 55 + i * 32
        svg += text(lx + 20, sy, icon, 12, PRIMARY, "start")
        svg += text(lx + 42, sy, label, 12, TEXT_SEC, "start")
        svg += text(lx + lw - 20, sy, str(val), 13, TEXT, "end", "bold")

    # Grade badge
    svg += f'<circle cx="{lx + lw // 2}" cy="{ly + lh - 25}" r="18" fill="{PRIMARY}" opacity="0.15"/>\n'
    svg += text(lx + lw // 2, ly + lh - 20, "A+", 18, PRIMARY, weight="bold")

    # Right: Languages card
    rx, ry, rw, rh = PAD + lw + GAP, 55, W - PAD * 2 - lw - GAP, 230
    svg += rounded_rect(rx, ry, rw, rh)
    svg += text(rx + rw // 2, ry + 28, "Most Used Languages", 14, PRIMARY, weight="bold")

    total = sum(c for _, c in data["languages"])
    bar_colors = [PRIMARY, SECONDARY, LIGHT, LIGHTER, DARK_ACCENT, "#4a6fa5"]

    for i, (lang, count) in enumerate(data["languages"]):
        pct = (count / total * 100) if total else 0
        ly2 = ry + 55 + i * 30
        svg += text(rx + 20, ly2, lang, 11, TEXT, "start")
        svg += progress_bar(rx + 120, ly2 - 8, rw - 200, 10, pct, bar_colors[i % len(bar_colors)])
        svg += text(rx + rw - 20, ly2, f"{pct:.0f}%", 11, TEXT_SEC, "end")

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
