"""Save the current year's profile stats snapshot and preserve previous years.

The workflow validates all live cards before calling this script. The archive
starts with the first real snapshot; it never invents historical totals.
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
PROFILE_TIMEZONE = ZoneInfo("Africa/Algiers")
METRICS = ("contributions", "stars", "commits", "prs", "issues", "contribs")
DEFINITIONS = """- **Contributions:** the calendar-year total shown on the public GitHub profile, including private contribution counts the owner has chosen to make visible. This includes qualifying commits and other activity such as pull requests, issues, reviews, and repository creation.
- **Public commits:** only the public commit contributions in that calendar year. This is a subset of the contribution total, not the total number of all public and private commits.
- **Stars, PRs, and issues:** cumulative public totals at the time of capture.
- **Contributed repositories:** the provider's trailing-year count, excluding owned repositories by default.
- **Rank:** the provider's GitHub Readme Stats score, based on its public stats. Adding the calendar contribution total does not change this score.

These are yearly snapshots, not annual totals for every metric. An active year
updates daily; completed years keep their last successful snapshot and its date.
Tracking starts with the first saved snapshot. Years before that are not backfilled.

[How GitHub counts contributions](https://docs.github.com/en/account-and-profile/reference/profile-contributions-reference) · [Other metric definitions](https://github-stats-extended.vercel.app/frontend/docs/cards/stats/)
"""


def read_stats(path: Path, year: int) -> dict:
    root = ET.parse(path).getroot()
    if root.tag != "{http://www.w3.org/2000/svg}svg":
        raise ValueError(f"{path}: expected an SVG")
    values = {
        element.attrib["data-testid"]: "".join(element.itertext()).strip()
        for element in root.iter()
        if "data-testid" in element.attrib
    }
    text = " ".join(" ".join(element.itertext())
                    for element in root.iter("{http://www.w3.org/2000/svg}text"))
    if (f"{year} snapshot" not in values.get("header", "")
            or root.attrib.get("data-contributions-year") != str(year)
            or not all(label in text for label in (f"Contributions ({year})", f"Public commits ({year})"))):
        raise ValueError(f"{path}: card year does not match {year}")
    counts = {}
    for metric in METRICS:
        value = values.get(metric, "")
        if not re.fullmatch(r"[\d,]+", value):
            raise ValueError(f"{path}: invalid {metric}")
        counts[metric] = int(value.replace(",", ""))
    if counts["contributions"] < counts["commits"]:
        raise ValueError(f"{path}: contributions are lower than public commits")
    rank = values.get("level-rank-icon", "")
    if not re.fullmatch(r"S|[ABC][+-]?", rank):
        raise ValueError(f"{path}: invalid rank")
    return {**counts, "rank": rank}


def archive(root: Path, year: int, captured_at: datetime) -> None:
    if captured_at.tzinfo is None or captured_at.astimezone(PROFILE_TIMEZONE).year != year:
        raise ValueError("Only the current calendar year's snapshot can be updated")
    source_cards = {theme: root / "assets" / f"stats-{theme}.svg" for theme in ("dark", "light")}
    counts = {theme: read_stats(path, year) for theme, path in source_cards.items()}
    if counts["dark"] != counts["light"]:
        raise ValueError("Theme cards contain different stats; retry on the next refresh")

    timestamp = captured_at.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    record = {"year": year, "username": "Mehdidjah", "captured_at": timestamp,
              "year_timezone": "Africa/Algiers",
              "contributions_source": f"https://github.com/users/Mehdidjah/contributions?from={year}-01-01&to={year}-12-31",
              "metrics": counts["dark"]}
    folder = root / "stats" / str(year)
    folder.mkdir(parents=True, exist_ok=True)
    for theme, source in source_cards.items():
        (folder / f"stats-{theme}.svg").write_bytes(source.read_bytes())
    (folder / "snapshot.json").write_text(json.dumps(record, indent=2) + "\n")
    (folder / "README.md").write_text(f"""# {year} GitHub stats snapshot

Last saved: **{timestamp}** (UTC).

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./stats-dark.svg" />
  <source media="(prefers-color-scheme: light)" srcset="./stats-light.svg" />
  <img src="./stats-light.svg" alt="Mehdi's {year} GitHub stats snapshot" width="495" />
</picture>

[All years](../README.md) · [Snapshot data](./snapshot.json)

{DEFINITIONS}""")

    # Only regenerate the index. Files in other year folders are never changed.
    records = []
    for path in (root / "stats").glob("[0-9][0-9][0-9][0-9]/snapshot.json"):
        records.append(json.loads(path.read_text()))
    lines = [
        "# Yearly GitHub stats", "",
        "[Back to profile](../README.md)", "",
        "Each year retains its last successful snapshot. Select a year to view its card.", "",
        "| Year | Contributions in year | Public commits in year | Total stars | Total PRs | Total issues | Repos in last year | Rank | Last saved (UTC) |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | :---: | --- |",
    ]
    for entry in sorted(records, key=lambda item: item["year"], reverse=True):
        metrics = entry["metrics"]
        values = [f'[{entry["year"]}](./{entry["year"]}/README.md)',
                  f'{metrics["contributions"]:,}' if "contributions" in metrics else "Not captured",
                  *(f'{metrics[key]:,}' for key in ("commits", "stars", "prs", "issues", "contribs")),
                  metrics["rank"], entry["captured_at"][:10]]
        lines.append("| " + " | ".join(values) + " |")
    lines.extend(["", "## What the numbers mean", "", DEFINITIONS])
    (root / "stats" / "README.md").write_text("\n".join(lines))
    print(f"Archived {year} stats; previous years preserved.")


def main() -> None:
    now = datetime.now(timezone.utc)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=now.astimezone(PROFILE_TIMEZONE).year)
    args = parser.parse_args()
    archive(ROOT, args.year, now)


if __name__ == "__main__":
    main()
