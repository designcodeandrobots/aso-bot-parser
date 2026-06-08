# ASO Bot Parser

ASO Bot Parser is a small CLI tool that checks an iOS app's current App Store search position for selected countries and keywords.

## How It Works

App Store search rank is measured for a specific keyword in a specific country. Each check needs:

- `app_id`: the numeric App Store app ID
- `country`: a 2-letter country code such as `US`, `GB`, `DE`, or `FR`
- `keyword`: the search query to check

The tool calls the public App Store Search API:

```text
https://itunes.apple.com/search?term=<keyword>&country=<country>&entity=software&limit=200
```

It then scans the returned apps in order and compares each result's `trackId` with your `app_id`.

- If the app is the first result, rank is `1`.
- If the app is the tenth result, rank is `10`.
- If the app is not found in the first 200 results, rank is `-` in table/CSV output and `null` in JSON output.

## Installation

Requirements:

- Python 3.10 or newer
- Internet access for calls to the App Store Search API

Clone the repository:

```bash
git clone https://github.com/designcodeandrobots/aso-bot-parser.git
cd aso-bot-parser
```

Run the menu interface:

```bash
python3 -m app_store_rank_bot
```

No third-party Python packages are required.

## Menu CLI Usage

Start the menu:

```bash
python3 -m app_store_rank_bot
```

You will see:

```text
ASO Bot Parser
Active app_id: 6443812062
1. Show keywords
2. Add keywords
3. Update keywords
4. Show geo list
5. Add geo
6. Delete geo
7. Check new positions
8. Show last report
9. Show today report
10. Show week report
11. Show monthly report
12. Delete app
13. Show logs
0. Exit
```

On first launch, the CLI checks `checks/app.json`. If no saved app ID exists, it asks for:

1. The App Store `app_id`

After the app ID is saved, choose `2` to add keywords. The CLI asks for:

1. The target country
2. All keywords in one line, separated by commas or semicolons

Example keyword input:

```text
ai chat, note taking app, language learning
```

After input, the tool:

1. Saves the checks to `checks/checks-<timestamp>.json`
2. Checks each keyword sequentially
3. Saves the report to `reports/positions-<timestamp>.csv`
4. Prints the same results to the terminal

## Request Delay

The tool waits between App Store requests to reduce the chance of rate limits or IP blocking. The default delay is `1.0` second between requests.

For large keyword lists, increase the delay:

```bash
python3 -m app_store_rank_bot /check-new-positions --delay-seconds 2
```

You can also set the default through an environment variable:

```bash
export ASO_REQUEST_DELAY_SECONDS=2
python3 -m app_store_rank_bot /check-new-positions
```

Use `0` only when you intentionally want no delay:

```bash
python3 -m app_store_rank_bot /check-new-positions --delay-seconds 0
```

## Saved History

The tool keeps local history in two folders:

- `checks/`: saved app, country, and keyword sets
- `reports/`: saved rank reports

To list saved check sets:

```bash
python3 -m app_store_rank_bot /show-logs
```

To check positions for the latest saved check set:

```bash
python3 -m app_store_rank_bot /check-new-positions
```

You can also use standard flags:

```bash
python3 -m app_store_rank_bot --show-logs
python3 -m app_store_rank_bot --check-new-positions
```

Each check creates a new report in `reports/`, so you can compare rank changes over time.

## Commands

Slash commands are convenient when the tool is driven from chat:

| Command | What it does |
| --- | --- |
| `/help` | Show CLI help. |
| `/add-geo` | Add one country to the active check set, then enter keywords for that country. |
| `/add-keywords` | Append keywords to the latest saved check set. |
| `/check-new-positions` | Check positions for the latest saved keyword list. |
| `/delete-app` | Delete the saved app ID after confirmation. |
| `/delete-geo` | Remove one country from the active check set after confirmation. Previous files are not deleted. |
| `/show-geo-list` | Print active countries in the latest saved check set. |
| `/show-keywords` | Print the latest saved keyword list. |
| `/show-report-last` | Print the latest saved positions report as a table. |
| `/show-report-today` | Print today's rank changes from saved reports. |
| `/show-report-week` | Print rank changes for the last 7 days from saved reports. |
| `/show-report-month` | Create this month's rank report from saved reports. |
| `/update-keywords` | Replace keywords for the latest saved app/country pair. |
| `/show-logs` | Show saved check sets. |

