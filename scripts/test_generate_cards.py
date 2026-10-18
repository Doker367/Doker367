"""Offline checks for the generated profile SVGs."""

import datetime
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch

from generate_cards import (
    PublicCalendarParser, calendar_milestones, generate_milestones, generate_pacman,
    generate_stats, generate_stats_mobile, get_contributions, get_public_stats,
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
