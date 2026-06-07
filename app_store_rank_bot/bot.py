from __future__ import annotations

import argparse
import csv
import json
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


APP_STORE_SEARCH_URL = "https://itunes.apple.com/search"
CHECKS_DIR = Path("checks")
REPORTS_DIR = Path("reports")


@dataclass(frozen=True)
class Check:
    app_id: str
    country: str
    keyword: str


@dataclass(frozen=True)
class RankResult:
    app_id: str
    country: str
    keyword: str
    rank: int | None
    checked_at: str


class AppStoreClient:
    def find_rank(self, app_id: str, country: str, keyword: str, limit: int = 200) -> int | None:
        query = urllib.parse.urlencode(
            {
                "term": keyword,
                "country": country.lower(),
                "entity": "software",
                "limit": str(limit),
            }
        )
        request = urllib.request.Request(
            f"{APP_STORE_SEARCH_URL}?{query}",
            headers={"User-Agent": "ASO-Bot-Parser/1.0"},
        )

        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))

        for index, item in enumerate(payload.get("results", []), start=1):
            if str(item.get("trackId")) == app_id:
                return index
        return None


def load_checks(path: Path) -> list[Check]:
    data = json.loads(path.read_text(encoding="utf-8"))
    checks: list[Check] = []

    for item in data.get("checks", []):
        app_id = str(item.get("app_id", "")).strip()
        country = str(item.get("country", "")).strip().upper()
        keyword = str(item.get("keyword", "")).strip()

        if not app_id.isdigit():
            raise ValueError(f"Invalid app_id: {app_id!r}")
        if len(country) != 2 or not country.isalpha():
            raise ValueError(f"Invalid country for app {app_id}: {country!r}")
        if not keyword:
            raise ValueError(f"Keyword is empty for app {app_id} in {country}")

        checks.append(Check(app_id=app_id, country=country, keyword=keyword))

    return checks


