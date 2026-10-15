"""Build complete language cards from aggregate GitHub language byte counts."""

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html import escape
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "stats" / "languages.json"
OWNER = "Mehdidjah"
THEMES = {
    "dark": {"bg": "#0D1117", "border": "#30363D", "title": "#E6EDF3",
             "text": "#C9D1D9", "muted": "#9198A1", "accent": "#9DCBB6"},
    "light": {"bg": "#FFFFFF", "border": "#EAEAEA", "title": "#1F2328",
              "text": "#59636E", "muted": "#59636E", "accent": "#346538"},
}


def github(endpoint: str, *, paginate: bool = False):
    command = ["gh", "api", endpoint]
    if paginate:
        command += ["--paginate", "--slurp"]
    result = subprocess.run(command, capture_output=True, text=True, timeout=90)
    if result.returncode:
        # Do not put private repository names or API response contents in logs.
        raise RuntimeError("GitHub language collection failed; the saved snapshot was retained")
    return json.loads(result.stdout)


def validate_snapshot(data: dict) -> None:
    if set(data) != {"version", "username", "public", "private", "forks"}:
        raise ValueError("The language snapshot must contain only aggregate sections")
    if data["version"] != 1 or data["username"] != OWNER:
        raise ValueError("Unexpected language snapshot version or owner")
    for scope in ("public", "private", "forks"):
        section = data[scope]
        if set(section) != {"captured_at", "repository_count", "languages"}:
            raise ValueError(f"Unexpected fields in the {scope} aggregate")
        captured = datetime.fromisoformat(section["captured_at"])
        if captured.tzinfo is None or type(section["repository_count"]) is not int:
            raise ValueError(f"Invalid {scope} capture metadata")
        if section["repository_count"] < 0 or not isinstance(section["languages"], dict):
            raise ValueError(f"Invalid {scope} aggregate")
        for name, size in section["languages"].items():
            if not isinstance(name, str) or not name or type(size) is not int or size <= 0:
                raise ValueError(f"Invalid {scope} language size")
    if not combined_languages(data):
        raise ValueError("No non-fork language data was collected")


def combined_languages(data: dict) -> Counter:
    return Counter(data["public"]["languages"]) + Counter(data["private"]["languages"])


def refresh(data: dict, *, include_private: bool) -> dict:
    if include_private:
        if github("user")["login"].lower() != OWNER.lower():
            raise ValueError("A full refresh requires the profile owner's GitHub login")
        endpoint = "user/repos?affiliation=owner&visibility=all&per_page=100"
    else:
        endpoint = f"users/{OWNER}/repos?type=owner&per_page=100"
    repositories = [
        repo for page in github(endpoint, paginate=True) for repo in page
        if repo["owner"]["login"].lower() == OWNER.lower()
        and (include_private or not repo["private"])
    ]

    def collect(repo):
        scope = "forks" if repo["fork"] else "private" if repo["private"] else "public"
        return scope, github(f"repos/{repo['full_name']}/languages")

    scopes = ("public", "private", "forks") if include_private else ("public", "forks")
    counts = Counter()
    languages = {scope: Counter() for scope in scopes}
    with ThreadPoolExecutor(max_workers=4) as executor:
        for scope, sizes in executor.map(collect, repositories):
            if not isinstance(sizes, dict) or any(type(n) is not int or n < 0 for n in sizes.values()):
                raise ValueError("GitHub returned invalid language sizes")
            counts[scope] += 1
            languages[scope].update({name: size for name, size in sizes.items() if size > 0})

    # A token that can see only some private repositories must not silently
    # replace the saved totals with a smaller, incomplete sample.
    if include_private and counts["private"] < data["private"]["repository_count"]:
        raise ValueError("Fewer private repositories were visible; reconcile access or the saved count before a full refresh")
    captured_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result = dict(data)
    for scope in scopes:
        result[scope] = {"captured_at": captured_at, "repository_count": counts[scope],
                         "languages": dict(sorted(languages[scope].items()))}
    validate_snapshot(result)
    return result


def percentage(size: int, total: int) -> str:
    share = size * 100 / total
    return "<0.01%" if share < 0.01 else f"{share:.2f}%"


