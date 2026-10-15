# Language cards

The language cards show every language GitHub detects in Mehdi's owned,
non-fork repositories, including private repositories. Percentages measure code
size in bytes across **all** included languages. They do not measure programming
time, proficiency, or who authored the code.

Languages detected only in forks appear in a separate **Also in forked projects**
section without percentages. Fork contents do not contribute to the main totals.

## Sources and refreshes

The source is GitHub's [repository languages API](https://docs.github.com/en/rest/repos/repos#list-repository-languages).
`languages.json` contains only aggregate byte totals, repository counts, and
capture times. It contains no private repository names, paths, or source code.

The hourly workflow refreshes public repositories and public forks. Private
totals retain their explicitly dated snapshot unless the repository has a
`PROFILE_LANGUAGES_TOKEN` Actions secret with read access to all of the owner's
private repositories. That optional token is used only by the language step;
the other card providers continue using `GITHUB_TOKEN`.

To refresh all totals locally with an authenticated GitHub CLI:

```sh
python3 scripts/build-languages.py --refresh-all
python3 scripts/validate-stats.py
python3 scripts/refresh-readme.py
```

Run a full refresh after changing a repository's visibility or deleting a private
repository, so the private snapshot is reconciled with the public totals.
Without flags, the builder only renders the saved aggregate snapshot.

## Display contract

- **Question:** which languages are present, and how much of the included code
  does each represent? The card makes smaller languages visible alongside the
  largest ones.
- **Form:** an exact-lookup table in two columns, sorted by byte count down the
  first column and then the second. Every detected language remains visible;
  there is no top-six or top-twenty cutoff.
- **Data:** one aggregate row per language; the initial snapshot has 28 non-fork
  languages and 14 additional languages found only in forks. Nonzero shares
  below 0.01% display as `<0.01%` rather than zero.
- **Surface:** static SVGs embedded in the GitHub profile README. Desktop cards
  are 495 px wide; mobile cards are 360 px wide. Height follows the row count.
- **Style:** match the existing light/dark profile cards, with neutral text,
  borders, and the existing muted accent. Names and values convey the data
  independently of color.
- **QA:** validate every language, total, percentage, fork-only label, and capture
  date against the snapshot. Inspect both themes at desktop and mobile widths.
