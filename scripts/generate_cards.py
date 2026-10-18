#!/usr/bin/env python3
"""Generate truthful GitHub milestones, analytics and Pac-Man activity."""

import datetime
import json
import os
import re
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
from xml.sax.saxutils import escape

BG = "#101820"
SURFACE = "#17242d"
INK = "#f0f5f3"
MUTED = "#a9c4c9"
CYAN = "#39d5dc"
YELLOW = "#f8d465"
PINK = "#ff83a6"
ORANGE = "#ffab70"
BLUE = "#83b8ff"
LEVELS = {
    "NONE": "#24343d",
    "FIRST_QUARTILE": "#245660",
    "SECOND_QUARTILE": "#278790",
    "THIRD_QUARTILE": "#32b5bd",
    "FOURTH_QUARTILE": CYAN,
}


def request_json(url, token=None, payload=None):
    headers = {"User-Agent": "Doker367-profile-assets", "Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        headers["Content-Type"] = "application/json"
    request = Request(url, headers=headers, data=json.dumps(payload).encode() if payload else None)
    with urlopen(request, timeout=25) as response:
        return json.load(response)


def get_public_stats(username, token):
    user = request_json(f"https://api.github.com/users/{quote(username)}", token)
    stars = 0
    languages = Counter()
    page = 1
    while True:
        repos = request_json(
            f"https://api.github.com/users/{quote(username)}/repos?per_page=100&page={page}&type=owner",
            token,
        )
        if not isinstance(repos, list):
            raise ValueError("GitHub did not return a repository list")
        for repo in repos:
            if repo.get("fork"):
                continue
            stars += repo.get("stargazers_count", 0)
            if repo.get("language"):
                languages[repo["language"]] += 1
        if len(repos) < 100:
            break
        page += 1
    return {
        "repositories": user["public_repos"],
        "stars": stars,
        "followers": user["followers"],
        "languages": languages.most_common(5),
    }


class PublicCalendarParser(HTMLParser):
    """Read the public contribution table and its accessible daily tooltips."""

    def __init__(self):
        super().__init__()
        self.days = {}
        self.current_tooltip = None
        self.tooltip_text = []

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == "td" and attrs.get("data-date") and attrs.get("data-level"):
            self.days[attrs["id"]] = {
                "date": attrs["data-date"], "level": int(attrs["data-level"]),
            }
        elif tag == "tool-tip" and attrs.get("for") in self.days:
            self.current_tooltip = attrs["for"]
            self.tooltip_text = []

    def handle_data(self, data):
        if self.current_tooltip:
            self.tooltip_text.append(data)

    def handle_endtag(self, tag):
        if tag != "tool-tip" or not self.current_tooltip:
            return
        label = "".join(self.tooltip_text).strip()
        match = re.match(r"(\d+) contributions? on |No contributions on ", label)
        if match:
            self.days[self.current_tooltip]["contributionCount"] = int(match.group(1) or 0)
        self.current_tooltip = None


def get_public_calendar(username):
    url = f"https://github.com/users/{quote(username)}/contributions"
    request = Request(url, headers={"User-Agent": "Doker367-profile-assets"})
    with urlopen(request, timeout=25) as response:
        html = response.read().decode("utf-8")
    parser = PublicCalendarParser()
    parser.feed(html)
    days = sorted(parser.days.values(), key=lambda day: day["date"])
    if len(days) < 350 or any("contributionCount" not in day for day in days):
        raise ValueError("The public GitHub calendar could not be parsed safely")
    levels = ["NONE", "FIRST_QUARTILE", "SECOND_QUARTILE", "THIRD_QUARTILE", "FOURTH_QUARTILE"]
    weeks = []
    for day in days:
        day["contributionLevel"] = levels[day.pop("level")]
        week_start = datetime.date.fromisoformat(day["date"])
        week_start -= datetime.timedelta(days=(week_start.weekday() + 1) % 7)
        if not weeks or weeks[-1]["start"] != week_start:
            weeks.append({"start": week_start, "contributionDays": []})
        weeks[-1]["contributionDays"].append(day)
    return {
        "totalContributions": sum(day["contributionCount"] for day in days),
        "weeks": [{"contributionDays": week["contributionDays"]} for week in weeks],
    }


def get_contributions(username, token):
    if not token:
        return get_public_calendar(username)
    query = """query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks { contributionDays { date contributionCount contributionLevel } }
          }
        }
      }
    }"""
    try:
        response = request_json(
            "https://api.github.com/graphql", token, {"query": query, "variables": {"login": username}}
        )
        if response.get("errors"):
            raise ValueError(f"GitHub GraphQL error: {response['errors']}")
        user = response.get("data", {}).get("user")
        if not user:
            raise ValueError(f"GitHub user {username!r} was not found")
        return user["contributionsCollection"]["contributionCalendar"]
    except (HTTPError, URLError, ValueError, KeyError) as error:
        print(f"GraphQL calendar unavailable ({error}); using the public calendar")
        return get_public_calendar(username)


def svg_root(width, height, title, description):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title description">'
        f'<title id="title">{escape(title)}</title>'
        f'<desc id="description">{escape(description)}</desc>'
    )


