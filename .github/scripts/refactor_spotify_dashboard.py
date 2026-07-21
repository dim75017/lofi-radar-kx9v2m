#!/usr/bin/env python3
"""Restore and split the last complete Spotify dashboard.

Commit 6b865a6 accidentally saved a tool-truncated response into
spotify/index.html.  Recover the last complete file, preserve the intended
live Soundcharts source, then externalize the large inline CSS and JavaScript.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

SOURCE_COMMIT = "7d8c5feb249726a8f1c7c856ca1681da146ffa2f"
HTML_PATH = Path("spotify/index.html")
CSS_PATH = Path("spotify/dashboard.css")
JS_PATH = Path("spotify/dashboard.js")


def git_show(path: str) -> str:
    return subprocess.check_output(
        ["git", "show", f"{SOURCE_COMMIT}:{path}"],
        text=True,
        encoding="utf-8",
    )


def main() -> None:
    source = git_show("spotify/index.html")

    # Keep the one intentional source update from the commit that accidentally
    # truncated the rest of the page.
    old_snapshot = (
        "../Spotify_Soundcharts_data_20260720T0217_editorial_strict.js"
        "?v=0217editorialstrict"
    )
    live_snapshot = "../Spotify_Soundcharts_data.js?v=soundcharts-live"
    if old_snapshot not in source:
        raise SystemExit("Expected historical Soundcharts script reference was not found")
    source = source.replace(old_snapshot, live_snapshot, 1)

    style_matches = list(
        re.finditer(r"<style\b[^>]*>([\s\S]*?)</style>", source, re.IGNORECASE)
    )
    if len(style_matches) != 1:
        raise SystemExit(f"Expected exactly one inline style block, found {len(style_matches)}")
    style_match = style_matches[0]

    body_start = source.lower().find("<body")
    if body_start < 0:
        raise SystemExit("Spotify dashboard has no body element")

    script_pattern = re.compile(
        r"<script\b(?P<attrs>[^>]*)>(?P<body>[\s\S]*?)</script>",
        re.IGNORECASE,
    )
    body_scripts: list[re.Match[str]] = []
    for match in script_pattern.finditer(source):
        attrs = match.group("attrs")
        if match.start() < body_start or re.search(r"\bsrc\s*=", attrs, re.IGNORECASE):
            continue
        script_type = re.search(
            r"\btype\s*=\s*(['\"])(.*?)\1", attrs, re.IGNORECASE
        )
        if script_type and script_type.group(2).lower() not in {
            "text/javascript",
            "application/javascript",
            "module",
        }:
            continue
        body_scripts.append(match)

    if len(body_scripts) != 1:
        raise SystemExit(
            f"Expected exactly one inline body script, found {len(body_scripts)}"
        )
    script_match = body_scripts[0]

    css = style_match.group(1).strip() + "\n"
    javascript = script_match.group("body").strip() + "\n"

    replacements = [
        (
            style_match.start(),
            style_match.end(),
            '<link rel="stylesheet" href="dashboard.css">',
        ),
        (
            script_match.start(),
            script_match.end(),
            '<script src="dashboard.js"></script>',
        ),
    ]
    html = source
    for start, end, replacement in sorted(replacements, reverse=True):
        html = html[:start] + replacement + html[end:]

    if "Warning: truncated output" in html:
        raise SystemExit("Truncation warning survived restoration")
    if "<style" in html.lower():
        raise SystemExit("Inline style block survived extraction")
    if html.count('src="dashboard.js"') != 1:
        raise SystemExit("Spotify JavaScript reference was not inserted exactly once")
    if html.count('href="dashboard.css"') != 1:
        raise SystemExit("Spotify stylesheet reference was not inserted exactly once")
    if len(html.splitlines()) > 180:
        raise SystemExit(f"Refactored HTML is unexpectedly long: {len(html.splitlines())} lines")

    HTML_PATH.write_text(html, encoding="utf-8")
    CSS_PATH.write_text(css, encoding="utf-8")
    JS_PATH.write_text(javascript, encoding="utf-8")

    print(
        "Restored Spotify dashboard:",
        f"html={len(html.encode('utf-8'))} bytes/{len(html.splitlines())} lines,",
        f"css={len(css.encode('utf-8'))} bytes/{len(css.splitlines())} lines,",
        f"js={len(javascript.encode('utf-8'))} bytes/{len(javascript.splitlines())} lines",
    )


if __name__ == "__main__":
    main()
