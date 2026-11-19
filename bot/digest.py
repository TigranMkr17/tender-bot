"""The Telegram messages, in plain Armenian."""
from __future__ import annotations

import html
import json
from collections import Counter
from datetime import datetime, timedelta

from . import contracts
from . import textproc as tp
from .store import is_open, parse

MAX_ITEMS = 10
#: How each procedure is called on the site (the same names as PROC in the page).
PROC = {"ԳՀ": "Գնանշման հարցում", "ԲՄ": "Բաց մրցույթ", "ՀԲՄ": "Հրատապ բաց մրցույթ", "ԵՄ": "Երկփուլ մրցույթ",
        "ՇՀ": "Շրջանակային համաձայնություն", "ԴՄ": "Դրամաշնորհային մրցույթ", "ՄԱ": "Մեկ անձից գնում",
        "ԲԸ": "Բանակցային ընթացակարգ", "ՊԸ": "Պարզեցված ընթացակարգ", "ՍԸ": "Սահմանափակ ընթացակարգ",
        "ՄԵ": "Մրցակցային երկխոսություն"}
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


def group_stems(path: str = contracts.HOME) -> list[str]:
    """The stems of the group's lines (docs/my/home.json), as «Մեր դաշտը» matches them."""
    try:
        with open(path, encoding="utf-8") as fh:
            home = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return []
    return [k for line in contracts.unpack_lines(home.get("w", "")) for k in line]


def ours(t: dict, stems: list[str]) -> bool:
    """In one of the group's lines: every word of a stem starts a word of the tender's subject or title."""
    text = contracts.norm(f"{t.get('subject') or ''} {t.get('title') or ''}")
    return any(all((" " + w) in text for w in stem.split(" ")) for stem in stems)


def procedure(t: dict) -> str:
    return PROC.get(t.get("pr") or "", "ARMEPS ընթացակարգ") if t.get("src") else "Աճուրդ"


def _items(items: list[dict], focus: list[str], app_url: str | None = None, stems: list[str] | None = None) -> list[str]:
    stems = stems or []

    def weight(t: dict) -> int:
        text = (t.get("title") or "").lower()
        return 0 if ours(t, stems) or any(w.lower() in text for w in focus) else 1

    ordered = sorted(items, key=weight)  # stable: keeps newest-first inside each group
    lines = []
    for t in ordered[:MAX_ITEMS]:
        end = parse(t["end"])
        who = short(t.get("buyer") or "")
        title = f"<b>{esc(headline(t))}</b>"
        if app_url:
            title = f'<a href="{esc(app_url)}#t{t["id"]}">{title}</a>'
        star = " ⭐" if ours(t, stems) else ""
        tail = f"{procedure(t)} · մինչև {tp.hy_short(end)}"
        lines.append(f"• {title}{star}\n{esc(who + ' · ' if who else '')}{tail}")
    more = len(ordered) - MAX_ITEMS
    if more > 0:
        lines.append(f"…և ևս {more} մրցույթ՝ կայքում")
    return lines


def build(tenders: list[dict], at: datetime, since: datetime, period: str,
          focus: list[str] | None = None, app_url: str | None = None, stems: list[str] | None = None) -> str | None:
    """Morning: always something to say. Later in the day (12:00, 15:00, 18:00): only when new tenders appeared.
    Tenders in the group's lines come first, with a star; each one opens its page on the site."""
    focus = focus or []
    open_, fresh, soon, today = split(tenders, at, since)
    day = tp.hy_date(at, weekday=True)
    mine = sum(ours(t, stems or []) for t in fresh)
    star = f"\n⭐ «Մեր դաշտի» ուղղություններով՝ <b>{mine}</b>" if mine else ""

    if period != "morning":
        if not fresh:
            return None
        when = f"ժամը {since.strftime('%H:%M')}-ից" if since.date() == at.date() else "վերջին հաղորդագրությունից"
        out = [f"<b>Մրցույթներ</b> · {day}", "",
               f"🆕 {when} հետո՝ <b>{len(fresh)}</b> նոր մրցույթ{star}",
               esc(_sector_line(fresh)), ""]
        out += ["\n\n".join(_items(fresh, focus, app_url, stems))]
        return "\n".join(out)

    out = [f"<b>Մրցույթներ</b> · {day}", "",
           f"🆕 Նոր՝ <b>{len(fresh)}</b>{star}",
           f"⏳ Առաջիկա 3 օրում փակվում է՝ <b>{len(soon)}</b>",
           f"📂 Ընդամենը բաց՝ <b>{len(open_)}</b>"]
    if today:
        out += ["", "<b>Այսօր փակվում է</b>"]
        for t in today[:6]:
            name = esc(headline(t, 80))
            if app_url:
                name = f'<a href="{esc(app_url)}#t{t["id"]}">{name}</a>'
            out.append(f"• {parse(t['end']).strftime('%H:%M')} — {name}")
        if len(today) > 6:
            out.append(f"…և ևս {len(today) - 6}")
    if fresh:
        out += ["", "<b>Նոր մրցույթները</b>", esc(_sector_line(fresh)), "",
                "\n\n".join(_items(fresh, focus, app_url, stems))]
    else:
        out += ["", "Երեկվանից նոր մրցույթ չի հրապարակվել։"]
    return "\n".join(out)


def welcome(tenders: list[dict], at: datetime) -> str:
    open_ = [t for t in tenders if is_open(t, at)]
    today = [t for t in open_ if (_published(t) or datetime.min).date() == at.date()]
    lines = [
        "Բարև Ձեզ։",
        "",
        "Այս բոտը հետևում է Հայաստանի պետական գնումներին ARMEPS-ում՝ էլեկտրոնային աճուրդներին, "
        "գնանշման հարցումներին և մրցույթներին, և պարզ հայերենով տեղեկացնում նորերի մասին։",
        "",
        "• Առավոտյան՝ նոր մրցույթները և մոտակա վերջնաժամկետները",
        "• Մոտ 12:00-ին, 15:00-ին և 18:00-ին՝ նոր հրապարակվածները, եթե կան",
        "• ⭐ նշանով են «Մեր դաշտի» ուղղությունների մրցույթները",
        "",
        "Մրցույթի անվան վրա սեղմելով կբացվի նրա էջը։ Բոլոր մրցույթները՝ «Մրցույթներ» կոճակով։",
        "Հաղորդագրությունները դադարեցնելու համար գրեք /stop։",
    ]
    if open_:
        lines += ["", f"Այս պահին բաց է <b>{len(open_)}</b> մրցույթ, "
                      f"այսօր հրապարակվել է <b>{len(today)}</b>-ը։"]
    return "\n".join(lines)


GOODBYE = "Հաղորդագրությունները դադարեցված են։ Վերսկսելու համար գրեք /start։"
HINT = ("Նոր մրցույթների մասին կգրեմ օրը մինչև չորս անգամ՝ երկուշաբթիից շաբաթ։ "
        "Բոլոր մրցույթները տեսնելու համար սեղմեք «Մրցույթներ» կոճակը։")
BUTTON = "Բացել մրցույթները"
MENU = "Մրցույթներ"
DESCRIPTION = ("Հայաստանի պետական մրցույթները՝ օրը չորս անգամ, պարզ հայերենով։ "
               "Սկսելու համար սեղմեք START։")
SHORT_DESCRIPTION = "Հայաստանի պետական մրցույթները՝ օրը չորս անգամ, պարզ հայերենով"
COMMANDS = [("start", "Ստանալ ամենօրյա հաղորդագրությունները"),
            ("stop", "Դադարեցնել հաղորդագրությունները")]
