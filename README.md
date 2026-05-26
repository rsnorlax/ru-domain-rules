# RU domain rules builder

Сборщик доменных списков для sing-box / Podkop / NekoBox / Throne.

## Что делает

1. Берёт внешние источники из `sources.txt`.
2. Добавляет твои домены из `custom-domains.txt`.
3. Удаляет всё, что указано в `exclude-domains.txt`.
4. Из удаленных доменов собирает отдельный excluded rule-set.
5. Из excluded rule-set дополнительно удаляет всё, что указано в `excluded-rule-exclude-domains.txt`.
6. Нормализует домены.
7. Убирает дубли.
8. Собирает:
   - `dist/domains.txt`
   - `dist/rule-set.json`
   - `dist/rule-set.srs`
   - `dist/excluded-domains.txt`
   - `dist/excluded-rule-set.json`
   - `dist/excluded-rule-set.srs`
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

### `excluded-rule-exclude-domains.txt`

Сюда добавляются домены, которые не должны попадать во второй rule-set из исключенных доменов.

Например, если `youtube.com` есть в `exclude-domains.txt`, он будет удален из основного `dist/rule-set.json` и попадет в `dist/excluded-rule-set.json`. Если при этом добавить `youtube.com` в `excluded-rule-exclude-domains.txt`, он не попадет и во второй rule-set.

Формат такой же:

```txt
youtube.com
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

sing-box rule-set compile \
  --output dist/excluded-rule-set.srs \
  dist/excluded-rule-set.json
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

После первого успешного запуска будут доступны raw-ссылки:

```txt
https://raw.githubusercontent.com/rsnorlax/ru-domain-rules/main/dist/domains.txt
https://raw.githubusercontent.com/rsnorlax/ru-domain-rules/main/dist/rule-set.json
https://raw.githubusercontent.com/rsnorlax/ru-domain-rules/main/dist/rule-set.srs
https://raw.githubusercontent.com/rsnorlax/ru-domain-rules/main/dist/excluded-domains.txt
https://raw.githubusercontent.com/rsnorlax/ru-domain-rules/main/dist/excluded-rule-set.json
https://raw.githubusercontent.com/rsnorlax/ru-domain-rules/main/dist/excluded-rule-set.srs
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
