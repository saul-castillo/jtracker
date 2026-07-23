"""Fetch, match, rank, deduplicate, queue, and notify."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests

from .connectors import epoch_date, fetch
from .matching import MatchResult, evaluate


ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = ROOT / "data" / "seen.json"
TIMEZONE = ZoneInfo("America/New_York")


def stable_key(job: dict[str, Any]) -> str:
    identity = "|".join(
        (
            str(job.get("company") or ""),
            str(job.get("platform") or ""),
            str(job.get("source_id") or job.get("url") or ""),
        )
    )
    return hashlib.sha256(identity.lower().encode()).hexdigest()[:24]


def legacy_key(job: dict[str, Any]) -> str:
    identity = "|".join(
        str(job.get(field) or "")
        for field in ("company", "title", "location", "url")
    )
    return hashlib.sha256(identity.lower().encode()).hexdigest()[:20]


def quiet_hours(now: datetime) -> bool:
    return now.hour >= 23 or now.hour < 8


def _load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {"seen": [], "pending": []}
    state = json.loads(STATE_PATH.read_text())
    state.setdefault("seen", [])
    state.setdefault("pending", [])
    return state


def _save_state(seen: set[str], pending: list[dict[str, Any]]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps(
            {
                "version": 2,
                "updated_at": datetime.now(TIMEZONE).isoformat(timespec="seconds"),
                "seen": sorted(seen),
                "pending": pending,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def notify_github(subject: str, body: str) -> None:
    token = os.environ.get("GITHUB_TOKEN")
    repository = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repository:
        raise RuntimeError("GitHub Actions notification environment is missing")
    response = requests.post(
        f"https://api.github.com/repos/{repository}/issues",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        json={"title": subject, "body": body, "assignees": ["saul-castillo"]},
        timeout=35,
    )
    response.raise_for_status()


def _render(items: list[dict[str, Any]]) -> str:
    rows = []
    for index, item in enumerate(items, start=1):
        job = item["job"]
        posted = epoch_date(job.get("posted")) or "Not provided"
        reasons = ", ".join(item["reasons"])
        rows.append(
            f"### {index}. {job['company']} — [{job['title']}]({job['url']})\n"
            f"- **Company:** {job['company']}\n"
            f"- **Platform:** {job.get('platform') or 'Official careers site'}\n"
            f"- **Location:** {job.get('location') or 'Unknown'}\n"
            f"- **Posted:** {posted}\n"
            f"- **Score:** {item['score']}\n"
            f"- **Matched:** {reasons}"
        )
    return (
        "## New Summer 2027 hardware internship matches\n\n"
        + "\n\n".join(rows)
        + "\n\n---\nOfficial application links are used whenever the source provides one."
    )


def _notify_pending(pending: list[dict[str, Any]], morning: bool) -> None:
    # GitHub issue bodies max out at 65,536 characters. Keep each digest comfortably below it.
    chunks: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_size = 0
    for item in pending:
        estimated = len(json.dumps(item, ensure_ascii=False))
        if current and current_size + estimated > 48_000:
            chunks.append(current)
            current = []
            current_size = 0
        current.append(item)
        current_size += estimated
    if current:
        chunks.append(current)

    label = "morning digest" if morning else "new matches"
    for index, chunk in enumerate(chunks, start=1):
        suffix = f" ({index}/{len(chunks)})" if len(chunks) > 1 else ""
        notify_github(f"jtracker: {len(chunk)} {label}{suffix}", _render(chunk))


def _fetch_all(config: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, int], list[str]]:
    jobs: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    diagnostics: list[str] = []
    sources = config["sources"]

    with ThreadPoolExecutor(max_workers=int(config.get("max_workers", 10))) as pool:
        future_sources = {pool.submit(fetch, source): source for source in sources}
        for future in as_completed(future_sources):
            source = future_sources[future]
            company = source["company"]
            try:
                result = future.result()
                jobs.extend(result.jobs)
                counts[company] = len(result.jobs)
                diagnostics.extend(result.warnings)
            except Exception as exc:
                counts[company] = 0
                diagnostics.append(f"{company}: {exc}")

    unique: dict[tuple[str, str, str], dict[str, Any]] = {}
    for job in jobs:
        identity = (
            str(job.get("company")),
            str(job.get("platform")),
            str(job.get("source_id") or job.get("url")),
        )
        unique[identity] = job
    return list(unique.values()), counts, diagnostics


def run(*, dry_run: bool = False, test_notification: bool = False) -> dict[str, Any]:
    if test_notification:
        notify_github(
            "jtracker test: notifications are working",
            "The scheduled monitor can create assigned GitHub notifications.",
        )
        return {"test_notification": "sent"}

    config = json.loads((ROOT / "config.json").read_text())
    jobs, source_counts, diagnostics = _fetch_all(config)

    matches: list[tuple[MatchResult, dict[str, Any]]] = []
    rejections: dict[str, int] = {}
    for job in jobs:
        result = evaluate(job)
        if result.matched:
            matches.append((result, job))
        else:
            rejections[result.rejection] = rejections.get(result.rejection, 0) + 1
    matches.sort(key=lambda item: item[0].score, reverse=True)

    state = _load_state()
    seen = set(state["seen"])
    new: list[dict[str, Any]] = []
    for result, job in matches:
        current_key = stable_key(job)
        if current_key in seen or legacy_key(job) in seen:
            continue
        new.append(
            {
                "key": current_key,
                "score": result.score,
                "reasons": list(result.reasons),
                "job": job,
            }
        )

    match_counts: dict[str, int] = {}
    for _, job in matches:
        company = job["company"]
        match_counts[company] = match_counts.get(company, 0) + 1

    report = {
        "sources": len(config["sources"]),
        "fetched": len(jobs),
        "matches": len(matches),
        "new": len(new),
        "source_counts": dict(sorted(source_counts.items())),
        "match_counts": dict(sorted(match_counts.items())),
        "rejections": dict(sorted(rejections.items())),
        "diagnostics": diagnostics,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    if dry_run:
        for item in new[:50]:
            job = item["job"]
            print(
                item["score"],
                job["company"],
                "|",
                job["title"],
                "|",
                job["location"],
                "|",
                job["platform"],
            )
        return report

    pending = []
    for item in state.get("pending", []):
        result = evaluate(item.get("job") or {})
        if not result.matched:
            continue
        item["score"] = result.score
        item["reasons"] = list(result.reasons)
        item["key"] = stable_key(item["job"])
        pending.append(item)
    pending_keys = {item["key"] for item in pending}
    for item in new:
        if item["key"] not in pending_keys:
            pending.append(item)
            pending_keys.add(item["key"])
    pending.sort(key=lambda item: item["score"], reverse=True)

    now = datetime.now(TIMEZONE)
    had_overnight_queue = bool(state.get("pending"))
    if pending and not quiet_hours(now):
        _notify_pending(pending, morning=had_overnight_queue and now.hour < 11)
        pending = []

    for _, job in matches:
        seen.add(stable_key(job))
    _save_state(seen, pending)

    if source_counts and not any(source_counts.values()):
        raise RuntimeError("all configured sources failed")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--test-notification", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run, test_notification=args.test_notification)
