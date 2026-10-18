#!/usr/bin/env python3
"""Generate truthful GitHub milestones, analytics and Pac-Man activity."""

import datetime
import json
import math
import os
import re
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
from xml.sax.saxutils import escape

BG = "#101526"
SURFACE = "#17243b"
INK = "#f4f7fb"
MUTED = "#b3c7d4"
CYAN = "#62d8e8"
YELLOW = "#ffd36e"
PINK = "#ff8bb7"
ORANGE = "#ffb071"
BLUE = "#8cb4ff"
LEVELS = {
    "NONE": "#203049",
    "FIRST_QUARTILE": "#28608a",
    "SECOND_QUARTILE": "#27a5b5",
    "THIRD_QUARTILE": "#70d7a6",
    "FOURTH_QUARTILE": YELLOW,
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
        '<circle cx="-3" cy="-1" r="1.5" fill="#101526"/>'
        '<circle cx="6" cy="-1" r="1.5" fill="#101526"/>'
    )
    return (
        f'<g transform="translate({x} {y})" fill="{color}">{shape}'
        f'<animateMotion path="M0 0 H{distance}" dur="11s" begin="{delay}s" repeatCount="indefinite"/>'
        "</g>"
    )


ACTIVITY_COLORS = (
    "#263650",  # No contributions.
    "#426cb8",  # 1–2: blue.
    "#20b9cb",  # 3–5: turquoise.
    "#65d694",  # 6–11: green.
    "#ffca62",  # 12+: gold.
)
CYCLE_SECONDS = 38


def activity_band(count):
    if count == 0:
        return 0
    if count <= 2:
        return 1
    if count <= 5:
        return 2
    if count <= 11:
        return 3
    return 4


def ordered_activity_route(weeks, start_x, graph_y, step=18):
    """Visit real nonzero days by count, nearest first only within equal counts."""
    groups = {}
    for week_index, week in enumerate(weeks):
        for day in week["contributionDays"]:
            count = day["contributionCount"]
            if count <= 0:
                continue
            weekday = (datetime.date.fromisoformat(day["date"]).weekday() + 1) % 7
            groups.setdefault(count, []).append({
                "count": count, "date": day["date"],
                "x": start_x + week_index * step + 7,
                "y": graph_y + weekday * step + 7,
            })
    route = []
    current = (start_x + 7, graph_y + 3 * step + 7)
    for count in sorted(groups):
        remaining = groups[count]
        while remaining:
            index = min(
                range(len(remaining)),
                key=lambda item: (
                    (remaining[item]["x"] - current[0]) ** 2 + (remaining[item]["y"] - current[1]) ** 2,
                    remaining[item]["date"],
                ),
            )
            point = remaining.pop(index)
            route.append(point)
            current = (point["x"], point["y"])
    return route


def route_progress(route):
    distances = [0.0]
    for previous, current in zip(route, route[1:]):
        distances.append(distances[-1] + math.hypot(
            current["x"] - previous["x"], current["y"] - previous["y"]
        ))
    total = distances[-1] if distances else 0
    return [distance / total if total else 0 for distance in distances]


def fade_after_arrival(fraction, consumed_opacity):
    """SMIL values share one clock, so every cell resets with Pac-Man."""
    arrival = max(.001, min(fraction, .995))
    after = min(arrival + .002, .998)
    return (
        f'<animate attributeName="opacity" values="1;1;{consumed_opacity};{consumed_opacity};1" '
        f'keyTimes="0;{arrival:.5f};{after:.5f};.999;1" '
        f'dur="{CYCLE_SECONDS}s" repeatCount="indefinite"/>'
    )


def activity_ghost(x, y, color, fraction, animate):
    shape = (
        f'<path d="M-12 11V-2a12 12 0 0 1 24 0v13l-4-3-4 3-4-3-4 3-4-3z" '
        f'fill="{color}" stroke="{BG}" stroke-width="2"/>'
        '<ellipse cx="-4" cy="-2" rx="3" ry="4" fill="#fff"/>'
        '<ellipse cx="5" cy="-2" rx="3" ry="4" fill="#fff"/>'
        f'<circle cx="-3" cy="-1" r="1.5" fill="{BG}"/>'
        f'<circle cx="6" cy="-1" r="1.5" fill="{BG}"/>'
    )
    return f'<g transform="translate({x} {y})">{shape}{fade_after_arrival(fraction, 0) if animate else ""}</g>'


def activity_legend(mobile):
    labels = ["0", "1–2", "3–5", "6–11", "12+"]
    svg = []
    for index, (label, color) in enumerate(zip(labels, ACTIVITY_COLORS)):
        x = (20 + index * 72) if mobile else (40 + index * 135)
        y = 465 if mobile else 429
        svg.append(f'<rect x="{x}" y="{y}" width="13" height="13" rx="3" fill="{color}"/>')
        svg.append(text(x + 20, y + 12, label, 13 if mobile else 15, MUTED))
    return svg


