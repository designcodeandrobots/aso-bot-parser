from __future__ import annotations

import contextlib
import csv
import io
import tempfile
import unittest
from pathlib import Path

from app_store_rank_bot import bot
from app_store_rank_bot.bot import RankResult


class ReportFormatTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
