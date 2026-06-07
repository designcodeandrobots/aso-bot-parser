from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


APP_STORE_SEARCH_URL = "https://itunes.apple.com/search"
CHECKS_DIR = Path("checks")
REPORTS_DIR = Path("reports")
DEFAULT_DELAY_SECONDS = 1.0


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


def print_geo_list(path: Path) -> None:
    checks = load_checks(path)
    if not checks:
        print(f"No geos found in {path}.")
        return

    print(f"Current geo list: {path}")
    for index, country in enumerate(sorted({check.country for check in checks}), start=1):
        keyword_count = sum(1 for check in checks if check.country == country)
        print(f"{index}. {country} ({keyword_count} keywords)")


def add_geo(path: Path) -> Path:
    checks = load_checks(path)
    if not checks:
        raise SystemExit(f"No checks found in {path}.")

    app_ids = sorted({check.app_id for check in checks})
    if len(app_ids) != 1:
        raise SystemExit("Add geo supports one app_id per active check set.")

    country = ask_country()
    existing_countries = {check.country for check in checks}
    if country in existing_countries:
        raise SystemExit(f"{country} already exists in the active geo list.")

    print(f"Adding geo {country} for app_id={app_ids[0]}")
    keywords = ask_keywords()
    updated_checks = checks + [Check(app_id=app_ids[0], country=country, keyword=keyword) for keyword in keywords]
    checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    updated_path = save_checks(updated_checks, checked_at)
    print(f"\nUpdated checks saved: {updated_path}")
    return updated_path


def delete_geo(path: Path) -> Path:
    checks = load_checks(path)
    if not checks:
        raise SystemExit(f"No checks found in {path}.")

    countries = sorted({check.country for check in checks})
    print("Current geos:")
    for index, country in enumerate(countries, start=1):
        keyword_count = sum(1 for check in checks if check.country == country)
        print(f"{index}. {country} ({keyword_count} keywords)")

    country = ask_country()
    if country not in countries:
        raise SystemExit(f"{country} is not in the active geo list.")
    if len(countries) == 1:
        raise SystemExit("Cannot delete the only active geo. Add another geo first.")

    confirmation = input(f"Type DELETE {country} to remove {country} from the active list: ").strip()
    if confirmation != f"DELETE {country}":
        print("Delete cancelled.")
        return path

    updated_checks = [check for check in checks if check.country != country]
    checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    updated_path = save_checks(updated_checks, checked_at)
    print(f"\nGeo {country} removed from active checks.")
    print(f"Updated checks saved: {updated_path}")
    print("Previous checks and reports were not deleted.")
    return updated_path


