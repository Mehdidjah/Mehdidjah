"""Use May 2, 2020 as the owner's requested contribution tracking start.

The streak action must fetch starting_year=2020 first. GitHub currently reports
May 14, 2020 as the earliest recorded contribution; there are no contributions
before May 2 in that year's public calendar. Extending the displayed period back
to May 2 therefore keeps the provider's total and streak calculations accurate.
Reject a truncated history or contributions preceding the requested period.
"""

from datetime import date, datetime
from pathlib import Path
import re
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
START = date(2020, 5, 2)
SVG = "{http://www.w3.org/2000/svg}"
ET.register_namespace("", SVG[1:-1])
ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")


def set_period(path: Path) -> bytes:
    root = ET.parse(path).getroot()
    if root.tag != f"{SVG}svg":
        raise ValueError(f"{path}: expected an SVG")
    ranges = [node for node in root.iter(f"{SVG}text")
              if re.fullmatch(r"[A-Z][a-z]{2} \d{1,2}, \d{4} - Present", "".join(node.itertext()).strip())]
    if len(ranges) != 1:
        raise ValueError(f"{path}: expected exactly one contribution period")
    displayed_date = "".join(ranges[0].itertext()).strip().removesuffix(" - Present")
    first = (date.fromisoformat(root.attrib["data-first-contribution"])
             if "data-first-contribution" in root.attrib
             else datetime.strptime(displayed_date, "%b %d, %Y").date())
    if first.year != START.year:
        raise ValueError(f"{path}: missing the verified 2020 history; generate with starting_year=2020")
    if first < START:
        raise ValueError(f"{path}: contributions before May 2 must be excluded from the total before relabelling")
    root.set("data-contributions-start", START.isoformat())
    root.set("data-first-contribution", first.isoformat())
    ranges[0].text = "May 2, 2020 - Present"
    description = root.find(f"{SVG}desc")
    if description is None:
        description = ET.Element(f"{SVG}desc")
        root.insert(0, description)
    description.text = (
        "GitHub contributions for the selected period, May 2, 2020 to present. "
        f"The earliest recorded contribution returned by GitHub is {first.isoformat()}."
    )
    result = ET.tostring(root, encoding="unicode")
    return ("\n".join(line.rstrip() for line in result.splitlines()).rstrip() + "\n").encode()


if __name__ == "__main__":
    paths = [ROOT / "assets" / f"streak-{theme}.svg" for theme in ("dark", "light")]
    cards = [set_period(path) for path in paths]
    for path, contents in zip(paths, cards):
        path.write_bytes(contents)
    print("Set contribution period to May 2, 2020 - Present, retaining verified history.")
