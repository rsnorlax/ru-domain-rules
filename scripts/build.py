#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Сборщик доменных rule-set для sing-box/Podkop/NekoBox/Throne.

Вход:
  sources.txt          - URL внешних списков доменов, по одному URL на строку
  custom-domains.txt   - домены, которые нужно добавить вручную
  exclude-domains.txt  - домены, которые нужно исключить

Выход:
  dist/domains.txt      - итоговый чистый список доменов без дублей
  dist/rule-set.json    - sing-box source rule-set
  dist/duplicates.txt   - найденные дубли
  dist/metadata.json    - статистика сборки

exclude-domains.txt:
  example.com       -> исключит example.com и все его поддомены
  full:example.com  -> исключит только exact example.com
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import re
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
SOURCES_FILE = ROOT / "sources.txt"
CUSTOM_FILE = ROOT / "custom-domains.txt"
EXCLUDE_FILE = ROOT / "exclude-domains.txt"
DIST_DIR = ROOT / "dist"

DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)(?!-)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"
)

SKIP_PREFIXES = (
    "regexp:",
    "keyword:",
    "domain_keyword:",
    "domain-regex:",
    "domain_regex:",
    "include:",
    "ext:",
    "geosite:",
    "geoip:",
)


def strip_comment(line: str) -> str:
    """Убирает комментарии и мусор вокруг строки."""
    line = line.replace("\ufeff", "").strip()

    if not line:
        return ""

    if line.startswith(("#", "//", ";")):
        return ""

    # Inline-комментарии убираем только если перед маркером есть пробел/таб.
    for marker in (" #", "\t#", " //", "\t//", " ;", "\t;"):
        pos = line.find(marker)
        if pos != -1:
            line = line[:pos].strip()

    return line


def looks_like_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def idna_domain(value: str) -> str | None:
    """Приводит IDN-домен к punycode."""
    try:
        return value.encode("idna").decode("ascii").lower()
    except UnicodeError:
        return None


def normalize_domain(raw: str) -> str | None:
    """
    Нормализует домен из разных популярных форматов:
      example.com
      *.example.com
      domain:example.com
      full:example.com
      DOMAIN-SUFFIX,example.com
      ||example.com^
      0.0.0.0 example.com
    Недоменные правила вроде regexp/keyword/ip пропускаются.
    """
    line = strip_comment(raw)
    if not line:
        return None

    line = line.strip().strip('"').strip("'").strip().strip(",")

    # AdBlock whitelist — это разрешающее правило, его нельзя включать в блок/обход.
    if line.startswith("@@"):
        return None

    lower = line.lower()

    if lower.startswith(SKIP_PREFIXES):
        return None

    # hosts: 0.0.0.0 example.com / 127.0.0.1 example.com
    parts = lower.split()
    if len(parts) >= 2 and looks_like_ip(parts[0]):
        lower = parts[1]

    # Clash/Mihomo:
    # DOMAIN-SUFFIX,example.com
    # DOMAIN,example.com
    if "," in lower:
        key, value = lower.split(",", 1)
        key = key.strip()
        value = value.strip()
        if key in {"domain-suffix", "domain", "host-suffix", "host"}:
            lower = value
        elif key in {"domain-keyword", "domain-regex", "ip-cidr", "ip-cidr6"}:
            return None

    # v2fly / xray style prefixes
    for prefix in ("domain:", "full:", "dotless:"):
        if lower.startswith(prefix):
            lower = lower[len(prefix):].strip()
            break

    # Adblock: ||example.com^
    if lower.startswith("||"):
        lower = lower[2:]
        lower = lower.split("^", 1)[0]
        lower = lower.split("/", 1)[0]

    # dnsmasq/address style: address=/example.com/1.2.3.4
    if lower.startswith("address=/"):
        chunks = lower.split("/")
        if len(chunks) >= 3:
            lower = chunks[1]

    # URL accidentally inserted instead of plain domain
    if "://" in lower:
        parsed = urlsplit(lower)
        lower = parsed.hostname or ""

    # Убираем wildcard/suffix-маркеры.
    lower = lower.removeprefix("*.").removeprefix("+.").removeprefix(".").rstrip(".")

    # Остатки путей/портов/масок нам не подходят.
    if "/" in lower or ":" in lower or "*" in lower or " " in lower:
        return None

    if not lower or looks_like_ip(lower):
        return None

    lower = idna_domain(lower)
    if not lower:
        return None

    if not DOMAIN_RE.match(lower):
        return None

    return lower


def normalize_exclude(raw: str) -> tuple[str, str] | None:
    """
    Возвращает ('suffix', domain) или ('full', domain).
    По умолчанию исключение суффиксное:
      youtube.com -> youtube.com и *.youtube.com
    """
    line = strip_comment(raw)
    if not line:
        return None

    mode = "suffix"
    if line.lower().startswith("full:"):
        mode = "full"

    domain = normalize_domain(line)
    if not domain:
        return None

    return mode, domain


def read_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8-sig").splitlines()


def read_urls(path: Path) -> list[str]:
    urls: list[str] = []
    for raw in read_lines(path):
        line = strip_comment(raw)
        if not line:
            continue
        urls.append(line)
    return urls


def fetch_url(url: str, retries: int = 3, timeout: int = 60) -> str:
    last_error: Exception | None = None
    headers = {
        "User-Agent": "ru-domain-rules-builder/1.0 (+https://github.com/rsnorlax)"
    }

    for attempt in range(1, retries + 1):
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = response.read()
            try:
                return data.decode("utf-8-sig")
            except UnicodeDecodeError:
                return data.decode("utf-8", errors="ignore")
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(2 * attempt)

    raise RuntimeError(f"Не удалось скачать {url}: {last_error}")


