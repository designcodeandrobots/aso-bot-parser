from __future__ import annotations

import contextlib
import csv
import io
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from app_store_rank_bot import bot
from app_store_rank_bot.bot import AppSearchResult, RankResult


class FixedDate(date):
    @classmethod
    def today(cls) -> date:
        return cls(2026, 6, 8)


class ReportFormatTests(unittest.TestCase):
    def test_save_and_load_active_app_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            original_checks_dir = bot.CHECKS_DIR
            original_app_id_file = bot.APP_ID_FILE
            bot.CHECKS_DIR = Path(temp_dir)
            bot.APP_ID_FILE = Path(temp_dir) / "app.json"
            try:
                path = bot.save_active_app_id("123456")
                app_id = bot.load_active_app_id()
            finally:
                bot.CHECKS_DIR = original_checks_dir
                bot.APP_ID_FILE = original_app_id_file

        self.assertEqual(path.name, "app.json")
        self.assertEqual(app_id, "123456")

    def test_ensure_active_app_id_prompts_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            original_checks_dir = bot.CHECKS_DIR
            original_app_id_file = bot.APP_ID_FILE
            bot.CHECKS_DIR = Path(temp_dir)
            bot.APP_ID_FILE = Path(temp_dir) / "app.json"
            try:
                output = io.StringIO()
                with patch("builtins.input", return_value="123456"):
                    with contextlib.redirect_stdout(output):
                        app_id = bot.ensure_active_app_id()
                saved_app_id = bot.load_active_app_id()
            finally:
                bot.CHECKS_DIR = original_checks_dir
                bot.APP_ID_FILE = original_app_id_file

        self.assertEqual(app_id, "123456")
        self.assertEqual(saved_app_id, "123456")
        self.assertIn("No saved app_id found.", output.getvalue())

    def test_delete_active_app_id_requires_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            original_checks_dir = bot.CHECKS_DIR
            original_app_id_file = bot.APP_ID_FILE
            bot.CHECKS_DIR = Path(temp_dir)
            bot.APP_ID_FILE = Path(temp_dir) / "app.json"
            try:
                bot.save_active_app_id("123456")
                with patch("builtins.input", return_value="YES"):
                    deleted = bot.delete_active_app_id()
                app_id = bot.load_active_app_id()
            finally:
                bot.CHECKS_DIR = original_checks_dir
                bot.APP_ID_FILE = original_app_id_file

        self.assertTrue(deleted)
        self.assertIsNone(app_id)

    def test_add_keywords_creates_first_check_set_when_none_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            original_checks_dir = bot.CHECKS_DIR
            original_app_id_file = bot.APP_ID_FILE
            bot.CHECKS_DIR = Path(temp_dir)
            bot.APP_ID_FILE = Path(temp_dir) / "app.json"
            try:
                with patch("builtins.input", side_effect=["US", "ai chat"]):
                    path = bot.add_keywords_or_create_first_set("123456")
                checks = bot.load_checks(path)
            finally:
                bot.CHECKS_DIR = original_checks_dir
                bot.APP_ID_FILE = original_app_id_file

        self.assertEqual(checks, [bot.Check(app_id="123456", country="US", keyword="ai chat")])

    def test_add_keywords_adds_to_selected_geos_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            original_checks_dir = bot.CHECKS_DIR
            bot.CHECKS_DIR = Path(temp_dir)
            try:
                path = bot.save_checks(
                    [
                        bot.Check(app_id="123456", country="US", keyword="us scanner"),
                        bot.Check(app_id="123456", country="GB", keyword="gb scanner"),
                    ],
                    "2026-06-08T07:21:00+00:00",
                )
                with patch("builtins.input", side_effect=["GB", "gb scan app"]):
                    updated_path = bot.add_keywords(path)
                checks = bot.load_checks(updated_path)
            finally:
                bot.CHECKS_DIR = original_checks_dir

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
            original_checks_dir = bot.CHECKS_DIR
            bot.CHECKS_DIR = Path(temp_dir)
            try:
                path = bot.save_checks(
                    [
                        bot.Check(app_id="123456", country="US", keyword="us scanner"),
                        bot.Check(app_id="123456", country="GB", keyword="gb scanner"),
                    ],
                    "2026-06-08T07:21:00+00:00",
                )
                with patch("builtins.input", side_effect=["GB", "gb scanner new"]):
                    updated_path = bot.update_keywords(path)
                checks = bot.load_checks(updated_path)
            finally:
                bot.CHECKS_DIR = original_checks_dir

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
                bot.run_reports_menu()

        self.assertIn("Reports", output.getvalue())
        self.assertIn("0. Back", output.getvalue())

    def test_parse_countries_accepts_multiple_codes(self) -> None:
        self.assertEqual(bot.parse_countries("us, gb; de, US"), ["US", "GB", "DE"])

    def test_add_geo_adds_multiple_geos_with_separate_keywords(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            original_checks_dir = bot.CHECKS_DIR
            bot.CHECKS_DIR = Path(temp_dir)
            try:
                path = bot.save_checks([bot.Check(app_id="123456", country="US", keyword="scanner")], "2026-06-08T07:21:00+00:00")
                with patch("builtins.input", side_effect=["GB, DE", "gb scanner", "de scanner; de scan"]):
                    updated_path = bot.add_geo(path)
                checks = bot.load_checks(updated_path)
            finally:
                bot.CHECKS_DIR = original_checks_dir

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
            original_checks_dir = bot.CHECKS_DIR
            bot.CHECKS_DIR = Path(temp_dir)
            try:
                path = bot.save_checks(
                    [
                        bot.Check(app_id="123456", country="US", keyword="us scanner"),
                        bot.Check(app_id="123456", country="GB", keyword="gb scanner"),
                        bot.Check(app_id="123456", country="DE", keyword="de scanner"),
                    ],
                    "2026-06-08T07:21:00+00:00",
                )
                with patch("builtins.input", side_effect=["GB, DE", "DELETE GB, DE"]):
                    updated_path = bot.delete_geo(path)
                checks = bot.load_checks(updated_path)
            finally:
                bot.CHECKS_DIR = original_checks_dir

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

    def test_markdown_table_escapes_pipe_characters(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            bot.print_markdown_table(["app_name"], [["PDF Scanner | Document Scan"]])

        self.assertIn("PDF Scanner \\| Document Scan", output.getvalue())

    def test_write_report_uses_public_column_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            original_reports_dir = bot.REPORTS_DIR
            bot.REPORTS_DIR = Path(temp_dir)
            try:
                path = bot.write_report(
                    [
                        RankResult(
                            app_id="123456",
                            country="US",
                            keyword="ai chat",
                            rank=4,
                            checked_at="2026-06-08T07:21:00+00:00",
                        )
                    ]
                )
            finally:
                bot.REPORTS_DIR = original_reports_dir

            with path.open("r", encoding="utf-8", newline="") as file:
                rows = list(csv.reader(file))

        self.assertEqual(rows[0], ["keyword", "rank", "country", "app_id", "date"])
        self.assertEqual(rows[1], ["ai chat", "4", "US", "123456", "2026-06-08T07:21:00+00:00"])

    def test_write_report_sorts_rows_by_rank(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            original_reports_dir = bot.REPORTS_DIR
            bot.REPORTS_DIR = Path(temp_dir)
            try:
                path = bot.write_report(
                    [
                        RankResult("123456", "US", "rank three", 3, "2026-06-08T07:21:00+00:00"),
                        RankResult("123456", "US", "rank one", 1, "2026-06-08T07:21:00+00:00"),
                        RankResult("123456", "US", "not found", None, "2026-06-08T07:21:00+00:00"),
                        RankResult("123456", "US", "rank two", 2, "2026-06-08T07:21:00+00:00"),
                    ]
                )
            finally:
                bot.REPORTS_DIR = original_reports_dir

            with path.open("r", encoding="utf-8", newline="") as file:
                rows = list(csv.DictReader(file))

        self.assertEqual([row["keyword"] for row in rows], ["rank one", "rank two", "rank three", "not found"])

    def test_write_report_uses_dash_for_missing_rank(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            original_reports_dir = bot.REPORTS_DIR
            bot.REPORTS_DIR = Path(temp_dir)
            try:
                path = bot.write_report(
                    [
                        RankResult("123456", "US", "missing rank", None, "2026-06-08T07:21:00+00:00"),
                    ]
                )
            finally:
                bot.REPORTS_DIR = original_reports_dir

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
            original_reports_dir = bot.REPORTS_DIR
            bot.REPORTS_DIR = Path(temp_dir)
            try:
                for day in range(2, 9):
                    report_date = f"2026-06-{day:02d}T08:00:00+00:00"
                    report_path = bot.REPORTS_DIR / f"positions-202606{day:02d}T080000Z.csv"
                    report_path.write_text(
                        "keyword,rank,country,app_id,date\n"
                        f"ai chat,{day},US,123456,{report_date}\n",
                        encoding="utf-8",
                    )

                output = io.StringIO()
                with patch.object(bot, "date", FixedDate):
                    with contextlib.redirect_stdout(output):
                        bot.print_week_report()
            finally:
                bot.REPORTS_DIR = original_reports_dir

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
            original_reports_dir = bot.REPORTS_DIR
            bot.REPORTS_DIR = Path(temp_dir)
            try:
                report_path = bot.REPORTS_DIR / "positions-20260608T080000Z.csv"
                report_path.write_text(
                    "keyword,rank,country,app_id,date\n"
                    "ai chat,4,US,123456,2026-06-08T08:00:00+00:00\n",
                    encoding="utf-8",
                )

                output = io.StringIO()
                with patch.object(bot, "date", FixedDate):
                    with contextlib.redirect_stdout(output):
                        bot.print_week_report()
            finally:
                bot.REPORTS_DIR = original_reports_dir

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
            original_reports_dir = bot.REPORTS_DIR
            bot.REPORTS_DIR = Path(temp_dir)
            try:
                older_report_path = bot.REPORTS_DIR / "positions-20260608T080000Z.csv"
                older_report_path.write_text(
                    "keyword,rank,country,app_id,date\n"
                    "ai chat,4,US,123456,2026-06-08T08:00:00+00:00\n",
                    encoding="utf-8",
                )
                newer_report_path = bot.REPORTS_DIR / "positions-20260608T090000Z.csv"
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
                        bot.print_week_report()
            finally:
                bot.REPORTS_DIR = original_reports_dir

            weekly_report_path = Path(temp_dir) / "week-report-2026-06-02..2026-06-08.csv"
            with weekly_report_path.open("r", encoding="utf-8", newline="") as file:
                rows = list(csv.reader(file))

        self.assertEqual(output.getvalue(), f"Weekly report ready: {weekly_report_path}\n")
        self.assertEqual(rows[1], ["ai chat", "US", "123456", "-", "-", "-", "-", "-", "-", "2"])

    def test_print_week_report_writes_dash_for_not_found_rank(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            original_reports_dir = bot.REPORTS_DIR
            bot.REPORTS_DIR = Path(temp_dir)
            try:
                report_path = bot.REPORTS_DIR / "positions-20260608T080000Z.csv"
                report_path.write_text(
                    "keyword,rank,country,app_id,date\n"
                    "ai chat,not found,US,123456,2026-06-08T08:00:00+00:00\n",
                    encoding="utf-8",
                )

                output = io.StringIO()
                with patch.object(bot, "date", FixedDate):
                    with contextlib.redirect_stdout(output):
                        bot.print_week_report()
            finally:
                bot.REPORTS_DIR = original_reports_dir

            weekly_report_path = Path(temp_dir) / "week-report-2026-06-02..2026-06-08.csv"
            with weekly_report_path.open("r", encoding="utf-8", newline="") as file:
                rows = list(csv.reader(file))

        self.assertEqual(output.getvalue(), f"Weekly report ready: {weekly_report_path}\n")
        self.assertEqual(rows[1], ["ai chat", "US", "123456", "-", "-", "-", "-", "-", "-", "-"])

    def test_print_week_report_explains_no_reports_for_week(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            original_reports_dir = bot.REPORTS_DIR
            bot.REPORTS_DIR = Path(temp_dir)
            try:
                output = io.StringIO()
                with patch.object(bot, "date", FixedDate):
                    with contextlib.redirect_stdout(output):
                        bot.print_week_report()
            finally:
                bot.REPORTS_DIR = original_reports_dir

        self.assertIn("Weekly report not ready: week-report-2026-06-02..2026-06-08", output.getvalue())
        self.assertIn("Reason: no saved position reports found for the last 7 days.", output.getvalue())

    def test_print_month_report_prints_ready_message_with_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            original_reports_dir = bot.REPORTS_DIR
            bot.REPORTS_DIR = Path(temp_dir)
            try:
                for day in (1, 8):
                    report_date = f"2026-06-{day:02d}T08:00:00+00:00"
                    report_path = bot.REPORTS_DIR / f"positions-202606{day:02d}T080000Z.csv"
                    report_path.write_text(
                        "keyword,rank,country,app_id,date\n"
                        f"ai chat,{day},US,123456,{report_date}\n",
                        encoding="utf-8",
                    )

                output = io.StringIO()
                with patch.object(bot, "date", FixedDate):
                    with contextlib.redirect_stdout(output):
                        bot.print_month_report()
            finally:
                bot.REPORTS_DIR = original_reports_dir

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
            original_reports_dir = bot.REPORTS_DIR
            bot.REPORTS_DIR = Path(temp_dir)
            try:
                older_report_path = bot.REPORTS_DIR / "positions-20260608T080000Z.csv"
                older_report_path.write_text(
                    "keyword,rank,country,app_id,date\n"
                    "ai chat,4,US,123456,2026-06-08T08:00:00+00:00\n",
                    encoding="utf-8",
                )
                newer_report_path = bot.REPORTS_DIR / "positions-20260608T090000Z.csv"
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
                        bot.print_month_report()
            finally:
                bot.REPORTS_DIR = original_reports_dir

            monthly_report_path = Path(temp_dir) / "month-report-2026-06-01..2026-06-08.csv"
            with monthly_report_path.open("r", encoding="utf-8", newline="") as file:
                rows = list(csv.reader(file))

        self.assertEqual(output.getvalue(), f"Monthly report ready: {monthly_report_path}\n")
        self.assertEqual(rows[1], ["ai chat", "US", "123456", "-", "-", "-", "-", "-", "-", "-", "2"])

    def test_print_month_report_explains_no_reports_for_month(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            original_reports_dir = bot.REPORTS_DIR
            bot.REPORTS_DIR = Path(temp_dir)
            try:
                output = io.StringIO()
                with patch.object(bot, "date", FixedDate):
                    with contextlib.redirect_stdout(output):
                        bot.print_month_report()
            finally:
                bot.REPORTS_DIR = original_reports_dir

        self.assertIn("Monthly report not ready: month-report-2026-06-01..2026-06-08", output.getvalue())
        self.assertIn("Reason: no saved position reports found for the current month.", output.getvalue())


if __name__ == "__main__":
    unittest.main()
