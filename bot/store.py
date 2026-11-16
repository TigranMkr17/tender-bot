"""What the bot remembers (bot/state/tenders.json) and what the app reads (docs/data/tenders.json)."""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

from . import textproc as tp

YEREVAN = timezone(timedelta(hours=4))  # Armenia has no daylight saving time
STATE_PATH = os.path.join("bot", "state", "tenders.json")   # everything the bot knows
DATA_PATH = os.path.join("docs", "data", "tenders.json")    # the slim copy the app downloads
KEEP_CLOSED_DAYS = 4
INVITATION = "https://eauction.armeps.am/application/documents/public_invitation/tender_{id}.zip"
#: Fields the app shows. The notice URL is left out: the app builds it from the id.
PUBLIC = ("id", "code", "title", "subject", "buyer", "bk", "for", "kind", "sector", "lots",
          "status", "pub", "end", "ask", "auc")

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


def load(path: str = STATE_PATH) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}
    data.setdefault("meta", {})
    data.setdefault("tenders", [])
    return data


def _write(obj: dict, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, separators=(",", ":"))
        fh.write("\n")


def save(data: dict, path: str = STATE_PATH) -> None:
    data["tenders"].sort(key=lambda t: (t.get("end") or "", t["id"]))
    _write(data, path)


def public_view(t: dict) -> dict:
    """One tender as the app needs it: no bookkeeping, no empty fields, short links."""
    out = {k: t[k] for k in PUBLIC if t.get(k) not in (None, "", False)}
    if "pub" not in out and t.get("seen"):
        out["seen"] = t["seen"]
    inv = t.get("inv")
    if inv:  # 1 means "the usual address for this id"; anything else is kept as written
        out["inv"] = 1 if inv == INVITATION.format(id=t["id"]) else inv
    return out


def publish(data: dict, path: str = DATA_PATH) -> None:
    """Write the copy the app downloads."""
    tenders = sorted(data["tenders"], key=lambda t: (t.get("end") or "", t["id"]))
    _write({"meta": data["meta"], "tenders": [public_view(t) for t in tenders]}, path)


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
        title = t["title"] = tp.clean_chars(t.get("title"))
        code = t.get("code") or ""
        readable = casing.fix(title, "title")
        subject, for_whom = tp.split_title(readable, code)
        buyer = casing.fix(tp.clean_name(t.get("buyer_official")), "name") or None
        kind = t.get("kind") or tp.kind_from_code(code)
        t["subject"] = subject
        t["buyer"] = buyer
        t["bk"] = tp.buyer_key(t.get("buyer_official")) or None
        t["for"] = None if tp.same_party(for_whom, buyer) else for_whom
        t["kind"] = kind
        t["sector"] = tp.classify(subject or readable, kind)
        t.pop("url", None)


def prune(tenders: list[dict], at: datetime) -> list[dict]:
    """Drop tenders whose deadline passed more than a few days ago."""
    limit = at - timedelta(days=KEEP_CLOSED_DAYS)
    return [t for t in tenders if (parse(t.get("end")) or at) >= limit]


def compact(t: dict) -> dict:
    """Drop empty fields before writing, to keep the published file small."""
    return {k: v for k, v in t.items() if v not in (None, "", False)}
