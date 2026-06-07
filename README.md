# ASO Bot Parser

Программа для проверки позиции приложения в поиске App Store по указанным странам и ключевым словам.

## Допущение

Позиция в App Store считается относительно поискового запроса. Поэтому для каждой проверки нужны три значения: `app_id`, `country`, `keyword`.

## Запуск

Запустите программу без аргументов:

```bash
python3 -m app_store_rank_bot
```

CLI проведет по шагам:

1. Спросит `app_id` приложения.
2. Спросит страну, например `US`.
3. Спросит ключевые запросы по одному на строку.

Пустая строка завершает ввод ключей. После этого программа сохранит список проверок в папку `checks/`, последовательно проверит каждый ключ и сохранит отчет в папку `reports/`.

## Формат отчета

Отчет сохраняется в CSV:

```text
checked_at,app_id,country,keyword,rank
2026-06-07T11:30:00+00:00,284882215,US,fitness tracker,12
2026-06-07T11:30:00+00:00,284882215,US,workout,not found
```

`checked_at` - дата и время проверки в UTC. Если приложение не найдено среди результатов, в `rank` будет `not found`.

## Запуск из готового файла

Можно подготовить JSON-файл со списком проверок:

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

Запустите программу:

```bash
python3 -m app_store_rank_bot checks.example.json
```

Вывод по умолчанию идет в CSV-таблицу в консоль и дополнительно сохраняется в `reports/`:

```text
checked_at,app_id,country,keyword,rank
2026-06-07T11:30:00+00:00,284882215,US,fitness tracker,12
```

Для JSON-вывода:

```bash
python3 -m app_store_rank_bot checks.example.json --format json
```

## Как считается позиция

Программа вызывает публичный App Store Search API:

```text
https://itunes.apple.com/search?term=<keyword>&country=<country>&entity=software&limit=200
```

Затем ищет приложение по `trackId`. Если приложения нет среди первых 200 результатов, в поле `rank` будет `not found` для таблицы или `null` для JSON.