def wrap_names(names: list[str], width: int) -> list[str]:
    lines = []
    current = ""
    for name in names:
        candidate = f"{current} · {name}" if current else name
        # Reserve generous space for font differences across SVG renderers.
        if current and len(candidate) * 6.4 > width:
            lines.append(current)
            current = name
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def render(data: dict, theme: str, *, mobile: bool) -> str:
    palette = THEMES[theme]
    sizes = combined_languages(data)
    ranked = sorted(sizes.items(), key=lambda row: (-row[1], row[0]))
    total = sum(sizes.values())
    extra = [name for name, _ in sorted(data["forks"]["languages"].items(),
                                       key=lambda row: (-row[1], row[0])) if name not in sizes]
    width = 360 if mobile else 495
    margin, gap = (18, 18) if mobile else (25, 36)
    inner = width - margin * 2
    column_width = (inner - gap) / 2
    rows = (len(ranked) + 1) // 2
    first_y, row_height = 112, 27
    divider_y = first_y + rows * row_height - 6
    extra_lines = wrap_names(extra, inner)
    dates_y = divider_y + (58 + len(extra_lines) * 19 if extra else 24)
    height = dates_y + 50
    public_date = data["public"]["captured_at"][:10]
    private_date = data["private"]["captured_at"][:10]
    fork_date = data["forks"]["captured_at"][:10]
    repository_count = data["public"]["repository_count"] + data["private"]["repository_count"]
    description = (
        f"All {len(ranked)} languages by code size in {repository_count} public and private non-fork repositories. "
        + "; ".join(f"{name}: {percentage(size, total)}" for name, size in ranked)
        + (". Additional languages found only in forks: " + ", ".join(extra) if extra else "")
        + f". Public snapshot {public_date}; private snapshot {private_date}; forks snapshot {fork_date}."
    )
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'role="img" aria-labelledby="title description" data-language-count="{len(ranked)}" '
        f'data-total-bytes="{total}" data-private-captured-at="{escape(data["private"]["captured_at"])}">',
        '<title id="title">Most used languages</title>',
        f'<desc id="description">{escape(description)}</desc>',
        '<style>text{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}'
        f'.heading{{font-size:{17 if mobile else 18}px;font-weight:600;fill:{palette["title"]}}}'
        f'.label{{font-size:13px;fill:{palette["text"]}}}'
        f'.value{{font-size:12px;font-variant-numeric:tabular-nums;fill:{palette["title"]}}}'
        f'.note{{font-size:11px;fill:{palette["muted"]}}}'
        f'.section{{font-size:12px;font-weight:600;fill:{palette["accent"]}}}'
        '</style>',
        f'<rect x="0.5" y="0.5" width="{width-1}" height="{height-1}" rx="8" '
        f'fill="{palette["bg"]}" stroke="{palette["border"]}"/>',
        f'<text x="{margin}" y="33" class="heading">Most used languages</text>',
        f'<text x="{margin}" y="55" class="note">Code size · Public + private · Non-fork repositories</text>',
        f'<text x="{margin}" y="73" class="note">All {len(ranked)} languages · {repository_count} repositories</text>',
        f'<path d="M {margin} 87 H {width-margin}" stroke="{palette["border"]}"/>',
    ]
    for index, (name, size) in enumerate(ranked):
        column, row = divmod(index, rows)
        x = margin + column * (column_width + gap)
        y = first_y + row * row_height
        parts += [
            f'<g data-language="{escape(name)}" data-bytes="{size}">',
            f'<text x="{x:g}" y="{y}" class="label">{escape(name)}</text>',
            f'<text x="{x+column_width:g}" y="{y}" text-anchor="end" class="value">{escape(percentage(size, total))}</text>',
            '</g>',
        ]
    if extra:
        parts += [
            f'<path d="M {margin} {divider_y} H {width-margin}" stroke="{palette["border"]}"/>',
            f'<text x="{margin}" y="{divider_y+26}" class="section">Also in forked projects</text>',
        ]
        for index, line in enumerate(extra_lines):
            parts.append(f'<text x="{margin}" y="{divider_y+48+index*19}" class="note">{escape(line)}</text>')
        for name in extra:
            parts.append(f'<metadata data-fork-language="{escape(name)}"/>')
    parts += [
        f'<text x="{margin}" y="{dates_y}" class="note">Public + forks: {public_date} · Refreshed hourly</text>',
        f'<text x="{margin}" y="{dates_y+19}" class="note">Private snapshot: {private_date}</text>',
        '</svg>',
    ]
    return "\n".join(parts) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    refresh_mode = parser.add_mutually_exclusive_group()
    refresh_mode.add_argument("--refresh-public", action="store_true")
    refresh_mode.add_argument("--refresh-all", action="store_true")
    args = parser.parse_args()
    data = json.loads(SNAPSHOT.read_text())
    validate_snapshot(data)
    if args.refresh_public or args.refresh_all:
        data = refresh(data, include_private=args.refresh_all)
    outputs = {}
    for theme in THEMES:
        for mobile in (False, True):
            suffix = "-mobile" if mobile else ""
            outputs[ROOT / "assets" / f"languages-{theme}{suffix}.svg"] = render(data, theme, mobile=mobile)
    SNAPSHOT.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    for path, svg in outputs.items():
        path.write_text(svg)
    print(f"Rendered {len(combined_languages(data))} languages in four themed cards")


if __name__ == "__main__":
    main()