def save_checks(checks: list[Check], checked_at: str) -> Path:
    CHECKS_DIR.mkdir(parents=True, exist_ok=True)
    path = CHECKS_DIR / f"checks-{file_timestamp(checked_at)}.json"
    payload = {
        "created_at": checked_at,
        "checks": [
            {
                "app_id": check.app_id,
                "country": check.country,
                "keyword": check.keyword,
            }
            for check in checks
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def saved_check_files() -> list[Path]:
    if not CHECKS_DIR.exists():
        return []
    return sorted(CHECKS_DIR.glob("checks-*.json"), key=lambda path: path.stat().st_mtime, reverse=True)


def latest_checks_file() -> Path | None:
    files = saved_check_files()
    return files[0] if files else None


def saved_report_files() -> list[Path]:
    if not REPORTS_DIR.exists():
        return []
    return sorted(REPORTS_DIR.glob("positions-*.csv"), key=lambda path: path.stat().st_mtime, reverse=True)


def latest_report_file() -> Path | None:
    files = saved_report_files()
    return files[0] if files else None


def require_latest_checks_file() -> Path:
    path = latest_checks_file()
    if path is None:
        raise SystemExit("No saved check sets found. Run the interactive flow first.")
    return path


def require_latest_report_file() -> Path:
    path = latest_report_file()
    if path is None:
        raise SystemExit("No saved position reports found. Run /check-new-positions first.")
    return path


def print_history() -> None:
    files = saved_check_files()
    if not files:
        print("No saved check sets found.")
        return

    print("Saved check sets:")
    for index, path in enumerate(files, start=1):
        checks = load_checks(path)
        created_at = read_created_at(path)
        app_ids = sorted({check.app_id for check in checks})
        countries = sorted({check.country for check in checks})
        print(
            f"{index}. {path} | created_at={created_at} | "
            f"apps={','.join(app_ids)} | countries={','.join(countries)} | keywords={len(checks)}"
        )


def read_created_at(path: Path) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    return str(data.get("created_at") or "unknown")


def print_keywords(path: Path) -> None:
    checks = load_checks(path)
    if not checks:
        print(f"No keywords found in {path}.")
        return

    app_ids = sorted({check.app_id for check in checks})
    countries = sorted({check.country for check in checks})
    print(f"Current keyword list: {path}")
    print(f"Apps: {', '.join(app_ids)}")
    print(f"Countries: {', '.join(countries)}")
    for index, check in enumerate(checks, start=1):
        print(f"{index}. {check.keyword}")


def print_saved_positions(path: Path) -> None:
    with path.open("r", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    if not rows:
        print(f"No saved positions found in {path}.")
        return

    print(f"Latest saved positions: {path}")
    print_markdown_table(
        ["checked_at", "app_id", "country", "keyword", "rank"],
        [
            [
                row.get("checked_at", ""),
                row.get("app_id", ""),
                row.get("country", ""),
                row.get("keyword", ""),
                row.get("rank", ""),
            ]
            for row in rows
        ],
    )


def print_markdown_table(headers: list[str], rows: list[list[str]]) -> None:
    widths = [
        max(len(str(value)) for value in [header] + [row[index] for row in rows])
        for index, header in enumerate(headers)
    ]

    header_row = "| " + " | ".join(header.ljust(widths[index]) for index, header in enumerate(headers)) + " |"
    separator = "| " + " | ".join("-" * width for width in widths) + " |"
    print(header_row)
    print(separator)

    for row in rows:
        print("| " + " | ".join(str(value).ljust(widths[index]) for index, value in enumerate(row)) + " |")


def update_keywords(path: Path) -> Path:
    checks = load_checks(path)
    if not checks:
        raise SystemExit(f"No checks found in {path}.")

    app_id = checks[0].app_id
    country = checks[0].country
    print(f"Updating keyword list for app_id={app_id}, country={country}")
    keywords = ask_keywords()
    updated_checks = [Check(app_id=app_id, country=country, keyword=keyword) for keyword in keywords]
    checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    updated_path = save_checks(updated_checks, checked_at)
    print(f"\nUpdated checks saved: {updated_path}")
    return updated_path


def run_checks(checks: list[Check], limit: int) -> list[RankResult]:
    client = AppStoreClient()
    checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    results: list[RankResult] = []

    for index, check in enumerate(checks, start=1):
        print(f"[{index}/{len(checks)}] {check.country} / {check.keyword}")
        results.append(
            RankResult(
                app_id=check.app_id,
                country=check.country,
                keyword=check.keyword,
                rank=client.find_rank(check.app_id, check.country, check.keyword, limit),
                checked_at=checked_at,
            )
        )

    return results


def write_report(results: list[RankResult]) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    checked_at = results[0].checked_at if results else datetime.now(timezone.utc).isoformat(timespec="seconds")
    path = REPORTS_DIR / f"positions-{file_timestamp(checked_at)}.csv"

    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["checked_at", "app_id", "country", "keyword", "rank"])
        for result in results:
            writer.writerow(
                [
                    result.checked_at,
                    result.app_id,
                    result.country,
                    result.keyword,
                    result.rank if result.rank is not None else "not found",
                ]
            )

    return path


def print_table(results: list[RankResult]) -> None:
    rows = [
        [
            result.checked_at,
            result.app_id,
            result.country,
            result.keyword,
            str(result.rank) if result.rank is not None else "not found",
        ]
        for result in results
    ]
    writer = csv.writer(sys.stdout)
    writer.writerow(["checked_at", "app_id", "country", "keyword", "rank"])
    writer.writerows(rows)


def print_json(results: list[RankResult]) -> None:
    payload: list[dict[str, Any]] = [
        {
            "app_id": result.app_id,
            "country": result.country,
            "keyword": result.keyword,
            "rank": result.rank,
            "checked_at": result.checked_at,
        }
        for result in results
    ]
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def check_positions(checks: list[Check], limit: int, output_format: str) -> Path:
    print("\nChecking App Store positions...")
    results = run_checks(checks, limit)
    report_path = write_report(results)

    if output_format == "json":
        print_json(results)
    else:
        print_table(results)

    print(f"\nReport saved: {report_path}")
    return report_path


def ask_checks() -> list[Check]:
    print("Step 1. App")
    app_id = ask_app_id()

    print("\nStep 2. Country")
    country = ask_country()

    print("\nStep 3. Keywords")
    keywords = ask_keywords()

    return [Check(app_id=app_id, country=country, keyword=keyword) for keyword in keywords]


def ask_app_id() -> str:
    while True:
        value = input("Enter the App Store app_id: ").strip()
        if value.isdigit():
            return value
        print("app_id must be numeric, for example 284882215.")


def ask_country() -> str:
    while True:
        value = input("Enter the 2-letter country code, for example US: ").strip().upper()
        if len(value) == 2 and value.isalpha():
            return value
        print("Use a 2-letter country code such as US, GB, DE, or FR.")


def ask_keywords() -> list[str]:
    while True:
        value = input("Enter all keywords separated by commas or semicolons: ").strip()
        keywords = [item.strip() for item in value.replace(";", ",").split(",") if item.strip()]
        if keywords:
            return keywords
        print("Add at least one keyword.")


def file_timestamp(value: str) -> str:
    normalized = value.replace("+00:00", "Z")
    return normalized.replace(":", "").replace("-", "")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check App Store search positions.")
    parser.add_argument("config", nargs="?", type=Path, help="Path to checks JSON file.")
    parser.add_argument("--check-new-positions", action="store_true", help="Check positions for the latest saved keyword list.")
    parser.add_argument("--check-history", action="store_true", help="List saved check sets and exit.")
    parser.add_argument("--show-keywords", action="store_true", help="Print the latest saved keyword list and exit.")
    parser.add_argument("--show-saved-positions", action="store_true", help="Print the latest saved positions report and exit.")
    parser.add_argument("--update-keywords", action="store_true", help="Replace keywords in the latest saved check set.")
    parser.add_argument("--limit", type=int, default=200, help="Search depth. Default: 200.")
    parser.add_argument(
        "--format",
        choices=("table", "json"),
        default="table",
        help="Output format. Default: table.",
    )
    return parser


def main() -> None:
    slash_aliases = {
        "/check-new-positions": "--check-new-positions",
        "/check-history": "--check-history",
        "/help": "--help",
        "/show-keywords": "--show-keywords",
        "/show-saved-positions": "--show-saved-positions",
        "/update-keywords": "--update-keywords",
    }
    if len(sys.argv) > 1 and sys.argv[1] in slash_aliases:
        sys.argv[1] = slash_aliases[sys.argv[1]]

    args = build_parser().parse_args()

    if args.check_history:
        print_history()
        return

    if args.show_keywords:
        print_keywords(require_latest_checks_file())
        return

    if args.show_saved_positions:
        print_saved_positions(require_latest_report_file())
        return

    if args.update_keywords:
        update_keywords(require_latest_checks_file())
        return

    if args.check_new_positions:
        checks_path = require_latest_checks_file()
        checks = load_checks(checks_path)
        print(f"Checking latest saved keywords: {checks_path}")
    elif args.config:
        checks = load_checks(args.config)
        checks_path = args.config
    else:
        checks = ask_checks()
        checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        checks_path = save_checks(checks, checked_at)
        print(f"\nChecks saved: {checks_path}")

    check_positions(checks, args.limit, args.format)