Examples:

```bash
python3 -m app_store_rank_bot /add-geo
python3 -m app_store_rank_bot /add-keywords
python3 -m app_store_rank_bot /show-keywords
python3 -m app_store_rank_bot /show-geo-list
python3 -m app_store_rank_bot /show-report-last
python3 -m app_store_rank_bot /show-report-today
python3 -m app_store_rank_bot /show-report-week
python3 -m app_store_rank_bot /show-report-month
python3 -m app_store_rank_bot /delete-app
python3 -m app_store_rank_bot /update-keywords
python3 -m app_store_rank_bot /delete-geo
python3 -m app_store_rank_bot /check-new-positions
python3 -m app_store_rank_bot /show-logs
```

The same actions are available as regular flags:

```bash
python3 -m app_store_rank_bot --add-geo
python3 -m app_store_rank_bot --add-keywords
python3 -m app_store_rank_bot --show-keywords
python3 -m app_store_rank_bot --show-geo-list
python3 -m app_store_rank_bot --show-report-last
python3 -m app_store_rank_bot --show-report-today
python3 -m app_store_rank_bot --show-report-week
python3 -m app_store_rank_bot --show-report-month
python3 -m app_store_rank_bot --delete-app
python3 -m app_store_rank_bot --update-keywords
python3 -m app_store_rank_bot --delete-geo
python3 -m app_store_rank_bot --check-new-positions
python3 -m app_store_rank_bot --show-logs
```

## Run From a Config File

You can also prepare a JSON file:

```json
{
  "checks": [
    {
      "app_id": "284882215",
      "country": "US",
      "keyword": "fitness tracker"
    }
  ]
}
```

Run:

```bash
python3 -m app_store_rank_bot checks.example.json
```

JSON output is also available:

```bash
python3 -m app_store_rank_bot checks.example.json --format json
```

## Output Format

Reports are saved as CSV:

```text
keyword,rank,country,app_id,date
fitness tracker,12,US,284882215,2026-06-07T11:30:00+00:00
workout,-,US,284882215,2026-06-07T11:30:00+00:00
```

`date` is the UTC timestamp for the check run.

## Help

Use either command:

```bash
python3 -m app_store_rank_bot --help
python3 -m app_store_rank_bot /help
python3 -m app_store_rank_bot /add-geo
python3 -m app_store_rank_bot /add-keywords
python3 -m app_store_rank_bot /show-logs
python3 -m app_store_rank_bot /show-geo-list
python3 -m app_store_rank_bot /show-keywords
python3 -m app_store_rank_bot /show-report-last
python3 -m app_store_rank_bot /show-report-today
python3 -m app_store_rank_bot /show-report-week
python3 -m app_store_rank_bot /show-report-month
python3 -m app_store_rank_bot /delete-app
python3 -m app_store_rank_bot /update-keywords
python3 -m app_store_rank_bot /delete-geo
python3 -m app_store_rank_bot /check-new-positions
```

## Chatbot / Agent Usage

This project is designed to be easy to drive from a chat-based coding agent or chatbot that can run shell commands.

Recommended flow:

1. Start the CLI with `python3 -m app_store_rank_bot`.
2. If no saved app ID exists, send the numeric App Store app ID once.
3. Choose the action you need from the menu.
4. When the app asks for country, send the 2-letter country code.
5. When the app asks for keywords, send all keywords in one message separated by commas or semicolons.
6. Wait for the sequential checks to finish.
7. Read the generated CSV from `reports/`.
8. If needed, render the CSV as a Markdown table in chat.

To repeat the previous keyword set from chat, run:

```bash
python3 -m app_store_rank_bot /check-new-positions
```

For fully non-interactive chatbot runs, write a temporary JSON config and run:

```bash
python3 -m app_store_rank_bot path/to/checks.json
```

This is usually better for long keyword lists because it avoids fragile terminal input handling.
