"""Build the README's monochrome tech grid without fetching external assets.

Run from any directory: python3 scripts/build-tech-stack.py
Edit STACK below to change categories or labels.
"""

from copy import deepcopy
from html import escape
import json
from pathlib import Path
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
STACK = [
    ("FRONTEND", [("REACT", "react"), ("NEXT.JS", "nextdotjs"),
                  ("TYPESCRIPT", "typescript"), ("SVELTE", "svelte"), ("VUE", "vuedotjs"),
                  ("ASTRO", "astro")]),
    ("STYLING", [("TAILWIND", "tailwindcss"), ("CSS", "css"), ("FIGMA", "figma")]),
    ("BACKEND", [("NODE.JS", "nodedotjs"), ("NESTJS", "nestjs"),
                 ("EXPRESS", "express"), ("TRPC", "trpc"),
                 ("RUST", "rust"), ("C", "c"), ("JAVA", "openjdk")]),
    ("DATABASE", [("POSTGRESQL", "postgresql"), ("MYSQL", "mysql"), ("PRISMA", "prisma"),
                  ("REDIS", "redis"), ("DRIZZLE", "drizzle")]),
    ("PAYMENTS", [("STRIPE", "stripe"), ("CHARGILY", "chargily")]),
    ("MOBILE", [("SWIFT", "swift"), ("FLUTTER", "flutter"), ("XCODE", "xcode")]),
]
THEMES = {
    "dark": {"background": "#0D1117", "border": "#30363D", "label": "#ADB5BD",
             "heading": "#8B949E", "icon": "#B7BEC6"},
    "light": {"background": "#FFFFFF", "border": "#D1D9E0", "label": "#47515C",
              "heading": "#59636E", "icon": "#4A5560"},
}
LAYOUTS = {
    "desktop": {"columns": 6, "cell_width": 156, "font_size": 13, "icon_size": 28},
    "tablet": {"columns": 3, "cell_width": 200, "font_size": 14, "icon_size": 30},
    "mobile": {"columns": 2, "cell_width": 210, "font_size": 15, "icon_size": 32},
}


def render_icon(source: str, x: int, y: int, size: int, color: str) -> str:
    icon = deepcopy(ET.fromstring(source))
    # The source logos contain their own viewBoxes and vector paths. Keep those
    # geometries, but inherit one ink color for a consistent monochrome grid.
    for node in icon.iter():
        node.tag = node.tag.split("}")[-1]
        for attr in ("fill", "stroke"):
            if attr in node.attrib and node.attrib[attr] != "none":
                node.attrib[attr] = "currentColor"
    for child in list(icon):
        if child.tag == "title":
            icon.remove(child)
    icon.attrib.update({"x": str(x), "y": str(y), "width": str(size), "height": str(size),
                        "fill": "currentColor", "color": color, "aria-hidden": "true"})
    return ET.tostring(icon, encoding="unicode")


def render_grid(theme: dict, layout: dict, icons: dict) -> str:
    columns = layout["columns"]
    cell_width = layout["cell_width"]
    width = columns * cell_width
    rows = [STACK[start:start + columns] for start in range(0, len(STACK), columns)]
    heights = [42 + 24 + max(len(items) for _, items in row) * 58 for row in rows]
    height = sum(heights)
    description = "; ".join(f"{category}: {', '.join(label for label, _ in items)}"
                            for category, items in STACK)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title description">',
        '<title id="title">Mehdi’s tech stack</title>',
        f'<desc id="description">{escape(description)}</desc>',
        f'<rect width="{width}" height="{height}" fill="{theme["background"]}"/>',
        f'<g fill="none" stroke="{theme["border"]}" stroke-width="1">',
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}"/>',
    ]
    y = 0
    for row_height in heights:
        if y:
            parts.append(f'<path d="M0 {y + 0.5}H{width}"/>')
        parts.append(f'<path d="M0 {y + 42.5}H{width}"/>')
        for column in range(1, columns):
            x = column * cell_width + 0.5
            parts.append(f'<path d="M{x} {y}V{y + row_height}"/>')
        y += row_height
    parts.append('</g>')
    parts.append('<g font-family="Menlo, Monaco, Consolas, Liberation Mono, monospace">')
    y = 0
    for row, row_height in zip(rows, heights):
        for column, (category, entries) in enumerate(row):
            x = column * cell_width
            parts.append(f'<text x="{x + 16}" y="{y + 26}" fill="{theme["heading"]}" '
                         f'font-size="12" letter-spacing="1.2">{category}</text>')
            for index, (label, slug) in enumerate(entries):
                center = y + 80 + index * 58
                size = layout["icon_size"]
                parts.append(render_icon(icons[slug]["svg"], x + 16,
                                         center - size // 2, size, theme["icon"]))
                parts.append(f'<text x="{x + size + 28}" y="{center + 4.5}" '
                             f'fill="{theme["label"]}" font-size="{layout["font_size"]}" '
                             f'letter-spacing="0.65">{escape(label)}</text>')
        y += row_height
    parts.append('</g></svg>')
    return '\n'.join(parts) + '\n'


def main() -> None:
    icons = json.loads((ROOT / "scripts/tech-stack-icons.json").read_text())
    for theme_name, theme in THEMES.items():
        for layout_name, layout in LAYOUTS.items():
            suffix = "" if layout_name == "desktop" else f"-{layout_name}"
            output = ROOT / "assets" / f"tech-stack-{theme_name}{suffix}.svg"
            output.write_text(render_grid(theme, layout, icons))
            print(f"Built {output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
