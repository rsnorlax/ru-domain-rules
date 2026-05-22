# RU domain rules builder

Сборщик доменных списков для sing-box / Podkop / NekoBox / Throne.

## Что делает

1. Берёт внешние источники из `sources.txt`.
2. Добавляет твои домены из `custom-domains.txt`.
3. Удаляет всё, что указано в `exclude-domains.txt`.
4. Нормализует домены.
5. Убирает дубли.
6. Собирает:
   - `dist/domains.txt`
   - `dist/rule-set.json`
   - `dist/rule-set.srs`
   - `dist/metadata.json`
   - `dist/duplicates.txt`
   - `dist/excluded-hit.txt`

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

Сюда добавляются свои домены.

Пример:

```txt
example.com
*.example.net
domain:example.org
```

### `exclude-domains.txt`

Сюда добавляются домены, которые надо вырезать.

```txt
youtube.com
googlevideo.com
```

По умолчанию исключение суффиксное. То есть `youtube.com` удалит и `youtube.com`, и `music.youtube.com`.

Для удаления только точного домена:

```txt
full:example.com
```

## Ручной запуск локально

```bash
python scripts/build.py
```

Если установлен `sing-box`, можно собрать `.srs`:

```bash
sing-box rule-set compile \
  --output dist/rule-set.srs \
  dist/rule-set.json
```

## Автоматический запуск

GitHub Actions запускает сборку каждый день в 03:17 по Москве:

```yaml
schedule:
  - cron: "17 3 * * *"
    timezone: "Europe/Moscow"
```

После сборки Action сам коммитит изменившиеся файлы из `dist/`.

## URL для использования

После первого успешного запуска будут доступны raw-ссылки:

```txt
https://raw.githubusercontent.com/rsnorlax/ru-domain-rules/main/dist/domains.txt
https://raw.githubusercontent.com/rsnorlax/ru-domain-rules/main/dist/rule-set.json
https://raw.githubusercontent.com/rsnorlax/ru-domain-rules/main/dist/rule-set.srs
```

Замени `USER/REPO` на свой репозиторий.

## Пример для sing-box / Podkop

```json
{
  "type": "remote",
  "tag": "custom-ru-domains",
  "format": "binary",
  "url": "https://raw.githubusercontent.com/USER/REPO/main/dist/rule-set.srs",
  "download_detour": "direct"
}
```
