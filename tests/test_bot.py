from __future__ import annotations

import contextlib
import csv
import io
import json
import os
import tempfile
import time
import unittest
import urllib.error
from datetime import date
from pathlib import Path
from unittest.mock import patch

from app_store_rank_bot import bot
from app_store_rank_bot.bot import AppSearchResult, RankResult


class FixedDate(date):
    @classmethod
    def today(cls) -> date:
        return cls(2026, 6, 8)


@contextlib.contextmanager
def isolated_projects(temp_dir: str):
    root = Path(temp_dir)
    with patch.object(bot, "PROJECTS_DIR", root / "projects"):
        with patch.object(bot, "PROJECTS_FILE", root / "projects.json"):
            with patch.object(bot, "LEGACY_CHECKS_DIR", root / "checks"):
                with patch.object(bot, "LEGACY_REPORTS_DIR", root / "reports"):
                    yield root


class ReportFormatTests(unittest.TestCase):
    def test_save_and_load_active_app_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with isolated_projects(temp_dir):
                path = bot.save_active_app_id("123456")
                app_id = bot.load_active_app_id()

        self.assertEqual(path.name, "app.json")
        self.assertEqual(app_id, "123456")

    def test_ensure_active_app_id_prompts_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with isolated_projects(temp_dir):
                output = io.StringIO()
                with patch("builtins.input", return_value="123456"):
                    with contextlib.redirect_stdout(output):
                        app_id = bot.ensure_active_app_id()
                saved_app_id = bot.load_active_app_id()

        self.assertEqual(app_id, "123456")
        self.assertEqual(saved_app_id, "123456")
        self.assertIn("No saved app_id found.", output.getvalue())

    def test_delete_active_app_id_requires_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with isolated_projects(temp_dir):
                bot.save_active_app_id("123456")
                with patch("builtins.input", return_value="YES"):
                    deleted = bot.delete_active_app_id()
                app_id = bot.load_active_app_id()

        self.assertTrue(deleted)
        self.assertIsNone(app_id)

    def test_add_keywords_creates_first_check_set_when_none_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with isolated_projects(temp_dir):
                with patch("builtins.input", side_effect=["US", "ai chat"]):
                    path = bot.add_keywords_or_create_first_set("123456")
                checks = bot.load_checks(path)

        self.assertEqual(checks, [bot.Check(app_id="123456", country="US", keyword="ai chat")])

    def test_add_keywords_adds_to_selected_geos_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = bot.save_checks(
                [
                    bot.Check(app_id="123456", country="US", keyword="us scanner"),
                    bot.Check(app_id="123456", country="GB", keyword="gb scanner"),
                ],
                "2026-06-08T07:21:00+00:00",
                Path(temp_dir),
            )
            with patch("builtins.input", side_effect=["GB", "gb scan app"]):
                updated_path = bot.add_keywords(path)
            checks = bot.load_checks(updated_path)

        self.assertEqual(
            checks,
            [
                bot.Check(app_id="123456", country="US", keyword="us scanner"),
                bot.Check(app_id="123456", country="GB", keyword="gb scanner"),
                bot.Check(app_id="123456", country="GB", keyword="gb scan app"),
            ],
        )

    def test_update_keywords_updates_selected_geos_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = bot.save_checks(
                [
                    bot.Check(app_id="123456", country="US", keyword="us scanner"),
                    bot.Check(app_id="123456", country="GB", keyword="gb scanner"),
                ],
                "2026-06-08T07:21:00+00:00",
                Path(temp_dir),
            )
            with patch("builtins.input", side_effect=["GB", "gb scanner new"]):
                updated_path = bot.update_keywords(path)
            checks = bot.load_checks(updated_path)

        self.assertEqual(
            checks,
            [
                bot.Check(app_id="123456", country="US", keyword="us scanner"),
                bot.Check(app_id="123456", country="GB", keyword="gb scanner new"),
            ],
        )

    def test_keywords_menu_can_go_back(self) -> None:
        output = io.StringIO()
        with patch("builtins.input", return_value="0"):
            with contextlib.redirect_stdout(output):
                bot.run_keywords_menu("123456")

        self.assertIn("Keywords", output.getvalue())
        self.assertIn("Add keywords by geo", output.getvalue())
        self.assertIn("Update keywords by geo", output.getvalue())
        self.assertIn("0. Back", output.getvalue())

    def test_reports_menu_can_go_back(self) -> None:
        output = io.StringIO()
        with patch("builtins.input", return_value="0"):
            with contextlib.redirect_stdout(output):
                bot.run_reports_menu("123456")

        self.assertIn("Reports", output.getvalue())
        self.assertIn("0. Back", output.getvalue())

    def test_parse_countries_accepts_multiple_codes(self) -> None:
        self.assertEqual(bot.parse_countries("us, gb; de, US"), ["US", "GB", "DE"])

    def test_add_geo_adds_multiple_geos_with_separate_keywords(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = bot.save_checks(
                [bot.Check(app_id="123456", country="US", keyword="scanner")],
                "2026-06-08T07:21:00+00:00",
                Path(temp_dir),
            )
            with patch("builtins.input", side_effect=["GB, DE", "gb scanner", "de scanner; de scan"]):
                updated_path = bot.add_geo(path)
            checks = bot.load_checks(updated_path)

        self.assertEqual(
            checks,
            [
                bot.Check(app_id="123456", country="US", keyword="scanner"),
                bot.Check(app_id="123456", country="GB", keyword="gb scanner"),
                bot.Check(app_id="123456", country="DE", keyword="de scanner"),
                bot.Check(app_id="123456", country="DE", keyword="de scan"),
            ],
        )

    def test_delete_geo_removes_multiple_geos(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = bot.save_checks(
                [
                    bot.Check(app_id="123456", country="US", keyword="us scanner"),
                    bot.Check(app_id="123456", country="GB", keyword="gb scanner"),
                    bot.Check(app_id="123456", country="DE", keyword="de scanner"),
                ],
                "2026-06-08T07:21:00+00:00",
                Path(temp_dir),
            )
            with patch("builtins.input", side_effect=["GB, DE", "DELETE GB, DE"]):
                updated_path = bot.delete_geo(path)
            checks = bot.load_checks(updated_path)

        self.assertEqual(checks, [bot.Check(app_id="123456", country="US", keyword="us scanner")])

    def test_print_top_apps_outputs_app_table(self) -> None:
        class FakeClient:
            def search_apps(self, country: str, keyword: str, limit: int = 10) -> list[AppSearchResult]:
                return [
                    AppSearchResult(
                        position=1,
                        app_id="123456",
                        app_name="Scanner One",
                        developer="Example Dev",
                    )
                ]

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            bot.print_top_apps("US", "scanner", FakeClient())

        self.assertIn("Top 10 apps for US / scanner", output.getvalue())
        self.assertIn("| position | app_name", output.getvalue())
        self.assertIn("| 1        | Scanner One", output.getvalue())

    def test_run_checks_returns_every_keyword(self) -> None:
        checks = [
            bot.Check(app_id="123456", country="US", keyword="first"),
            bot.Check(app_id="123456", country="US", keyword="second"),
        ]

        def fake_find_rank(self: object, app_id: str, country: str, keyword: str, limit: int = bot.DEFAULT_SEARCH_LIMIT) -> int:
            return {"first": 1, "second": 2}[keyword]

        with patch.object(bot.AppStoreClient, "find_rank", fake_find_rank):
            results = bot.run_checks(checks, limit=bot.DEFAULT_SEARCH_LIMIT)

        self.assertEqual({result.keyword: result.rank for result in results}, {"first": 1, "second": 2})

    def test_find_rank_uses_a_single_request(self) -> None:
        client = bot.AppStoreClient()
        limits: list[int] = []

        def fake_search_payload(country: str, keyword: str, limit: int) -> dict[str, object]:
            limits.append(limit)
            return {"results": [{"trackId": "111"} for _ in range(22)] + [{"trackId": "123456"}]}

        with patch.object(client, "search_payload", fake_search_payload):
            rank = client.find_rank("123456", "US", "scanner")

        self.assertEqual(rank, 23)
        self.assertEqual(limits, [bot.DEFAULT_SEARCH_LIMIT])

    def test_find_rank_rejects_an_empty_result_set(self) -> None:
        client = bot.AppStoreClient()

        with patch.object(client, "search_payload", lambda country, keyword, limit: {"results": []}):
            with self.assertRaises(bot.SuspectEmptyResults):
                client.find_rank("123456", "US", "scanner")

    def test_search_payload_raises_rate_limited_on_403(self) -> None:
        client = bot.AppStoreClient(pacer=bot.RequestPacer(0.0))

        def raise_403(request: object, timeout: int = 20) -> None:
            raise urllib.error.HTTPError("url", 403, "Forbidden", None, None)

        with patch.object(bot.urllib.request, "urlopen", raise_403):
            with self.assertRaises(bot.RateLimited):
                client.search_payload("US", "scanner", 200)

    def test_run_checks_pauses_and_retries_the_throttled_keyword(self) -> None:
        checks = [bot.Check(app_id="123456", country="US", keyword="scanner")]
        calls: list[str] = []
        pauses: list[float] = []

        def fake_find_rank(self: object, app_id: str, country: str, keyword: str, limit: int = bot.DEFAULT_SEARCH_LIMIT) -> int:
            calls.append(keyword)
            if len(calls) == 1:
                raise bot.RateLimited("HTTP 403")
            return 4

        with patch.object(bot.AppStoreClient, "find_rank", fake_find_rank):
            with patch.object(bot.RequestPacer, "pause", lambda self, seconds: pauses.append(seconds)):
                results = bot.run_checks(checks, limit=bot.DEFAULT_SEARCH_LIMIT)

        self.assertEqual(pauses, [bot.THROTTLE_PAUSE_SECONDS[0]])
        self.assertEqual([result.rank for result in results], [4])
        self.assertFalse(results[0].failed)

    def test_run_checks_gives_up_after_repeated_throttling(self) -> None:
        checks = [
            bot.Check(app_id="123456", country="US", keyword="first"),
            bot.Check(app_id="123456", country="US", keyword="second"),
        ]

        def always_throttled(self: object, app_id: str, country: str, keyword: str, limit: int = bot.DEFAULT_SEARCH_LIMIT) -> int:
            raise bot.RateLimited("HTTP 403")

        with patch.object(bot.AppStoreClient, "find_rank", always_throttled):
            with patch.object(bot.RequestPacer, "pause", lambda self, seconds: None):
                results = bot.run_checks(checks, limit=bot.DEFAULT_SEARCH_LIMIT)

        self.assertEqual(len(results), 2)
        self.assertTrue(all(result.failed for result in results))

    def test_markdown_table_escapes_pipe_characters(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            bot.print_markdown_table(["app_name"], [["PDF Scanner | Document Scan"]])

        self.assertIn("PDF Scanner \\| Document Scan", output.getvalue())

    def test_write_report_uses_public_column_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = bot.write_report(
                [
                    RankResult(
                        app_id="123456",
                        country="US",
                        keyword="ai chat",
                        rank=4,
                        checked_at="2026-06-08T07:21:00+00:00",
                    )
                ],
                Path(temp_dir),
            )

            with path.open("r", encoding="utf-8", newline="") as file:
                rows = list(csv.reader(file))

        self.assertEqual(rows[0], ["keyword", "rank", "country", "app_id", "date"])
        self.assertEqual(rows[1], ["ai chat", "4", "US", "123456", "2026-06-08T07:21:00+00:00"])

    def test_write_report_sorts_rows_by_rank(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = bot.write_report(
                [
                    RankResult("123456", "US", "rank three", 3, "2026-06-08T07:21:00+00:00"),
                    RankResult("123456", "US", "rank one", 1, "2026-06-08T07:21:00+00:00"),
                    RankResult("123456", "US", "not found", None, "2026-06-08T07:21:00+00:00"),
                    RankResult("123456", "US", "rank two", 2, "2026-06-08T07:21:00+00:00"),
                ],
                Path(temp_dir),
            )

            with path.open("r", encoding="utf-8", newline="") as file:
                rows = list(csv.DictReader(file))

        self.assertEqual([row["keyword"] for row in rows], ["rank one", "rank two", "rank three", "not found"])

    def test_write_report_uses_dash_for_missing_rank(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = bot.write_report(
                [
                    RankResult("123456", "US", "missing rank", None, "2026-06-08T07:21:00+00:00"),
                ],
                Path(temp_dir),
            )

            with path.open("r", encoding="utf-8", newline="") as file:
                rows = list(csv.reader(file))

        self.assertEqual(rows[1], ["missing rank", "-", "US", "123456", "2026-06-08T07:21:00+00:00"])

    def test_print_table_uses_dash_for_missing_rank(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            bot.print_table(
                [
                    RankResult("123456", "US", "missing rank", None, "2026-06-08T07:21:00+00:00"),
                ]
            )

        rows = list(csv.reader(io.StringIO(output.getvalue())))
        self.assertEqual(rows[1], ["missing rank", "-", "US", "123456", "2026-06-08T07:21:00+00:00"])

    def test_load_report_rows_supports_old_checked_at_column(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "positions-old.csv"
            path.write_text(
                "checked_at,app_id,country,keyword,rank\n"
                "2026-06-08T07:21:00+00:00,123456,US,ai chat,4\n",
                encoding="utf-8",
            )

            rows = bot.load_report_rows([path])

        self.assertEqual(
            rows,
            [
                {
                    "date": "2026-06-08T07:21:00+00:00",
                    "app_id": "123456",
                    "country": "US",
                    "keyword": "ai chat",
                    "rank": "4",
                }
            ],
        )

    def test_load_report_rows_converts_not_found_to_dash(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "positions-old.csv"
            path.write_text(
                "keyword,rank,country,app_id,date\n"
                "ai chat,not found,US,123456,2026-06-08T07:21:00+00:00\n",
                encoding="utf-8",
            )

            rows = bot.load_report_rows([path])

        self.assertEqual(rows[0]["rank"], "-")

    def test_print_saved_positions_uses_public_column_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "positions-new.csv"
            path.write_text(
                "keyword,rank,country,app_id,date\n"
                "ai chat,4,US,123456,2026-06-08T07:21:00+00:00\n",
                encoding="utf-8",
            )

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                bot.print_saved_positions(path)

        self.assertIn("| keyword | rank | country | app_id | date", output.getvalue())

    def test_print_saved_positions_uses_dash_for_not_found_rank(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "positions-new.csv"
            path.write_text(
                "keyword,rank,country,app_id,date\n"
                "ai chat,not found,US,123456,2026-06-08T07:21:00+00:00\n",
                encoding="utf-8",
            )

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                bot.print_saved_positions(path)

        self.assertIn("| ai chat | -", output.getvalue())
        self.assertNotIn("not found", output.getvalue())

    def test_position_change_table_sorts_by_latest_rank(self) -> None:
        rows = [
            {
                "date": "2026-06-08T08:00:00+00:00",
                "app_id": "123456",
                "country": "US",
                "keyword": "rank ten",
                "rank": "10",
            },
            {
                "date": "2026-06-08T08:00:00+00:00",
                "app_id": "123456",
                "country": "US",
                "keyword": "rank one",
                "rank": "1",
            },
            {
                "date": "2026-06-08T08:00:00+00:00",
                "app_id": "123456",
                "country": "US",
                "keyword": "rank five",
                "rank": "5",
            },
        ]

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            bot.print_position_change_table(rows, "first_rank", "last_rank")

        table_lines = [line for line in output.getvalue().splitlines() if line.startswith("| rank")]
        self.assertTrue(table_lines[0].startswith("| rank one"))
        self.assertTrue(table_lines[1].startswith("| rank five"))
        self.assertTrue(table_lines[2].startswith("| rank ten"))

    def test_position_change_table_uses_dash_for_not_found_rank(self) -> None:
        rows = [
            {
                "date": "2026-06-08T08:00:00+00:00",
                "app_id": "123456",
                "country": "US",
                "keyword": "missing rank",
                "rank": "not found",
            }
        ]

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            bot.print_position_change_table(rows, "first_rank", "last_rank")

        self.assertIn("| missing rank | -", output.getvalue())
        self.assertNotIn("not found", output.getvalue())

    def test_print_week_report_prints_ready_message_with_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            reports_dir = Path(temp_dir)
            for day in range(2, 9):
                report_date = f"2026-06-{day:02d}T08:00:00+00:00"
                report_path = reports_dir / f"positions-202606{day:02d}T080000Z.csv"
                report_path.write_text(
                    "keyword,rank,country,app_id,date\n"
                    f"ai chat,{day},US,123456,{report_date}\n",
                    encoding="utf-8",
                )

            output = io.StringIO()
            with patch.object(bot, "date", FixedDate):
                with contextlib.redirect_stdout(output):
                    bot.print_week_report(reports_dir)

            weekly_report_path = Path(temp_dir) / "week-report-2026-06-02..2026-06-08.csv"
            with weekly_report_path.open("r", encoding="utf-8", newline="") as file:
                rows = list(csv.reader(file))

        self.assertEqual(output.getvalue(), f"Weekly report ready: {weekly_report_path}\n")
        self.assertEqual(
            rows,
            [
                [
                    "keyword",
                    "country",
                    "app_id",
                    "2026-06-02",
                    "2026-06-03",
                    "2026-06-04",
                    "2026-06-05",
                    "2026-06-06",
                    "2026-06-07",
                    "2026-06-08",
                ],
                ["ai chat", "US", "123456", "2", "3", "4", "5", "6", "7", "8"],
            ],
        )

    def test_print_week_report_is_ready_with_one_report_day(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            reports_dir = Path(temp_dir)
            report_path = reports_dir / "positions-20260608T080000Z.csv"
            report_path.write_text(
                "keyword,rank,country,app_id,date\n"
                "ai chat,4,US,123456,2026-06-08T08:00:00+00:00\n",
                encoding="utf-8",
            )

            output = io.StringIO()
            with patch.object(bot, "date", FixedDate):
                with contextlib.redirect_stdout(output):
                    bot.print_week_report(reports_dir)

            weekly_report_path = Path(temp_dir) / "week-report-2026-06-02..2026-06-08.csv"
            with weekly_report_path.open("r", encoding="utf-8", newline="") as file:
                rows = list(csv.reader(file))

        self.assertEqual(output.getvalue(), f"Weekly report ready: {weekly_report_path}\n")
        self.assertEqual(
            rows[1],
            ["ai chat", "US", "123456", "-", "-", "-", "-", "-", "-", "4"],
        )

    def test_print_week_report_uses_latest_report_file_for_day(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            reports_dir = Path(temp_dir)
            older_report_path = reports_dir / "positions-20260608T080000Z.csv"
            older_report_path.write_text(
                "keyword,rank,country,app_id,date\n"
                "ai chat,4,US,123456,2026-06-08T08:00:00+00:00\n",
                encoding="utf-8",
            )
            newer_report_path = reports_dir / "positions-20260608T090000Z.csv"
            newer_report_path.write_text(
                "keyword,rank,country,app_id,date\n"
                "ai chat,2,US,123456,2026-06-08T09:00:00+00:00\n",
                encoding="utf-8",
            )
            os.utime(older_report_path, (1, 1))
            os.utime(newer_report_path, (2, 2))

            output = io.StringIO()
            with patch.object(bot, "date", FixedDate):
                with contextlib.redirect_stdout(output):
                    bot.print_week_report(reports_dir)

            weekly_report_path = Path(temp_dir) / "week-report-2026-06-02..2026-06-08.csv"
            with weekly_report_path.open("r", encoding="utf-8", newline="") as file:
                rows = list(csv.reader(file))

        self.assertEqual(output.getvalue(), f"Weekly report ready: {weekly_report_path}\n")
        self.assertEqual(rows[1], ["ai chat", "US", "123456", "-", "-", "-", "-", "-", "-", "2"])

    def test_print_week_report_writes_dash_for_not_found_rank(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            reports_dir = Path(temp_dir)
            report_path = reports_dir / "positions-20260608T080000Z.csv"
            report_path.write_text(
                "keyword,rank,country,app_id,date\n"
                "ai chat,not found,US,123456,2026-06-08T08:00:00+00:00\n",
                encoding="utf-8",
            )

            output = io.StringIO()
            with patch.object(bot, "date", FixedDate):
                with contextlib.redirect_stdout(output):
                    bot.print_week_report(reports_dir)

            weekly_report_path = Path(temp_dir) / "week-report-2026-06-02..2026-06-08.csv"
            with weekly_report_path.open("r", encoding="utf-8", newline="") as file:
                rows = list(csv.reader(file))

        self.assertEqual(output.getvalue(), f"Weekly report ready: {weekly_report_path}\n")
        self.assertEqual(rows[1], ["ai chat", "US", "123456", "-", "-", "-", "-", "-", "-", "-"])

    def test_print_week_report_sorts_by_latest_rank(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            reports_dir = Path(temp_dir)
            report_path = reports_dir / "positions-20260608T080000Z.csv"
            report_path.write_text(
                "keyword,rank,country,app_id,date\n"
                "z top,1,US,123456,2026-06-08T08:00:00+00:00\n"
                "a second,2,US,123456,2026-06-08T08:00:00+00:00\n",
                encoding="utf-8",
            )

            output = io.StringIO()
            with patch.object(bot, "date", FixedDate):
                with contextlib.redirect_stdout(output):
                    bot.print_week_report(reports_dir)

            weekly_report_path = Path(temp_dir) / "week-report-2026-06-02..2026-06-08.csv"
            with weekly_report_path.open("r", encoding="utf-8", newline="") as file:
                rows = list(csv.reader(file))

        self.assertEqual(rows[1][0], "z top")
        self.assertEqual(rows[2][0], "a second")

    def test_print_week_report_explains_no_reports_for_week(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = io.StringIO()
            with patch.object(bot, "date", FixedDate):
                with contextlib.redirect_stdout(output):
                    bot.print_week_report(Path(temp_dir))

        self.assertIn("Weekly report not ready: week-report-2026-06-02..2026-06-08", output.getvalue())
        self.assertIn("Reason: no saved position reports found for the last 7 days.", output.getvalue())

    def test_print_month_report_prints_ready_message_with_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            reports_dir = Path(temp_dir)
            for day in (1, 8):
                report_date = f"2026-06-{day:02d}T08:00:00+00:00"
                report_path = reports_dir / f"positions-202606{day:02d}T080000Z.csv"
                report_path.write_text(
                    "keyword,rank,country,app_id,date\n"
                    f"ai chat,{day},US,123456,{report_date}\n",
                    encoding="utf-8",
                )

            output = io.StringIO()
            with patch.object(bot, "date", FixedDate):
                with contextlib.redirect_stdout(output):
                    bot.print_month_report(reports_dir)

            monthly_report_path = Path(temp_dir) / "month-report-2026-06-01..2026-06-08.csv"
            with monthly_report_path.open("r", encoding="utf-8", newline="") as file:
                rows = list(csv.reader(file))

        self.assertEqual(output.getvalue(), f"Monthly report ready: {monthly_report_path}\n")
        self.assertEqual(
            rows,
            [
                [
                    "keyword",
                    "country",
                    "app_id",
                    "2026-06-01",
                    "2026-06-02",
                    "2026-06-03",
                    "2026-06-04",
                    "2026-06-05",
                    "2026-06-06",
                    "2026-06-07",
                    "2026-06-08",
                ],
                ["ai chat", "US", "123456", "1", "-", "-", "-", "-", "-", "-", "8"],
            ],
        )

    def test_print_month_report_uses_latest_report_file_for_day(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            reports_dir = Path(temp_dir)
            older_report_path = reports_dir / "positions-20260608T080000Z.csv"
            older_report_path.write_text(
                "keyword,rank,country,app_id,date\n"
                "ai chat,4,US,123456,2026-06-08T08:00:00+00:00\n",
                encoding="utf-8",
            )
            newer_report_path = reports_dir / "positions-20260608T090000Z.csv"
            newer_report_path.write_text(
                "keyword,rank,country,app_id,date\n"
                "ai chat,2,US,123456,2026-06-08T09:00:00+00:00\n",
                encoding="utf-8",
            )
            os.utime(older_report_path, (1, 1))
            os.utime(newer_report_path, (2, 2))

            output = io.StringIO()
            with patch.object(bot, "date", FixedDate):
                with contextlib.redirect_stdout(output):
                    bot.print_month_report(reports_dir)

            monthly_report_path = Path(temp_dir) / "month-report-2026-06-01..2026-06-08.csv"
            with monthly_report_path.open("r", encoding="utf-8", newline="") as file:
                rows = list(csv.reader(file))

        self.assertEqual(output.getvalue(), f"Monthly report ready: {monthly_report_path}\n")
        self.assertEqual(rows[1], ["ai chat", "US", "123456", "-", "-", "-", "-", "-", "-", "-", "2"])

    def test_print_month_report_explains_no_reports_for_month(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = io.StringIO()
            with patch.object(bot, "date", FixedDate):
                with contextlib.redirect_stdout(output):
                    bot.print_month_report(Path(temp_dir))

        self.assertIn("Monthly report not ready: month-report-2026-06-01..2026-06-08", output.getvalue())
        self.assertIn("Reason: no saved position reports found for the current month.", output.getvalue())


class MultiAppProjectTests(unittest.TestCase):
    def test_legacy_layout_requires_migration(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with isolated_projects(temp_dir) as root:
                (root / "checks").mkdir()
                (root / "checks" / "app.json").write_text('{"app_id": "6443812062"}\n', encoding="utf-8")
                with self.assertRaises(SystemExit) as raised:
                    bot.ensure_active_app_id()

        self.assertIn("--migrate-projects", str(raised.exception))

    def test_list_apps_marks_active_project(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with isolated_projects(temp_dir):
                bot.save_active_app_id("6443812062", name="Doc Scanner PDF, Convert & OCR")
                bot.save_project_app("111", name="Other App")
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    bot.list_apps()

        self.assertIn("6443812062  Doc Scanner PDF, Convert & OCR (active)", output.getvalue())
        self.assertIn("111  Other App", output.getvalue())
        self.assertNotIn("111  Other App (active)", output.getvalue())

    def test_use_app_switches_active_project(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with isolated_projects(temp_dir):
                bot.save_active_app_id("6443812062")
                bot.save_project_app("111")
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    bot.use_app("111")
                self.assertEqual(bot.load_active_project_id(), "111")
                self.assertEqual(bot.resolve_app_id(), "111")
                self.assertEqual(bot.resolve_app_id("6443812062"), "6443812062")

        self.assertIn("Active project: 111", output.getvalue())

    def test_use_app_rejects_unknown_project(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with isolated_projects(temp_dir):
                with self.assertRaises(SystemExit) as raised:
                    bot.use_app("999")

        self.assertIn("No project for app_id=999", str(raised.exception))

    def test_migrate_projects_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with isolated_projects(temp_dir) as root:
                checks = root / "checks"
                reports = root / "reports"
                checks.mkdir()
                reports.mkdir()
                (checks / "app.json").write_text(
                    '{\n  "app_id": "6443812062",\n  "saved_at": "2026-06-08T13:10:00+00:00"\n}\n',
                    encoding="utf-8",
                )
                (checks / "checks-20260607T113705Z.json").write_text('{"checks": []}\n', encoding="utf-8")
                (reports / "positions-20260607T113719Z.csv").write_text(
                    "keyword,rank,country,app_id,date\nscanner,1,US,6443812062,2026-06-07T11:37:19+00:00\n",
                    encoding="utf-8",
                )

                bot.migrate_projects()
                first_app = (root / "projects" / "6443812062" / "app.json").read_text(encoding="utf-8")
                first_checks = list((root / "projects" / "6443812062" / "checks").glob("checks-*.json"))
                first_reports = list((root / "projects" / "6443812062" / "reports").iterdir())
                bot.migrate_projects()
                second_app = (root / "projects" / "6443812062" / "app.json").read_text(encoding="utf-8")

                self.assertFalse((root / "checks").exists())
                self.assertFalse((root / "reports").exists())
                self.assertEqual(json.loads((root / "projects.json").read_text(encoding="utf-8")), {"active": "6443812062"})
                self.assertEqual(len(first_checks), 1)
                self.assertEqual(len(first_reports), 1)
                self.assertEqual(first_app, second_app)
                self.assertEqual(bot.load_active_app_id(), "6443812062")

    def test_write_report_stays_in_selected_project(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with isolated_projects(temp_dir):
                bot.save_active_app_id("111")
                bot.save_project_app("222")
                path = bot.write_report(
                    [RankResult("222", "US", "scanner", 1, "2026-06-08T07:21:00+00:00")],
                    bot.reports_dir("222"),
                )

                self.assertEqual(path.parent, bot.reports_dir("222"))
                self.assertFalse(any(bot.reports_dir("111").glob("positions-*.csv")))

    def test_run_one_check_keeps_failures_local(self) -> None:
        check = bot.Check(app_id="123456", country="US", keyword="scanner")

        def fake_find_rank(self: object, app_id: str, country: str, keyword: str, limit: int = bot.DEFAULT_SEARCH_LIMIT) -> int:
            raise TimeoutError("temporary")

        with patch.object(bot.AppStoreClient, "find_rank", fake_find_rank):
            with patch.object(bot.time, "sleep", return_value=None):
                result = bot.run_one_check(bot.AppStoreClient(), check, bot.DEFAULT_SEARCH_LIMIT, "2026-06-08T07:21:00+00:00")

        self.assertTrue(result.failed)
        self.assertIsNone(result.rank)


if __name__ == "__main__":
    unittest.main()