def generate_activity_panel(stats, calendar, mobile=False, animate=True):
    """One activity panel: live metrics and Pac-Man moving inside the real grid."""
    weeks = calendar["weeks"][-18:] if mobile else calendar["weeks"]
    if not weeks or not any(week["contributionDays"] for week in weeks):
        raise ValueError("GitHub returned an empty contribution calendar")
    width, height = (390, 492) if mobile else (max(1060, 84 + len(weeks) * 18), 458)
    days = [day for week in weeks for day in week["contributionDays"]]
    first_date, last_date = days[0]["date"], days[-1]["date"]
    milestones = calendar_milestones(calendar)
    graph_y, start_x, step = (274, 30, 18) if mobile else (240, 42, 18)
    route = ordered_activity_route(weeks, start_x, graph_y, step)
    progress = route_progress(route)
    rank_by_date = {point["date"]: index for index, point in enumerate(route)}
    description = f"{calendar['totalContributions']} contribuciones en el último año. Calendario del {first_date} al {last_date}."
    if route:
        description += " Pac-Man consume la actividad de menor a mayor y devora fantasmas durante el recorrido."
    svg = [
        svg_root(width, height, "Actividad de GitHub de Doker367", description),
        f'<rect width="{width}" height="{height}" fill="{BG}"/>',
    ]
    accents = [CYAN, YELLOW, PINK, BLUE]
    for index, color in enumerate(accents):
        svg.append(f'<rect x="{index * width / 4:.1f}" width="{width / 4:.1f}" height="6" fill="{color}"/>')
    left = 20 if mobile else 40
    svg.append(text(left, 45 if not mobile else 42, "Actividad en GitHub" if not mobile else "Actividad", 32 if not mobile else 29, INK, "bold"))
    if mobile:
        svg.append(text(width - 20, 42, "GITHUB", 13, CYAN, "bold", "end"))
    else:
        svg.append(text(width - 40, 45, "DOKER367  /  ÚLTIMO AÑO", 15, MUTED, "bold", "end"))
    svg.append(text(left, 75 if not mobile else 69, f"{first_date}  —  {last_date}", 15 if not mobile else 13, MUTED))
    metrics = [
        (calendar["totalContributions"], "Contribuciones", CYAN),
        (stats["repositories"], "Repositorios", YELLOW),
        (stats["stars"], "Estrellas", PINK),
        (stats["followers"], "Seguidores", BLUE),
    ]
    for index, (value, label, color) in enumerate(metrics):
        if mobile:
            x, y, size = 20 + (index % 2) * 188, 127 + (index // 2) * 75, 43
        else:
            x, y, size = 40 + index * ((width - 80) / 4), 150, 53
        svg.append(text(f"{x:.1f}", y, f"{value:,}", size, color, "bold"))
        svg.append(text(f"{x:.1f}", y + 26, label, 16 if mobile else 18, MUTED))
    graph_label = ("Pac-Man: menor → mayor" if mobile else "Pac-Man come de menor a mayor") if route else "Sin contribuciones recientes"
    svg.append(text(left, 254 if mobile else 215, graph_label, 17 if mobile else 19, INK, "bold"))
    if not mobile and route:
        svg.append(text(width - 40, 215, "CASILLAS + FANTASMAS", 15, YELLOW, "bold", "end"))
    for week_index, week in enumerate(weeks):
        for day in week["contributionDays"]:
            weekday = (datetime.date.fromisoformat(day["date"]).weekday() + 1) % 7
            x, y = start_x + week_index * step, graph_y + weekday * step
            count = day["contributionCount"]
            band = activity_band(count)
            rank = rank_by_date.get(day["date"])
            cell_animation = fade_after_arrival(progress[rank], 0) if animate and rank is not None else ""
            svg.append(
                f'<rect x="{x}" y="{y}" width="14" height="14" rx="3" '
                f'fill="{ACTIVITY_COLORS[band]}" data-count="{count}">'
                f'<title>{day["date"]}: {count} contribuciones</title>{cell_animation}</rect>'
            )
    if route:
        ghost_indices = sorted({min(len(route) - 1, round((len(route) - 1) * fraction)) for fraction in (.28, .58, .86)})
        for index, color in zip(ghost_indices, (PINK, BLUE, ORANGE)):
            point = route[index]
            svg.append(activity_ghost(point["x"], point["y"], color, progress[index], animate))
        first = route[0]
        svg.append(f'<g transform="translate({first["x"]} {first["y"]})" fill="{YELLOW}">')
        svg.append(f'<circle r="13" stroke="{BG}" stroke-width="2"/>')
        svg.append(f'<path d="M0 0L15-7A16 16 0 0 1 15 7Z" fill="{BG}">')
        if animate:
            svg.append('<animate attributeName="opacity" values="1;0;1" dur=".28s" repeatCount="indefinite"/>')
        svg.append('</path>')
        if animate and len(route) > 1:
            path = "M0 0 " + " ".join(
                f'L{point["x"] - first["x"]} {point["y"] - first["y"]}' for point in route[1:]
            )
            svg.append(f'<animateMotion path="{path}" rotate="auto" dur="{CYCLE_SECONDS}s" repeatCount="indefinite"/>')
        svg.append('</g>')
    else:
        svg.append(f'<circle cx="{start_x + 7}" cy="{graph_y + 3 * step + 7}" r="13" '
                   f'fill="{YELLOW}" stroke="{BG}" stroke-width="2"/>')
    if mobile:
        svg.append(text(20, 421, f"{milestones[1][1]:,} días activos  ·  {milestones[2][1]:,} días de racha", 16, INK))
        svg.append(text(20, 449, f"Máximo: {milestones[3][1]:,} contribuciones en un día", 15, MUTED))
        svg.extend(activity_legend(True))
    else:
        for index, (value, label, color) in enumerate([
            (milestones[1][1], "días activos", CYAN),
            (milestones[2][1], "días de racha", PINK),
            (milestones[3][1], "en un día", YELLOW),
        ]):
            x = 40 + index * ((width - 80) / 3)
            svg.append(text(f"{x:.1f}", 414, f"{value:,}", 24, color, "bold"))
            svg.append(text(f"{x + 43:.1f}", 414, label, 17, INK))
        svg.extend(activity_legend(False))
    svg.append("</svg>")
    return "\n".join(svg)


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
    print(f"Generated GitHub statistics for {username}; the snake is built by the workflow")


if __name__ == "__main__":
    main()
