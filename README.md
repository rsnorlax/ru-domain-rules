# RU domain rules builder

Сборщик доменных списков для sing-box / Podkop / NekoBox / Throne.

## Что делает

1. Берет внешние источники из `sources.txt`.
2. Добавляет домены из `custom-domains.txt`.
3. Нормализует домены и убирает дубли.
4. Раскладывает общий набор доменов по каналам:
   - `domains`
   - `domains2`
   - `domains3`
   - `dpi`
5. Собирает:
   - `dist/domains.json`
   - `dist/domains.srs`
   - `dist/domains2.json`
   - `dist/domains2.srs`
   - `dist/domains3.json`
   - `dist/domains3.srs`
   - `dist/dpi.json`
   - `dist/dpi.srs`
   - `dist/metadata.json`
   - `dist/duplicates.txt`

## Файлы управления

### `sources.txt`

Сюда добавляются URL внешних списков.

Поддерживаются:

- обычные `.txt` / `.lst` списки доменов;
- sing-box source JSON.

Не поддерживаются как вход:

- `.srs`, потому что это бинарный формат;
- `geoip.dat` / `geosite.dat`;
- чистые IP-списки.

### `custom-domains.txt`

Сюда добавляются свои домены в общий набор `all_domains`.

Пример:

```txt
example.com
*.example.net
domain:example.org
full:example.com
```

В итоговых rule-set домены записываются как `domain_suffix`.

### `move-to-domains2.txt`

Правила доменов, которые нужно убрать из основного `domains` и положить в `domains2`.

### `move-to-domains3.txt`

Правила доменов, которые нужно убрать из основного `domains` и положить в `domains3`.

### `move-to-dpi.txt`

Правила доменов, которые нужно убрать из обычных списков `domains` / `domains2` / `domains3` и положить только в `dpi`.

## Формат move-to правил

Формат одинаковый для всех `move-to-*.txt`:

```txt
example.com
full:example.net
```

`example.com` работает как суффиксное правило: совпадет `example.com` и любой его поддомен.

`full:example.net` работает как точное правило: совпадет только `example.net`.

Приоритеты:

1. `move-to-dpi.txt`
2. `move-to-domains3.txt`
3. `move-to-domains2.txt`
4. `domains`, если домен не совпал ни с одним правилом

Один домен попадает только в один итоговый список.

## Ручной запуск локально

```bash
python scripts/build.py
```

Если установлен `sing-box`, можно собрать `.srs`:

```bash
sing-box rule-set compile --output dist/domains.srs dist/domains.json
sing-box rule-set compile --output dist/domains2.srs dist/domains2.json
sing-box rule-set compile --output dist/domains3.srs dist/domains3.json
sing-box rule-set compile --output dist/dpi.srs dist/dpi.json
```

## Автоматический запуск

GitHub Actions запускает сборку каждый день в 03:17 по Москве:

```yaml
schedule:
  - cron: "17 0 * * *"
```

GitHub Actions использует UTC, поэтому `00:17 UTC` соответствует `03:17` по Москве.

После сборки Action сам коммитит изменившиеся файлы из `dist/`.

## URL для использования

```txt
https://raw.githubusercontent.com/rsnorlax/ru-domain-rules/main/dist/domains.srs
https://raw.githubusercontent.com/rsnorlax/ru-domain-rules/main/dist/domains2.srs
https://raw.githubusercontent.com/rsnorlax/ru-domain-rules/main/dist/domains3.srs
https://raw.githubusercontent.com/rsnorlax/ru-domain-rules/main/dist/dpi.srs
```

## Пример для sing-box / Podkop

```json
{
  "type": "remote",
  "tag": "custom-ru-domains",
  "format": "binary",
  "url": "https://raw.githubusercontent.com/rsnorlax/ru-domain-rules/main/dist/domains.srs",
  "download_detour": "direct"
}
```
