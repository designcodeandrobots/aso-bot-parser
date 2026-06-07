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


def ask_checks() -> list[Check]:
    print("Шаг 1. Приложение")
    app_id = ask_app_id()

    print("\nШаг 2. Страна")
    country = ask_country()

    print("\nШаг 3. Ключевые запросы")
    keywords = ask_keywords()

    return [Check(app_id=app_id, country=country, keyword=keyword) for keyword in keywords]


def ask_app_id() -> str:
    while True:
        value = input("Введите app_id из App Store: ").strip()
        if value.isdigit():
            return value
        print("app_id должен быть числом, например 284882215.")


def ask_country() -> str:
    while True:
        value = input("Введите страну, код из 2 букв, например US: ").strip().upper()
        if len(value) == 2 and value.isalpha():
            return value
        print("Нужен двухбуквенный код страны: US, GB, DE, FR и т.д.")


def ask_keywords() -> list[str]:
    print("Вводите по одному запросу на строку. Пустая строка завершит ввод.")
    keywords: list[str] = []

    while True:
        value = input(f"Ключ #{len(keywords) + 1}: ").strip()
        if not value:
            if keywords:
                return keywords
            print("Добавьте хотя бы один ключевой запрос.")
            continue
        keywords.append(value)


def file_timestamp(value: str) -> str:
    normalized = value.replace("+00:00", "Z")
    return normalized.replace(":", "").replace("-", "")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check App Store search positions.")
    parser.add_argument("config", nargs="?", type=Path, help="Path to checks JSON file.")
    parser.add_argument("--limit", type=int, default=200, help="Search depth. Default: 200.")
    parser.add_argument(
        "--format",
        choices=("table", "json"),
        default="table",
        help="Output format. Default: table.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()

    if args.config:
        checks = load_checks(args.config)
        checks_path = args.config
    else:
        checks = ask_checks()
        checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        checks_path = save_checks(checks, checked_at)
        print(f"\nСписок проверок сохранен: {checks_path}")

    print("\nПроверяю позиции в App Store...")
    results = run_checks(checks, args.limit)
    report_path = write_report(results)

    if args.format == "json":
        print_json(results)
    else:
        print_table(results)

    print(f"\nОтчет сохранен: {report_path}")
