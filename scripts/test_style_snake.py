"""Checks for the visual treatment applied to generated snake SVGs."""

import unittest
import xml.etree.ElementTree as ET

from style_snake import PALETTES, style_snake


SAMPLE = (
    '<svg viewBox="-16 -32 880 192" width="880" height="192" '
    'xmlns="http://www.w3.org/2000/svg">'
    '<desc>Generated with https://github.com/Platane/snk</desc>'
    '<style>:root{--cb:#000;--cs:#fff;--ce:#111;--c0:#111;--c1:#222}'
    '.c.c0{fill:var(--c1);animation-name:c0}'
    '.u.u0{fill:var(--c1);animation-name:u0}'
    '@keyframes c0{50%{opacity:0}}</style>'
    '<rect class="c c0" x="2" y="2"/>'
    '<rect class="u u0" x="0" y="144"/>'
    '<rect class="s s0" x="0" y="0"/>'
    '<rect class="s s1" x="16" y="0"/>'
    '</svg>'
)


class SnakeStyleTests(unittest.TestCase):
    def test_light_and_dark_preserve_motion_and_contribution_cells(self):
        for name, palette in PALETTES.items():
            with self.subTest(theme=name):
                styled = style_snake(SAMPLE, palette)
                self.assertEqual(style_snake(styled, palette), styled)
                root = ET.fromstring(styled)
                rects = root.findall('{http://www.w3.org/2000/svg}rect')
                self.assertEqual(len(rects), 5)
                self.assertEqual(rects[0].get('fill'), palette['background'])
                self.assertEqual(rects[1].get('fill'), palette['c1'])
                self.assertEqual(rects[2].get('fill'), palette['c1'])
                self.assertEqual(rects[3].get('fill'), palette['cs'])
                self.assertEqual(rects[4].get('fill'), palette['s1'])
                self.assertIn('@keyframes c0{50%{opacity:0}}', styled)
                self.assertIn('prefers-reduced-motion: reduce', styled)

    def test_rejects_unexpected_svg_instead_of_silently_replacing_it(self):
        with self.assertRaises(ValueError):
            style_snake('<svg/>', PALETTES['github-snake.svg'])


if __name__ == '__main__':
    unittest.main()
