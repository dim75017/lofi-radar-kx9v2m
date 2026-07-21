#!/usr/bin/env python3
"""Count the live Soundcharts song totals for every mapped radar artist.

The script uses the production Soundcharts credentials supplied by GitHub Actions,
never prints credentials, and stores only aggregate counts plus the largest
artist discographies.
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

API_BASE = "https://customer.api.soundcharts.com"
PREFIX = "window.SPOTIFY_SOUNDCHARTS="


def clean(value: str) -> str:
    return value.strip().strip("\ufeff\u200b").strip("\"'").strip()


def read_payload(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith(PREFIX):
        raise RuntimeError("Unexpected Spotify_Soundcharts_data.js prefix")
    payload = json.loads(text[len(PREFIX) :].strip().removesuffix(";"))
    if not isinstance(payload, dict):
        raise RuntimeError("Invalid Soundcharts payload")
    return payload


def main() -> int:
    app_id = clean(os.environ.get("SOUNDCHARTS_CLIENT_ID", ""))
    api_key = clean(os.environ.get("SOUNDCHARTS_CLIENT_SECRET", ""))
    if not app_id or not api_key:
        raise RuntimeError("Soundcharts credentials are missing")

    payload = read_payload(Path("Spotify_Soundcharts_data.js"))
    schema = list(payload.get("schemas", {}).get("artists", []))
    rows = payload.get("artists", [])

    def field(row: list[Any], name: str) -> Any:
        try:
            index = schema.index(name)
        except ValueError:
            return None
        return row[index] if index < len(row) else None

    artists: list[tuple[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        uuid = str(field(row, "soundcharts_uuid") or "").strip()
        name = str(field(row, "name") or "").strip()
        if uuid and uuid not in seen:
            seen.add(uuid)
            artists.append((uuid, name))
    if not artists:
        raise RuntimeError("No mapped Soundcharts artists")

    headers = {
        "x-app-id": app_id,
        "x-api-key": api_key,
        "Accept": "application/json",
        "User-Agent": "Lofi-Radar-Catalog-Count/1.0",
    }

    state_lock = threading.Lock()
    rate_lock = threading.Lock()
    state: dict[str, Any] = {"requests": 0, "quota": None, "next_call": 0.0}

    def throttle() -> None:
        # 40 requests/second = 2,400/minute, below Soundcharts' 5,000/minute advice.
        with rate_lock:
            now = time.monotonic()
            target = max(now, float(state["next_call"]))
            state["next_call"] = target + 0.025
            delay = target - now
        if delay > 0:
            time.sleep(delay)

    def request_json(path: str, retries: int = 4) -> tuple[int, Any]:
        last_error: Exception | None = None
        for attempt in range(retries):
            throttle()
            with state_lock:
                state["requests"] += 1
            request = urllib.request.Request(API_BASE + path, headers=headers)
            try:
                with urllib.request.urlopen(request, timeout=45) as response:
                    body = json.loads(response.read().decode("utf-8"))
                    raw_quota = response.headers.get("x-quota-remaining") or response.headers.get(
                        "X-Quota-Remaining"
                    )
                    try:
                        quota = int(raw_quota) if raw_quota is not None else None
                    except (TypeError, ValueError):
                        quota = None
                    if quota is not None:
                        with state_lock:
                            state["quota"] = quota
                    return response.status, body
            except urllib.error.HTTPError as exc:
                if exc.code in {400, 401, 403, 404}:
                    try:
                        body = json.loads(exc.read().decode("utf-8"))
                    except Exception:
                        body = None
                    return exc.code, body
                last_error = exc
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc
            time.sleep(min(12.0, 1.5 * (attempt + 1)))
        raise RuntimeError(f"Soundcharts request failed: {type(last_error).__name__}")

    favorite_probe: dict[str, Any]
    try:
        status, body = request_json("/api/v2/favorite/artists?offset=0&limit=20")
        page = body.get("page") if isinstance(body, dict) else None
        favorite_probe = {
            "status": status,
            "total": page.get("total") if isinstance(page, dict) else None,
        }
    except Exception as exc:
        favorite_probe = {"error": type(exc).__name__}

    def count_artist(entry: tuple[str, str]) -> dict[str, Any]:
        uuid, name = entry
        query = urllib.parse.urlencode(
            {"offset": 0, "limit": 1, "sortBy": "releaseDate", "sortOrder": "desc"}
        )
        try:
            status, body = request_json(
                f"/api/v2/artist/{urllib.parse.quote(uuid)}/songs?{query}"
            )
        except Exception as exc:
            return {
                "uuid": uuid,
                "name": name,
                "status": "exception",
                "error": type(exc).__name__,
                "total": 0,
            }
        page = body.get("page") if isinstance(body, dict) else None
        total = page.get("total") if isinstance(page, dict) else None
        return {
            "uuid": uuid,
            "name": name,
            "status": status,
            "total": int(total) if isinstance(total, (int, float)) else 0,
        }

    results: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        futures = [pool.submit(count_artist, entry) for entry in artists]
        for index, future in enumerate(concurrent.futures.as_completed(futures), 1):
            results.append(future.result())
            if index % 250 == 0:
                with state_lock:
                    snapshot = {
                        "processed": index,
                        "artists": len(artists),
                        "requests": state["requests"],
                        "quota_remaining": state["quota"],
                    }
                print(json.dumps(snapshot))

    successful = [result for result in results if result.get("status") == 200]
    totals = [int(result.get("total") or 0) for result in successful]
    ranked = sorted(successful, key=lambda item: int(item.get("total") or 0), reverse=True)
    sorted_totals = sorted(totals)

    with state_lock:
        request_count = int(state["requests"])
        quota_remaining = state["quota"]

    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": "live_soundcharts_api",
        "endpoint": "/api/v2/artist/{uuid}/songs?limit=1",
        "artists_queried": len(artists),
        "status_counts": dict(Counter(str(result.get("status")) for result in results)),
        "artists_successful": len(successful),
        "sum_of_page_totals": sum(totals),
        "mean_songs_per_artist": round(sum(totals) / len(totals), 2) if totals else None,
        "median_songs_per_artist": sorted_totals[len(sorted_totals) // 2] if totals else None,
        "maximum_songs_for_one_artist": max(totals) if totals else None,
        "artists_over_100": sum(total > 100 for total in totals),
        "artists_over_500": sum(total > 500 for total in totals),
        "artists_over_1000": sum(total > 1000 for total in totals),
        "largest_discographies": [
            {key: item.get(key) for key in ("uuid", "name", "total")} for item in ranked[:30]
        ],
        "requests_used": request_count,
        "quota_remaining": quota_remaining,
        "favorite_artist_probe": favorite_probe,
        "current_export_track_rows": len(payload.get("tracks", [])),
        "existing_export_coverage": payload.get("coverage", {}),
    }
    Path("soundcharts-live-total-count.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
