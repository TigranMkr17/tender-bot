"""The data file the app reads (docs/data/tenders.json) and how records are built."""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

from . import textproc as tp
from .armeps import detail_url

YEREVAN = timezone(timedelta(hours=4))  # Armenia has no daylight saving time
DATA_PATH = os.path.join("docs", "data", "tenders.json")
KEEP_CLOSED_DAYS = 4

STATUS = {"Հրապարակված": "open", "Published": "open",
          "Չեղարկված": "cancelled", "Cancelled": "cancelled", "Canceled": "cancelled"}


def now() -> datetime:
    return datetime.now(YEREVAN).replace(tzinfo=None, second=0, microsecond=0)


def parse(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.strptime(ts[:16], "%Y-%m-%dT%H:%M")
    except ValueError:
        return None


def stamp(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M")


def load(path: str = DATA_PATH) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}
    data.setdefault("meta", {})
    data.setdefault("tenders", [])
    return data


def save(data: dict, path: str = DATA_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data["tenders"].sort(key=lambda t: (t.get("end") or "", t["id"]))
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
        fh.write("\n")


def status_key(text: str | None) -> str:
    return STATUS.get((text or "").strip(), "other")


def is_open(t: dict, at: datetime) -> bool:
    end = parse(t.get("end"))
    return t.get("status") == "open" and end is not None and end > at


def enrich(tenders: list[dict]) -> None:
    """Fill the reader-facing fields (subject, buyer, sector...) from the raw ones."""
    casing = tp.Casing().learn(
        [t.get("title") for t in tenders] + [t.get("buyer_official") for t in tenders])
    for t in tenders:
        title = t.get("title") or ""
        code = t.get("code") or ""
        readable = casing.fix(title, "title")
        subject, for_whom = tp.split_title(readable, code)
        buyer = casing.fix((t.get("buyer_official") or "").strip("«»\"“” "), "name") or None
        kind = t.get("kind") or tp.kind_from_code(code)
        t["subject"] = subject
        t["buyer"] = buyer
        t["for"] = None if tp.same_party(for_whom, buyer) else for_whom
        t["kind"] = kind
        t["sector"] = tp.classify(subject or readable, kind)
        t["url"] = detail_url(t["id"])


def prune(tenders: list[dict], at: datetime) -> list[dict]:
    """Drop tenders whose deadline passed more than a few days ago."""
    limit = at - timedelta(days=KEEP_CLOSED_DAYS)
    return [t for t in tenders if (parse(t.get("end")) or at) >= limit]


def compact(t: dict) -> dict:
    """Drop empty fields before writing, to keep the published file small."""
    return {k: v for k, v in t.items() if v not in (None, "", False)}
