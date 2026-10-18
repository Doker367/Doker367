#!/usr/bin/env python3
"""Draw the profile wordmark as font outlines for reliable GitHub rendering."""

from pathlib import Path
from xml.sax.saxutils import escape

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
FONT = ROOT / "assets/fonts/PirataOne-Regular.ttf"
OUTPUT = ROOT / "assets/header.svg"
FOOTER = ROOT / "assets/footer.svg"


def outlined_text(font, text, max_width=916, height=145, left=42, baseline=188):
    glyphs = font.getGlyphSet()
    cmap = font.getBestCmap()
    units = font["head"].unitsPerEm
    advances = font["hmtx"].metrics
    glyph_names = [cmap[ord(character)] for character in text]
    width = sum(advances[name][0] for name in glyph_names)
    scale = min(height / units, max_width / width)
    x = left + (max_width - width * scale) / 2
    result = []
    for name in glyph_names:
        pen = SVGPathPen(glyphs)
        glyphs[name].draw(pen)
        path = pen.getCommands()
        if path:
            result.append(
                f'<path d="{escape(path)}" transform="translate({x:.2f} {baseline}) '
                f'scale({scale:.6f} {-scale:.6f})"/>'
            )
        x += advances[name][0] * scale
    return "\n    ".join(result)


def main():
    font = TTFont(FONT)
    lettering = outlined_text(font, "DOKER 367")
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="310" viewBox="0 0 1000 310" role="img" aria-labelledby="title description">
  <title id="title">DOKER 367</title>
  <desc id="description">Lettering gótico para el perfil de Doker367, desarrollador full stack en México.</desc>
  <rect width="1000" height="310" fill="#101820"/>
  <rect width="1000" height="7" fill="#39d5dc"/>
  <g fill="#f0f5f3">
    {lettering}
  </g>
  <text x="500" y="237" fill="#a9c4c9" font-family="Arial, Helvetica, sans-serif" font-size="21" text-anchor="middle">Full Stack Developer · México</text>
  <text x="500" y="274" fill="#39d5dc" font-family="Arial, Helvetica, sans-serif" font-size="17" text-anchor="middle">Sistemas seguros · Productos útiles · Inteligencia aplicada</text>
</svg>
'''
    OUTPUT.write_text(svg, encoding="utf-8")
    footer_lettering = outlined_text(font, "DOKER 367", max_width=770, height=93, left=115, baseline=118)
    footer = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="174" viewBox="0 0 1000 174" role="img" aria-labelledby="title description">
  <title id="title">DOKER 367</title>
  <desc id="description">Construir, aprender, compartir.</desc>
  <rect width="1000" height="174" fill="#dceef0"/>
  <g fill="#101820">
    {footer_lettering}
  </g>
  <text x="500" y="151" fill="#245660" font-family="Arial, Helvetica, sans-serif" font-size="17" text-anchor="middle">Construir · Aprender · Compartir</text>
</svg>
'''
    FOOTER.write_text(footer, encoding="utf-8")
    print(f"Wrote {OUTPUT} and {FOOTER}")


if __name__ == "__main__":
    main()
