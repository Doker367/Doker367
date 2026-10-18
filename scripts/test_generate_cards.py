"""Offline checks for the generated profile SVGs."""

import datetime
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch

from generate_cards import (
    PublicCalendarParser, activity_band, calendar_milestones, generate_activity_panel,
    generate_milestones, generate_pacman, generate_stats, generate_stats_mobile,
    get_contributions, get_public_stats, ordered_activity_route,
)


class ProfileAssetTests(unittest.TestCase):
    def test_stats_use_only_returned_numbers(self):
        svg = generate_stats({
            "repositories": 23,
            "stars": 17,
            "followers": 8,
            "languages": [("Python", 4), ("Dart", 2)],
        })
        root = ET.fromstring(svg)
        text = " ".join(node.text or "" for node in root.iter() if node.tag.endswith("text"))
        for value in ("23", "17", "8", "Python", "Dart"):
            self.assertIn(value, text)
        self.assertNotIn("755", text)
        self.assertEqual(ET.fromstring(generate_stats_mobile({
            "repositories": 23, "stars": 17, "followers": 8,
            "languages": [("Python", 4), ("Dart", 2)],
        })).attrib["width"], "390")

    def test_milestones_are_calculated_from_real_calendar_days(self):
        days = [
            {"date": f"2026-10-{day:02d}", "contributionCount": count}
            for day, count in [(11, 0), (12, 2), (13, 3), (14, 0), (15, 4), (16, 1)]
        ]
        calendar = {"weeks": [{"contributionDays": days}], "totalContributions": 10}
        self.assertEqual(calendar_milestones(calendar), [
            ("Contribuciones", 10), ("Días con actividad", 4),
            ("Racha más larga", 2), ("Máximo en un día", 4),
        ])
        for mobile, expected_width in [(False, "1000"), (True, "390")]:
            root = ET.fromstring(generate_milestones(calendar, mobile=mobile))
            self.assertEqual(root.attrib["width"], expected_width)

    def test_pacman_preserves_dates_levels_and_motion(self):
        sunday = datetime.date(2026, 10, 11)
        days = []
        for day in range(7):
            date = sunday + datetime.timedelta(days=day)
            days.append({
                "date": date.isoformat(),
                "contributionCount": day,
                "contributionLevel": "NONE" if day == 0 else "FOURTH_QUARTILE",
            })
        svg = generate_pacman({"weeks": [{"contributionDays": days}], "totalContributions": 21})
        root = ET.fromstring(svg)
        self.assertEqual(len(root.findall(".//{http://www.w3.org/2000/svg}animateMotion")), 4)
        self.assertIn("2026-10-11: 0 contribuciones", svg)
        self.assertIn("2026-10-17: 6 contribuciones", svg)
        self.assertIn("21 contribuciones", svg)
        mobile = generate_pacman({"weeks": [{"contributionDays": days}], "totalContributions": 21}, mobile=True)
        self.assertEqual(ET.fromstring(mobile).attrib["width"], "390")
        self.assertIn("21 aportes", mobile)

    def test_one_panel_places_pacman_inside_real_contribution_grid(self):
        sunday = datetime.date(2026, 6, 14)
        weeks = []
        for week in range(18):
            weeks.append({"contributionDays": [
                {
                    "date": (sunday + datetime.timedelta(days=week * 7 + day)).isoformat(),
                    "contributionCount": 1 + week % 4 if day == 3 else 0,
                    "contributionLevel": "FIRST_QUARTILE" if day == 3 else "NONE",
                }
                for day in range(7)
            ]})
        calendar = {"weeks": weeks, "totalContributions": 43}
        stats = {"repositories": 45, "stars": 7, "followers": 55}
        self.assertEqual([activity_band(n) for n in (0, 1, 2, 3, 5, 6, 11, 12)],
                         [0, 1, 1, 2, 2, 3, 3, 4])
        for mobile, expected_width in [(False, "1060"), (True, "390")]:
            graph_y, start_x = (274, 30) if mobile else (240, 42)
            route = ordered_activity_route(weeks, start_x, graph_y)
            self.assertEqual([point["count"] for point in route], sorted(point["count"] for point in route))
            svg = generate_activity_panel(stats, calendar, mobile=mobile)
            root = ET.fromstring(svg)
            self.assertEqual(root.attrib["width"], expected_width)
            self.assertIn(f'translate({route[0]["x"]} {route[0]["y"]})', svg)
            self.assertIn("2026-06-17: 1 contribuciones", svg)
            motion = root.findall(".//{http://www.w3.org/2000/svg}animateMotion")
            self.assertEqual(len(motion), 1)
            self.assertEqual(motion[0].attrib["rotate"], "auto")
            self.assertEqual(len(root.findall(".//{http://www.w3.org/2000/svg}animate")), 22)
            self.assertNotIn('y="81" width=', svg)
            static = ET.fromstring(generate_activity_panel(stats, calendar, mobile=mobile, animate=False))
            self.assertFalse(static.findall(".//{http://www.w3.org/2000/svg}animateMotion"))
            self.assertFalse(static.findall(".//{http://www.w3.org/2000/svg}animate"))

    def test_empty_activity_has_no_false_ghost_encounters(self):
        days = [{
            "date": (datetime.date(2026, 10, 11) + datetime.timedelta(days=day)).isoformat(),
            "contributionCount": 0, "contributionLevel": "NONE",
        } for day in range(7)]
        svg = generate_activity_panel(
            {"repositories": 0, "stars": 0, "followers": 0},
            {"weeks": [{"contributionDays": days}], "totalContributions": 0},
        )
        root = ET.fromstring(svg)
        self.assertIn("Sin contribuciones recientes", svg)
        self.assertFalse(root.findall(".//{http://www.w3.org/2000/svg}animateMotion"))

    def test_public_calendar_tooltips_supply_real_counts(self):
        parser = PublicCalendarParser()
        parser.feed('''<td id="a" data-date="2026-10-11" data-level="0"></td>
            <tool-tip for="a">No contributions on October 11th.</tool-tip>
            <td id="b" data-date="2026-10-12" data-level="3"></td>
            <tool-tip for="b">12 contributions on October 12th.</tool-tip>''')
        self.assertEqual(parser.days["a"]["contributionCount"], 0)
        self.assertEqual(parser.days["b"]["contributionCount"], 12)
        with patch("generate_cards.request_json", side_effect=ValueError("API unavailable")), patch(
            "generate_cards.get_public_calendar", return_value={"totalContributions": 12}
        ) as fallback:
            self.assertEqual(get_contributions("Doker367", "token")["totalContributions"], 12)
        fallback.assert_called_once_with("Doker367")

    def test_repository_stats_ignore_forks_and_follow_pagination(self):
        first_page = [{"fork": True, "stargazers_count": 50, "language": "Go"}] + [
            {"fork": False, "stargazers_count": 1, "language": "Python"} for _ in range(99)
        ]
        responses = [
            {"public_repos": 101, "followers": 9},
            first_page,
            [{"fork": False, "stargazers_count": 2, "language": "Dart"}],
        ]
        with patch("generate_cards.request_json", side_effect=responses) as request:
            stats = get_public_stats("Doker367", "token")
        self.assertEqual(request.call_count, 3)
        self.assertEqual(stats["stars"], 101)
        self.assertEqual(stats["languages"], [("Python", 99), ("Dart", 1)])


if __name__ == "__main__":
    unittest.main()
