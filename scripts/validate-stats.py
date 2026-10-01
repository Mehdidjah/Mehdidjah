"""Reject blank SVGs and error cards before a workflow replaces the saved stats."""

from pathlib import Path
import re
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
SVG_NAMESPACE = "{http://www.w3.org/2000/svg}"


def validate_card(path: Path, kind: str) -> None:
    root = ET.parse(path).getroot()
    if root.tag != f"{SVG_NAMESPACE}svg":
        raise ValueError(f"{path.name}: not an SVG")

    labels = [
        " ".join(element.itertext()).strip()
        for element in root.iter(f"{SVG_NAMESPACE}text")
    ]
    text = " ".join(labels)
    lower = text.lower()
    if not text or any(
        error in lower
        for error in (
            "something went wrong",
            "rate limit",
            "could not fetch",
            "user not found",
            "maximum retries",
            "deployment_disabled",
        )
    ):
        raise ValueError(f"{path.name}: empty card or service error")

    if kind == "streak":
        expected = ("Total Contributions", "Current Streak", "Longest Streak")
        if not all(label in text for label in expected):
            raise ValueError(f"{path.name}: missing streak labels")
        if len([label for label in labels if re.fullmatch(r"[\d,]+", label)]) < 3:
            raise ValueError(f"{path.name}: missing contribution or streak counts")
        if (root.attrib.get("data-contributions-start") != "2020-05-02"
                or "May 2, 2020 - Present" not in labels):
            raise ValueError(f"{path.name}: missing the requested contribution period")
    elif kind == "languages":
        if "most used languages" not in lower or not re.search(r"\d+(?:\.\d+)?%", text):
            raise ValueError(f"{path.name}: missing language percentages")
    elif kind == "stats":
        values = {
            element.attrib["data-testid"]: "".join(element.itertext()).strip()
            for element in root.iter()
            if "data-testid" in element.attrib
        }
        for metric in ("contributions", "stars", "commits", "prs", "issues", "contribs"):
            if not re.fullmatch(r"[\d,]+", values.get(metric, "")):
                raise ValueError(f"{path.name}: missing or invalid {metric}")
        if int(values["contributions"].replace(",", "")) < int(values["commits"].replace(",", "")):
            raise ValueError(f"{path.name}: contributions are lower than public commits")
        year = root.attrib.get("data-contributions-year", "")
        if not re.fullmatch(r"\d{4}", year) or not all(
            label in text for label in (f"Contributions ({year})", f"Public commits ({year})")
        ):
            raise ValueError(f"{path.name}: missing contribution year or metric scope")
        if not re.fullmatch(r"S|[ABC][+-]?", values.get("level-rank-icon", "")):
            raise ValueError(f"{path.name}: missing rank")
    else:
        raise ValueError(f"Unknown card kind: {kind}")

    print(f"Validated {path.name}")


def main() -> None:
    for kind in ("stats", "streak", "languages"):
        for theme in ("dark", "light"):
            validate_card(ROOT / "assets" / f"{kind}-{theme}.svg", kind)


if __name__ == "__main__":
    main()
