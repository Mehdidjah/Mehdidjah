"""Show when stats were generated and change image URLs when their contents change.

GitHub and browsers cache raw image URLs. A content version makes new snapshots
use a new URL, so a previously cached zero-day streak does not hide a correction.
Run only after the six cards pass validation and the yearly archive is saved.
"""

from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def refresh(root: Path, generated_at: datetime) -> None:
    if generated_at.tzinfo is None:
        raise ValueError("The generation timestamp must include its timezone")
    version = hashlib.sha256()
    for kind in ("stats", "streak", "languages"):
        for theme in ("dark", "light"):
            version.update((root / "assets" / f"{kind}-{theme}.svg").read_bytes())

    path = root / "README.md"
    readme, count = re.subn(
        r'(\./assets/(?:stats|streak|languages)-(?:dark|light)\.svg)(?:\?v=[a-f0-9]+)?',
        lambda match: f"{match.group(1)}?v={version.hexdigest()[:16]}",
        path.read_text(),
    )
    if count != 9:
        raise ValueError(f"Expected nine themed stats image references; found {count}")

    timestamp = generated_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    readme, count = re.subn(
        r'(?s)<!-- stats-updated:start -->.*?<!-- stats-updated:end -->',
        f"<!-- stats-updated:start -->\n"
        f"<sub>Updated {timestamp} · Scheduled hourly.</sub>\n"
        f"<!-- stats-updated:end -->",
        readme,
    )
    if count != 1:
        raise ValueError("Expected one stats update marker")
    path.write_text(readme)
    print(f"Updated stats image versions and timestamp: {timestamp}")


if __name__ == "__main__":
    refresh(ROOT, datetime.now(timezone.utc))