def print_saved_positions(path: Path) -> None:
    with path.open("r", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    if not rows:
        print(f"No saved positions found in {path}.")
        return

    rows.sort(key=rank_sort_key)

    print(f"Latest saved positions: {path}")
    print_markdown_table(
        ["keyword", "rank", "country", "app_id", "checked_at"],
        [
            [
                row.get("keyword", ""),
                row.get("rank", ""),
                row.get("country", ""),
                row.get("app_id", ""),
                row.get("checked_at", ""),
            ]
            for row in rows
        ],
    )


def print_today_report() -> None:
    today = date.today()
    rows = [row for row in load_report_rows(saved_report_files()) if local_date(row["checked_at"]) == today]
    if not rows:
        print("No saved position reports found for today.")
        return

    print(f"Position changes today: {today.isoformat()}")
    print_position_change_table(rows, "first_rank", "last_rank")


def print_week_report() -> None:
    end_date = date.today()
    dates = [end_date - timedelta(days=offset) for offset in range(6, -1, -1)]
    date_set = set(dates)
    rows = [
        row
        for row in load_report_rows(saved_report_files())
        if local_date(row["checked_at"]) in date_set
    ]
    if not rows:
        print("No saved position reports found for the last 7 days.")
        return

    latest_by_day: dict[tuple[str, str, str, date], dict[str, str]] = {}
    for row in rows:
        key = (row["app_id"], row["country"], row["keyword"], local_date(row["checked_at"]))
        current = latest_by_day.get(key)
        if current is None or parse_checked_at(row["checked_at"]) > parse_checked_at(current["checked_at"]):
            latest_by_day[key] = row

    keys = sorted({(row["app_id"], row["country"], row["keyword"]) for row in rows}, key=lambda item: item[2])
    sortable_rows: list[tuple[tuple[int, int | str], list[str]]] = []
    for app_id, country, keyword in keys:
        rank_by_date = {
            report_date: latest_by_day[(app_id, country, keyword, report_date)]["rank"]
            for report_date in dates
            if (app_id, country, keyword, report_date) in latest_by_day
        }
        first_rank = next((rank_by_date[report_date] for report_date in dates if report_date in rank_by_date), "")
        last_rank = next((rank_by_date[report_date] for report_date in reversed(dates) if report_date in rank_by_date), "")
        sortable_rows.append(
            (
                rank_cell_sort_key(last_rank or "not found"),
                [keyword, rank_delta(first_rank, last_rank), country, app_id]
                + [rank_by_date.get(report_date, "") for report_date in dates],
            )
        )

    table_rows = [row for _, row in sorted(sortable_rows, key=lambda item: item[0])]
    print(f"Position changes for the last 7 days: {dates[0].isoformat()}..{dates[-1].isoformat()}")
    print_markdown_table(
        ["keyword", "rank_delta", "country", "app_id"] + [report_date.isoformat() for report_date in dates],
        table_rows,
    )


def print_position_change_table(rows: list[dict[str, str]], first_label: str, last_label: str) -> None:
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault((row["app_id"], row["country"], row["keyword"]), []).append(row)

    table_rows: list[list[str]] = []
    for (app_id, country, keyword), group_rows in grouped.items():
        group_rows.sort(key=lambda row: parse_checked_at(row["checked_at"]))
        first = group_rows[0]
        last = group_rows[-1]
        table_rows.append(
            [
                keyword,
                first["rank"],
                last["rank"],
                rank_delta(first["rank"], last["rank"]),
                country,
                app_id,
                first["checked_at"],
                last["checked_at"],
            ]
        )

    table_rows.sort(key=lambda row: rank_cell_sort_key(row[2]))
    print_markdown_table(
        ["keyword", first_label, last_label, "rank_delta", "country", "app_id", "first_checked_at", "last_checked_at"],
        table_rows,
    )


def load_report_rows(paths: list[Path]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in paths:
        with path.open("r", encoding="utf-8", newline="") as file:
            for row in csv.DictReader(file):
                if row.get("checked_at") and row.get("app_id") and row.get("country") and row.get("keyword"):
                    rows.append(
                        {
                            "checked_at": row.get("checked_at", ""),
                            "app_id": row.get("app_id", ""),
                            "country": row.get("country", ""),
                            "keyword": row.get("keyword", ""),
                            "rank": row.get("rank", "not found"),
                        }
                    )
    return rows


def parse_checked_at(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def local_date(value: str) -> date:
    return parse_checked_at(value).astimezone().date()


def rank_delta(first_rank: str, last_rank: str) -> str:
    first = rank_number(first_rank)
    last = rank_number(last_rank)
    if first is None or last is None:
        return ""
    delta = last - first
    if delta > 0:
        return f"+{delta}"
    return str(delta)


def rank_number(value: str) -> int | None:
    return int(value) if value.isdigit() else None


def rank_sort_key(row: dict[str, str]) -> tuple[int, int | str]:
    return rank_cell_sort_key(row.get("rank", ""))


def rank_cell_sort_key(rank: str) -> tuple[int, int | str]:
    if rank.isdigit():
        return (0, int(rank))
    return (1, rank)


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


def add_keywords(path: Path) -> Path:
    checks = load_checks(path)
    if not checks:
        raise SystemExit(f"No checks found in {path}.")

    countries = sorted({check.country for check in checks})
    print(f"Adding keywords for countries: {', '.join(countries)}")
    keywords = ask_keywords()
    existing = {(check.country, check.keyword.casefold()) for check in checks}
    additions = [
        Check(app_id=checks[0].app_id, country=country, keyword=keyword)
        for country in countries
        for keyword in keywords
        if (country, keyword.casefold()) not in existing
    ]
    if not additions:
        print("No new keywords to add.")
        return path

    checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    updated_path = save_checks(checks + additions, checked_at)
    print(f"\nAdded {len(additions)} keyword checks.")
    print(f"Updated checks saved: {updated_path}")
    return updated_path


def run_checks(checks: list[Check], limit: int, delay_seconds: float) -> list[RankResult]:
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
        if delay_seconds > 0 and index < len(checks):
            print(f"Waiting {delay_seconds:g}s before the next request...")
            time.sleep(delay_seconds)

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


def check_positions(checks: list[Check], limit: int, output_format: str, delay_seconds: float) -> Path:
    print("\nChecking App Store positions...")
    results = run_checks(checks, limit, delay_seconds)
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


def delay_from_env() -> float:
    raw_value = os.environ.get("ASO_REQUEST_DELAY_SECONDS")
    if raw_value is None:
        return DEFAULT_DELAY_SECONDS
    return parse_delay(raw_value)


def parse_delay(value: str) -> float:
    try:
        delay = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("delay must be a number") from exc
    if delay < 0:
        raise argparse.ArgumentTypeError("delay must be 0 or greater")
    return delay


def file_timestamp(value: str) -> str:
    normalized = value.replace("+00:00", "Z")
    return normalized.replace(":", "").replace("-", "")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check App Store search positions.")
    parser.add_argument("config", nargs="?", type=Path, help="Path to checks JSON file.")
    parser.add_argument("--add-geo", action="store_true", help="Add one country to the latest saved check set.")
    parser.add_argument("--add-keywords", action="store_true", help="Append keywords to the latest saved check set.")
    parser.add_argument("--check-new-positions", action="store_true", help="Check positions for the latest saved keyword list.")
    parser.add_argument("--delete-geo", action="store_true", help="Remove one country from the active check set without deleting history.")
    parser.add_argument("--show-logs", action="store_true", help="List saved check sets and exit.")
    parser.add_argument("--show-geo-list", action="store_true", help="Print active countries in the latest saved check set and exit.")
    parser.add_argument("--show-keywords", action="store_true", help="Print the latest saved keyword list and exit.")
    parser.add_argument("--show-report-last", action="store_true", help="Print the latest saved positions report and exit.")
    parser.add_argument("--show-report-today", action="store_true", help="Print today's saved position changes and exit.")
    parser.add_argument("--show-report-week", action="store_true", help="Print saved position changes for the last 7 days and exit.")
    parser.add_argument("--update-keywords", action="store_true", help="Replace keywords in the latest saved check set.")
    parser.add_argument("--limit", type=int, default=200, help="Search depth. Default: 200.")
    parser.add_argument(
        "--delay-seconds",
        type=parse_delay,
        default=delay_from_env(),
        help="Delay between App Store requests. Default: 1.0 or ASO_REQUEST_DELAY_SECONDS.",
    )
    parser.add_argument(
        "--format",
        choices=("table", "json"),
        default="table",
        help="Output format. Default: table.",
    )
    return parser


def main() -> None:
    slash_aliases = {
        "/add-geo": "--add-geo",
        "/add-keywords": "--add-keywords",
        "/check-new-positions": "--check-new-positions",
        "/delete-geo": "--delete-geo",
        "/help": "--help",
        "/show-geo-list": "--show-geo-list",
        "/show-keywords": "--show-keywords",
        "/show-logs": "--show-logs",
        "/show-report-last": "--show-report-last",
        "/show-report-today": "--show-report-today",
        "/show-report-week": "--show-report-week",
        "/update-keywords": "--update-keywords",
    }
    if len(sys.argv) > 1 and sys.argv[1] in slash_aliases:
        sys.argv[1] = slash_aliases[sys.argv[1]]

    args = build_parser().parse_args()

    if args.show_logs:
        print_history()
        return

    if args.show_geo_list:
        print_geo_list(require_latest_checks_file())
        return

    if args.show_keywords:
        print_keywords(require_latest_checks_file())
        return

    if args.add_geo:
        add_geo(require_latest_checks_file())
        return

    if args.add_keywords:
        add_keywords(require_latest_checks_file())
        return

    if args.delete_geo:
        delete_geo(require_latest_checks_file())
        return

    if args.show_report_last:
        print_saved_positions(require_latest_report_file())
        return

    if args.show_report_today:
        print_today_report()
        return

    if args.show_report_week:
        print_week_report()
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

    check_positions(checks, args.limit, args.format, args.delay_seconds)
