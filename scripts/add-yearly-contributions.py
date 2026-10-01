"""Add the public profile calendar total to the generated stats cards.

GitHub's calendar includes private contribution counts the owner has chosen to
share. The stats provider's commit count covers public commits only. Fetch the
calendar without authentication so the published total matches a profile visitor's
view; never infer private commits from the aggregate contribution count.
"""

import argparse
from datetime import date, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
SVG = "{http://www.w3.org/2000/svg}"
ET.register_namespace("", SVG[1:-1])


def calendar_url(year: int) -> str:
    return f"https://github.com/users/Mehdidjah/contributions?from={year}-01-01&to={year}-12-31"


class CalendarParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.headings = []
        self.dates = {}
        self.tooltips = {}
        self.heading = None
        self.tooltip_id = None
        self.tooltip = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "h2":
            self.heading = []
        if "data-date" in attrs and "id" in attrs:
            self.dates[attrs["id"]] = date.fromisoformat(attrs["data-date"])
        if tag == "tool-tip":
            self.tooltip_id = attrs.get("for")
            self.tooltip = []

    def handle_data(self, data):
        if self.heading is not None:
            self.heading.append(data)
        if self.tooltip_id is not None:
            self.tooltip.append(data)

    def handle_endtag(self, tag):
        if tag == "h2" and self.heading is not None:
            self.headings.append(" ".join("".join(self.heading).split()))
            self.heading = None
        if tag == "tool-tip" and self.tooltip_id is not None:
            self.tooltips[self.tooltip_id] = " ".join("".join(self.tooltip).split())
            self.tooltip_id = None


def parse_calendar(html: str, year: int) -> int:
    parser = CalendarParser()
    parser.feed(html)
    totals = [
        int(match.group(1).replace(",", ""))
        for heading in parser.headings
        if (match := re.fullmatch(rf"([\d,]+) contributions? in {year}", heading))
    ]
    if len(totals) != 1:
        raise ValueError("Missing or ambiguous calendar-year contribution total")

    first, end = date(year, 1, 1), date(year + 1, 1, 1)
    expected = {first + timedelta(days=offset) for offset in range((end - first).days)}
    if set(parser.dates.values()) != expected or len(parser.dates) != len(expected):
        raise ValueError("GitHub did not return the complete requested calendar year")
    counts = []
    for identifier in parser.dates:
        text = parser.tooltips.get(identifier, "")
        match = re.match(r"(No|[\d,]+) contributions? on ", text)
        if not match:
            raise ValueError("Missing daily contribution count")
        counts.append(0 if match.group(1) == "No" else int(match.group(1).replace(",", "")))
    if sum(counts) != totals[0]:
        raise ValueError("The calendar headline and daily contribution counts disagree")
    return totals[0]


def fetch_contributions(year: int) -> int:
    request = urllib.request.Request(calendar_url(year), headers={
        "User-Agent": "Mehdidjah-profile-stats",
        "Accept-Language": "en-US,en;q=0.9",
    })
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return parse_calendar(response.read().decode("utf-8"), year)
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("Unable to fetch GitHub contributions")


def update_card(path: Path, year: int, contributions: int) -> bytes:
    root = ET.parse(path).getroot()
    if root.tag != f"{SVG}svg":
        raise ValueError(f"{path}: expected an SVG")
    nodes = {node.attrib["data-testid"]: node for node in root.iter() if "data-testid" in node.attrib}
    if f"{year} snapshot" not in "".join(nodes["header"].itertext()):
        raise ValueError(f"{path}: incorrect card year")
    text = " ".join("".join(node.itertext()) for node in root.iter(f"{SVG}text"))
    if not re.search(rf"(?:Total Commits|Public commits) \({year}\)", text):
        raise ValueError(f"{path}: incorrect commit year")
    metrics = {}
    for key in ("commits", "stars", "prs", "issues", "contribs"):
        value = "".join(nodes[key].itertext()).strip()
        if not re.fullmatch(r"[\d,]+", value):
            raise ValueError(f"{path}: invalid {key}")
        metrics[key] = int(value.replace(",", ""))
    if contributions < metrics["commits"]:
        raise ValueError("Contribution total cannot be lower than the public commit count")

    metrics["contributions"] = contributions
    rows = [
        ("contributions", f"Contributions ({year}):"),
        ("commits", f"Public commits ({year}):"),
        ("stars", "Total stars:"),
        ("prs", "Total PRs:"),
        ("issues", "Total issues:"),
        ("contribs", "Contributed repos (1 yr):"),
    ]
    body = nodes["main-card-body"].find(f"{SVG}svg")
    if body is None:
        raise ValueError(f"{path}: missing card body")
    body.clear()
    for index, (key, label) in enumerate(rows):
        row = ET.SubElement(body, f"{SVG}g", {"transform": f"translate(25, {index * 25})"})
        ET.SubElement(row, f"{SVG}text", {"class": "stat bold", "y": "12.5"}).text = label
        ET.SubElement(row, f"{SVG}text", {
            "class": "stat bold", "x": "204.01", "y": "12.5", "data-testid": key,
        }).text = f"{metrics[key]:,}"
    root.set("height", "220")
    root.set("viewBox", "0 0 495 220")
    root.set("data-contributions-year", str(year))
    nodes["rank-circle"].set("transform", "translate(410, 60)")
    root.find(f"{SVG}desc").text = ", ".join(
        f"{label} {metrics[key]:,}" for key, label in rows
    ) + ". Contributions include private activity counts publicly shared on the GitHub profile."
    return ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=datetime.now(ZoneInfo("Africa/Algiers")).year)
    args = parser.parse_args()
    total = fetch_contributions(args.year)
    paths = [ROOT / "assets" / f"stats-{theme}.svg" for theme in ("dark", "light")]
    # Prepare both cards before replacing either one; failures leave saved cards intact.
    updated = [update_card(path, args.year, total) for path in paths]
    for path, contents in zip(paths, updated):
        path.write_bytes(contents)
    print(f"Added {total:,} contributions for {args.year}, matching the public GitHub calendar.")


if __name__ == "__main__":
    main()
