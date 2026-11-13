"""The Telegram messages, in plain Armenian."""
from __future__ import annotations

import html
from collections import Counter
from datetime import datetime, timedelta

from . import textproc as tp
from .store import is_open, parse

MAX_ITEMS = 7
SOON_HOURS = 72
#: Some notices never say what is being bought; the invitation does.
NO_SUBJECT = "Գնման առարկան վերնագրում նշված չէ"


def esc(text: str) -> str:
    return html.escape(text or "", quote=False)


def headline(t: dict, limit: int = 90) -> str:
    text = t.get("subject") or NO_SUBJECT
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def short(text: str | None, limit: int = 64) -> str:
    text = text or ""
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _published(t: dict) -> datetime | None:
    return parse(t.get("pub")) or parse(t.get("seen"))


def split(tenders: list[dict], at: datetime, since: datetime):
    open_ = [t for t in tenders if is_open(t, at)]
    fresh = [t for t in open_ if (_published(t) or datetime.min) > since]
    fresh.sort(key=lambda t: _published(t) or datetime.min, reverse=True)
    soon = [t for t in open_ if parse(t["end"]) - at <= timedelta(hours=SOON_HOURS)]
    today = sorted((t for t in open_ if parse(t["end"]).date() == at.date()),
                   key=lambda t: t["end"])
    return open_, fresh, soon, today


def _sector_line(items: list[dict]) -> str:
    counts = Counter(t.get("sector") or "other" for t in items)
    parts = [f"{tp.SECTOR_LABELS.get(k, k)} {n}" for k, n in counts.most_common(6)]
    rest = sum(counts.values()) - sum(n for _, n in counts.most_common(6))
    if rest:
        parts.append(f"մնացածը {rest}")
    return " · ".join(parts)


def _items(items: list[dict], focus: list[str]) -> list[str]:
    def weight(t: dict) -> int:
        text = (t.get("title") or "").lower()
        return 0 if any(w.lower() in text for w in focus) else 1

    ordered = sorted(items, key=weight)  # stable: keeps newest-first inside each group
    lines = []
    for t in ordered[:MAX_ITEMS]:
        end = parse(t["end"])
        who = short(t.get("buyer") or "")
        tail = f"մինչև {tp.hy_short(end)}"
        lines.append(f"• <b>{esc(headline(t))}</b>\n{esc(who + ' · ' if who else '')}{tail}")
    more = len(ordered) - MAX_ITEMS
    if more > 0:
        lines.append(f"…և ևս {more} մրցույթ՝ հավելվածում")
    return lines


def build(tenders: list[dict], at: datetime, since: datetime, period: str,
          focus: list[str] | None = None) -> str | None:
    """Morning: always something to say. Evening: only when new tenders appeared."""
    focus = focus or []
    open_, fresh, soon, today = split(tenders, at, since)
    day = tp.hy_date(at, weekday=True)

    if period == "evening":
        if not fresh:
            return None
        out = [f"<b>Մրցույթներ</b> · {day}", "",
               f"🆕 Այսօր հրապարակվել է <b>{len(fresh)}</b> նոր մրցույթ",
               esc(_sector_line(fresh)), ""]
        out += ["\n\n".join(_items(fresh, focus))]
        return "\n".join(out)

    out = [f"<b>Մրցույթներ</b> · {day}", "",
           f"🆕 Նոր՝ <b>{len(fresh)}</b>",
           f"⏳ Առաջիկա 3 օրում փակվում է՝ <b>{len(soon)}</b>",
           f"📂 Ընդամենը բաց՝ <b>{len(open_)}</b>"]
    if today:
        out += ["", "<b>Այսօր փակվում է</b>"]
        for t in today[:6]:
            out.append(f"• {parse(t['end']).strftime('%H:%M')} — {esc(headline(t, 80))}")
        if len(today) > 6:
            out.append(f"…և ևս {len(today) - 6}")
    if fresh:
        out += ["", "<b>Նոր մրցույթները</b>", esc(_sector_line(fresh)), "",
                "\n\n".join(_items(fresh, focus))]
    else:
        out += ["", "Երեկվանից նոր մրցույթ չի հրապարակվել։"]
    return "\n".join(out)


def welcome(tenders: list[dict], at: datetime) -> str:
    open_ = [t for t in tenders if is_open(t, at)]
    today = [t for t in open_ if (_published(t) or datetime.min).date() == at.date()]
    lines = [
        "Բարև Ձեզ։",
        "",
        "Այս բոտը հետևում է Հայաստանի պետական գնումների էլեկտրոնային աճուրդներին (ARMEPS) "
        "և պարզ հայերենով տեղեկացնում նոր մրցույթների մասին։",
        "",
        "• Առավոտյան՝ նոր մրցույթները և մոտակա վերջնաժամկետները",
        "• Երեկոյան՝ օրվա ընթացքում հրապարակվածները",
        "",
        "Բոլոր մրցույթները տեսնելու համար սեղմեք «Մրցույթներ» կոճակը։",
        "Հաղորդագրությունները դադարեցնելու համար գրեք /stop։",
    ]
    if open_:
        lines += ["", f"Այս պահին բաց է <b>{len(open_)}</b> մրցույթ, "
                      f"այսօր հրապարակվել է <b>{len(today)}</b>-ը։"]
    return "\n".join(lines)


GOODBYE = "Հաղորդագրությունները դադարեցված են։ Վերսկսելու համար գրեք /start։"
HINT = ("Նոր մրցույթների մասին կգրեմ ամեն աշխատանքային օր։ "
        "Բոլոր մրցույթները տեսնելու համար սեղմեք «Մրցույթներ» կոճակը։")
BUTTON = "Բացել մրցույթները"
MENU = "Մրցույթներ"
DESCRIPTION = ("Հայաստանի պետական մրցույթները՝ ամեն աշխատանքային օր, պարզ հայերենով։ "
               "Սկսելու համար սեղմեք START։")
SHORT_DESCRIPTION = "Հայաստանի պետական մրցույթները՝ ամեն օր, պարզ հայերենով"
COMMANDS = [("start", "Ստանալ ամենօրյա հաղորդագրությունները"),
            ("stop", "Դադարեցնել հաղորդագրությունները")]