def extract_domains_from_json_text(text: str) -> set[str]:
    data = json.loads(text)
    found: set[str] = set()

    def add_value(value) -> None:
        if isinstance(value, str):
            domain = normalize_domain(value)
            if domain:
                found.add(domain)
        elif isinstance(value, list):
            for item in value:
                add_value(item)

    if isinstance(data, dict):
        rules = data.get("rules", [])
        if isinstance(rules, list):
            for rule in rules:
                if not isinstance(rule, dict):
                    continue

                # sing-box headless rule fields
                add_value(rule.get("domain"))
                add_value(rule.get("domain_suffix"))

                # На всякий случай поддержим snake/camel варианты.
                add_value(rule.get("domainSuffix"))

    return found


def extract_domains_from_text(text: str) -> set[str]:
    found: set[str] = set()

    stripped = text.lstrip()
    if stripped.startswith("{"):
        try:
            return extract_domains_from_json_text(text)
        except json.JSONDecodeError:
            pass

    for line in text.splitlines():
        domain = normalize_domain(line)
        if domain:
            found.add(domain)

    return found


def is_excluded(domain: str, exact_excludes: set[str], suffix_excludes: set[str]) -> bool:
    if domain in exact_excludes:
        return True

    for excluded in suffix_excludes:
        if domain == excluded or domain.endswith("." + excluded):
            return True

    return False


def write_list(path: Path, values: list[str]) -> None:
    path.write_text("\n".join(values) + ("\n" if values else ""), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fail-on-source-error",
        action="store_true",
        help="Падать, если хотя бы один внешний источник не скачался",
    )
    args = parser.parse_args()

    DIST_DIR.mkdir(parents=True, exist_ok=True)

    source_urls = read_urls(SOURCES_FILE)
    all_domains_counter: Counter[str] = Counter()
    domain_sources: dict[str, set[str]] = defaultdict(set)
    source_stats: list[dict[str, object]] = []
    errors: list[str] = []

    for url in source_urls:
        try:
            text = fetch_url(url)
            domains = extract_domains_from_text(text)
            for domain in domains:
                all_domains_counter[domain] += 1
                domain_sources[domain].add(url)

            source_stats.append(
                {
                    "url": url,
                    "ok": True,
                    "domains": len(domains),
                }
            )
            print(f"[OK] {url} -> {len(domains)} доменов")
        except Exception as exc:
            message = f"[ERROR] {url}: {exc}"
            errors.append(message)
            source_stats.append({"url": url, "ok": False, "error": str(exc)})
            print(message, file=sys.stderr)

            if args.fail_on_source_error:
                return 1

    custom_domains: set[str] = set()
    for raw in read_lines(CUSTOM_FILE):
        domain = normalize_domain(raw)
        if domain:
            custom_domains.add(domain)

    for domain in custom_domains:
        all_domains_counter[domain] += 1
        domain_sources[domain].add("custom-domains.txt")

    exact_excludes: set[str] = set()
    suffix_excludes: set[str] = set()
    for raw in read_lines(EXCLUDE_FILE):
        item = normalize_exclude(raw)
        if not item:
            continue
        mode, domain = item
        if mode == "full":
            exact_excludes.add(domain)
        else:
            suffix_excludes.add(domain)

    before_exclude = set(all_domains_counter.keys())
    final_domains = sorted(
        domain
        for domain in before_exclude
        if not is_excluded(domain, exact_excludes, suffix_excludes)
    )
    excluded_domains = sorted(before_exclude - set(final_domains))

    duplicates = sorted(
        (domain, count)
        for domain, count in all_domains_counter.items()
        if count > 1
    )

    rule_set = {
        "version": 3,
        "rules": [
            {
                "domain_suffix": final_domains
            }
        ],
    }

    write_list(DIST_DIR / "domains.txt", final_domains)
    write_list(DIST_DIR / "excluded-hit.txt", excluded_domains)
    write_list(
        DIST_DIR / "duplicates.txt",
        [f"{domain} {count}" for domain, count in duplicates],
    )
    (DIST_DIR / "rule-set.json").write_text(
        json.dumps(rule_set, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    now_utc = datetime.now(timezone.utc)
    try:
        now_moscow = now_utc.astimezone(ZoneInfo("Europe/Moscow"))
    except Exception:
        now_moscow = None

    metadata = {
        "generated_at_utc": now_utc.isoformat(),
        "generated_at_moscow": now_moscow.isoformat() if now_moscow else None,
        "sources_count": len(source_urls),
        "sources_ok": sum(1 for item in source_stats if item.get("ok")),
        "sources_failed": sum(1 for item in source_stats if not item.get("ok")),
        "source_stats": source_stats,
        "custom_domains_count": len(custom_domains),
        "exclude_suffix_count": len(suffix_excludes),
        "exclude_exact_count": len(exact_excludes),
        "unique_before_exclude_count": len(before_exclude),
        "duplicates_count": len(duplicates),
        "excluded_removed_count": len(excluded_domains),
        "output_domains_count": len(final_domains),
        "errors": errors,
    }

    (DIST_DIR / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    if not final_domains:
        print("[ERROR] Итоговый список пустой. Проверь sources/custom/exclude.", file=sys.stderr)
        return 1

    print("")
    print("Готово:")
    print(f"  domains.txt:      {len(final_domains)} доменов")
    print(f"  rule-set.json:    sing-box source rule-set")
    print(f"  duplicates.txt:   {len(duplicates)} дублей")
    print(f"  excluded-hit.txt: {len(excluded_domains)} удалено по exclude")
    print(f"  metadata.json:    статистика сборки")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