def text(x, y, value, size=18, color=INK, weight="normal", anchor="start"):
    return (
        f'<text x="{x}" y="{y}" fill="{color}" font-family="Arial, Helvetica, sans-serif" '
        f'font-size="{size}" font-weight="{weight}" text-anchor="{anchor}">{escape(str(value))}</text>'
    )


def calendar_milestones(calendar):
    days = sorted(
        (day for week in calendar["weeks"] for day in week["contributionDays"]),
        key=lambda day: day["date"],
    )
    active = sum(day["contributionCount"] > 0 for day in days)
    peak = max((day["contributionCount"] for day in days), default=0)
    streak = longest_streak = 0
    previous_date = None
    for day in days:
        date = datetime.date.fromisoformat(day["date"])
        if day["contributionCount"] > 0:
            streak = streak + 1 if previous_date and date - previous_date == datetime.timedelta(days=1) else 1
            longest_streak = max(longest_streak, streak)
        else:
            streak = 0
        previous_date = date
    return [
        ("Contribuciones", calendar["totalContributions"]),
        ("Días con actividad", active),
        ("Racha más larga", longest_streak),
        ("Máximo en un día", peak),
    ]


def generate_milestones(calendar, mobile=False):
    width, height = (390, 294) if mobile else (1000, 226)
    svg = [
        svg_root(width, height, "GitHub Milestones", "Hitos calculados con el calendario real de contribuciones del último año."),
        f'<rect width="{width}" height="{height}" fill="{BG}"/>',
        text(24 if mobile else 36, 43, "Hitos del último año", 25 if mobile else 30, INK, "bold"),
    ]
    for index, (label, value) in enumerate(calendar_milestones(calendar)):
        if mobile:
            x, y = 24 + (index % 2) * 184, 111 + (index // 2) * 92
        else:
            x, y = 36 + index * 244, 137
        svg.append(text(x, y, f"{value:,}", 40 if mobile else 61, CYAN, "bold"))
        svg.append(text(x, y + 27, label, 15 if mobile else 18, MUTED))
    svg.append(text(24 if mobile else 36, height - 14, "Datos del calendario público de GitHub", 14 if mobile else 16, MUTED))
    svg.append("</svg>")
    return "\n".join(svg)


def generate_stats(stats):
    svg = [svg_root(1000, 248, "GitHub en cifras", "Repositorios públicos, estrellas y seguidores obtenidos de la API de GitHub.")]
    svg += [f'<rect width="1000" height="248" fill="{BG}"/>', text(36, 48, "GitHub en cifras", 30, INK, "bold")]
    items = [
        ("Repositorios públicos", stats["repositories"]),
        ("Estrellas recibidas", stats["stars"]),
        ("Seguidores", stats["followers"]),
    ]
    for index, (label, value) in enumerate(items):
        x = 36 + index * 326
        svg.append(text(x, 130, value, 62, CYAN, "bold"))
        svg.append(text(x, 161, label, 18, MUTED))
    language_list = ", ".join(name for name, _ in stats["languages"]) or "Sin lenguajes públicos detectados"
    svg.append(text(36, 218, f"Lenguajes de repositorios: {language_list}", 17, INK))
    svg.append("</svg>")
    return "\n".join(svg)


def generate_stats_mobile(stats):
    svg = [svg_root(390, 338, "GitHub en cifras", "Repositorios, estrellas y seguidores públicos de Doker367.")]
    svg += [f'<rect width="390" height="338" fill="{BG}"/>', text(24, 42, "GitHub en cifras", 27, INK, "bold")]
    items = [
        ("Repositorios públicos", stats["repositories"]),
        ("Estrellas recibidas", stats["stars"]),
        ("Seguidores", stats["followers"]),
    ]
    for index, (label, value) in enumerate(items):
        y = 105 + index * 76
        svg.append(text(24, y, value, 43, CYAN, "bold"))
        svg.append(text(119, y - 7, label, 19, INK))
    languages = ", ".join(name for name, _ in stats["languages"][:3]) or "Sin datos públicos"
    svg.append(text(24, 318, f"Lenguajes: {languages}", 16, MUTED))
    svg.append("</svg>")
    return "\n".join(svg)


def ghost(x, y, color, delay, distance):
    # The dark eye pupils make the characters legible on both GitHub themes.
    shape = (
        '<path d="M-12 11V-2a12 12 0 0 1 24 0v13l-4-3-4 3-4-3-4 3-4-3z"/>'
        '<ellipse cx="-4" cy="-2" rx="3" ry="4" fill="#fff"/>'
        '<ellipse cx="5" cy="-2" rx="3" ry="4" fill="#fff"/>'
        '<circle cx="-3" cy="-1" r="1.5" fill="#17242d"/>'
        '<circle cx="6" cy="-1" r="1.5" fill="#17242d"/>'
    )
    return (
        f'<g transform="translate({x} {y})" fill="{color}">{shape}'
        f'<animateMotion path="M0 0 H{distance}" dur="11s" begin="{delay}s" repeatCount="indefinite"/>'
        "</g>"
    )


def generate_pacman(calendar, mobile=False):
    weeks = calendar["weeks"][-18:] if mobile else calendar["weeks"]
    if not weeks or not any(week["contributionDays"] for week in weeks):
        raise ValueError("GitHub returned an empty contribution calendar")
    width = 390 if mobile else max(1000, 74 + len(weeks) * 18)
    height = 294
    left = 24 if mobile else 42
    start_x, start_y = (32 if mobile else 42), 136
    all_days = [day for week in weeks for day in week["contributionDays"]]
    first_date, last_date = all_days[0]["date"], all_days[-1]["date"]
    total = sum(day["contributionCount"] for day in all_days) if mobile else calendar["totalContributions"]
    svg = [
        svg_root(
            width, height,
            "Pac-Man en mi actividad de GitHub",
            f"Calendario real de contribuciones del {first_date} al {last_date}: {total} contribuciones. Pac-Man y tres fantasmas recorren la cuadrícula.",
        ),
        f'<rect width="{width}" height="{height}" fill="{BG}"/>',
        text(left, 43, "Actividad reciente" if mobile else "Un año de código", 24 if mobile else 30, INK, "bold"),
        text(width - left, 43, f"{total:,} aportes" if mobile else f"{total:,} contribuciones", 15 if mobile else 19, CYAN, anchor="end"),
        text(left, 72, f"{first_date}  —  {last_date}", 14 if mobile else 16, MUTED),
    ]
    # A short arcade lane makes the moving characters visible without obscuring real data.
    svg.append(f'<rect x="{left}" y="81" width="{width - left * 2}" height="39" rx="4" fill="{SURFACE}"/>')
    travel = width - 210
    for x in range(160, width - 70, 25):
        arrival = (x - 135) / travel * 11
        svg.append(
            f'<circle cx="{x}" cy="100" r="2.3" fill="{YELLOW}" opacity=".75">'
            f'<animate attributeName="opacity" values=".75;0;0;.75" '
            f'keyTimes="0;.015;.95;1" begin="{arrival:.2f}s" dur="11s" repeatCount="indefinite"/>'
            '</circle>'
        )
    svg.append(ghost(98, 100, PINK, 0, travel))
    svg.append(ghost(68, 100, BLUE, 0, travel))
    svg.append(ghost(38, 100, ORANGE, 0, travel))
    svg.append(
        f'<g transform="translate(135 100)" fill="{YELLOW}">'
        '<circle r="13"/>'
        f'<path d="M0 0L14-7A15 15 0 0 1 14 7Z" fill="{SURFACE}">'
        '<animate attributeName="opacity" values="1;0;1" dur=".28s" repeatCount="indefinite"/>'
        '</path>'
        f'<animateMotion path="M0 0 H{width - 210}" dur="11s" repeatCount="indefinite"/>'
        '</g>'
    )
    for week_index, week in enumerate(weeks):
        for day in week["contributionDays"]:
            # GraphQL weeks may begin or end partway through a calendar week.
            weekday = (datetime.date.fromisoformat(day["date"]).weekday() + 1) % 7
            x, y = start_x + week_index * 18, start_y + weekday * 18
            level = day["contributionLevel"]
            if level not in LEVELS:
                raise ValueError(f"Unknown contribution level: {level}")
            svg.append(
                f'<rect x="{x}" y="{y}" width="14" height="14" rx="3" fill="{LEVELS[level]}">'
                f'<title>{day["date"]}: {day["contributionCount"]} contribuciones</title></rect>'
            )
    svg.append(text(left, 281, "Dom · Lun · Mar · Mié · Jue · Vie · Sáb", 12 if mobile else 15, MUTED))
    if not mobile:
        svg.append(text(width - 42, 281, "Menos actividad     ▪  ▪  ▪  ▪  Más actividad", 15, MUTED, anchor="end"))
    svg.append("</svg>")
    return "\n".join(svg)


def main():
    username = os.environ.get("GITHUB_USER", "Doker367")
    token = os.environ.get("GITHUB_TOKEN")
    out_dir = Path(os.environ.get("OUT_DIR", "dist"))
    stats = get_public_stats(username, token)
    calendar = get_contributions(username, token)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "milestones.svg").write_text(generate_milestones(calendar), encoding="utf-8")
    (out_dir / "milestones-mobile.svg").write_text(generate_milestones(calendar, mobile=True), encoding="utf-8")
    (out_dir / "stats.svg").write_text(generate_stats(stats), encoding="utf-8")
    (out_dir / "stats-mobile.svg").write_text(generate_stats_mobile(stats), encoding="utf-8")
    (out_dir / "pacman.svg").write_text(generate_pacman(calendar), encoding="utf-8")
    (out_dir / "pacman-mobile.svg").write_text(generate_pacman(calendar, mobile=True), encoding="utf-8")
    print(f"Generated real GitHub stats and {calendar['totalContributions']} contributions for {username}")


if __name__ == "__main__":
    main()
