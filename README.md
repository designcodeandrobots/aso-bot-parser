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
- If the app is not found in the first 200 results, rank is `not found` in CSV output and `null` in JSON output.

## Installation

Requirements:

- Python 3.10 or newer
- Internet access for calls to the App Store Search API

Clone the repository:

```bash
git clone https://github.com/designcodeandrobots/aso-bot-parser.git
cd aso-bot-parser
```

Run the tool:

```bash
python3 -m app_store_rank_bot
```

No third-party Python packages are required.

## Interactive CLI Usage

Start the interactive flow:

```bash
python3 -m app_store_rank_bot
```

The CLI asks for:

1. The App Store `app_id`
2. The target country
3. All keywords in one line, separated by commas or semicolons

Example keyword input:

```text
ai chat, note taking app, language learning
```

After input, the tool:

1. Saves the checks to `checks/checks-<timestamp>.json`
2. Checks each keyword sequentially
3. Saves the report to `reports/positions-<timestamp>.csv`
4. Prints the same results to the terminal

## Saved History

The tool keeps local history in two folders:

- `checks/`: saved app, country, and keyword sets
- `reports/`: saved rank reports

To list saved check sets:

```bash
python3 -m app_store_rank_bot /check-history
```

To check positions for the latest saved check set:

```bash
python3 -m app_store_rank_bot /check-new-positions
```

You can also use standard flags:

```bash
python3 -m app_store_rank_bot --check-history
python3 -m app_store_rank_bot --check-new-positions
```

Each check creates a new report in `reports/`, so you can compare rank changes over time.

## Commands

Slash commands are convenient when the tool is driven from chat:

| Command | What it does |
| --- | --- |
| `/help` | Show CLI help. |
| `/check-new-positions` | Check positions for the latest saved keyword list. |
| `/show-keywords` | Print the latest saved keyword list. |
| `/update-keywords` | Replace keywords for the latest saved app/country pair. |
| `/check-history` | Show saved check sets. |

Examples:

```bash
python3 -m app_store_rank_bot /show-keywords
python3 -m app_store_rank_bot /update-keywords
python3 -m app_store_rank_bot /check-new-positions
python3 -m app_store_rank_bot /check-history
```

The same actions are available as regular flags:

```bash
python3 -m app_store_rank_bot --show-keywords
python3 -m app_store_rank_bot --update-keywords
python3 -m app_store_rank_bot --check-new-positions
python3 -m app_store_rank_bot --check-history
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
checked_at,app_id,country,keyword,rank
2026-06-07T11:30:00+00:00,284882215,US,fitness tracker,12
2026-06-07T11:30:00+00:00,284882215,US,workout,not found
```

`checked_at` is the UTC timestamp for the check run.

## Help

Use either command:

```bash
python3 -m app_store_rank_bot --help
python3 -m app_store_rank_bot /help
python3 -m app_store_rank_bot /check-history
python3 -m app_store_rank_bot /show-keywords
python3 -m app_store_rank_bot /update-keywords
python3 -m app_store_rank_bot /check-new-positions
```

## Chatbot / Agent Usage

This project is designed to be easy to drive from a chat-based coding agent or chatbot that can run shell commands.

Recommended flow:

1. Start the CLI with `python3 -m app_store_rank_bot`.
2. When the app asks for `app_id`, send the numeric app ID.
3. When the app asks for country, send the 2-letter country code.
4. When the app asks for keywords, send all keywords in one message separated by commas or semicolons.
5. Wait for the sequential checks to finish.
6. Read the generated CSV from `reports/`.
7. If needed, render the CSV as a Markdown table in chat.

To repeat the previous keyword set from chat, run:

```bash
python3 -m app_store_rank_bot /check-new-positions
```

For fully non-interactive chatbot runs, write a temporary JSON config and run:

```bash
python3 -m app_store_rank_bot path/to/checks.json
```

This is usually better for long keyword lists because it avoids fragile terminal input handling.
