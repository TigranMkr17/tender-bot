"""Past prices: for every open tender, the contracts most like it in the contracts register (docs/data/k, every
procedure, the last year or so), with the company that got each one and its price.

The page shows them in the tender's sheet under «Նման պայմանագրեր». They are worked out here, at each update, and
written to docs/data/p/<id % 16>.json, so that a phone downloads only the sixteenth it needs.

Likeness is by the words of the subject. Words that say nothing about what is bought (purchase, needs, goods,
services...), places (Yerevan, its districts, the regions, streets named after people) and words found in a large
share of all contracts are left out; the rest are cut to a stem, so that մանկապարտեզի and մանկապարտեզների meet.
Rare words count for more (inverse document frequency); a contract of the same buyer counts a little more."""
from __future__ import annotations

import glob
import json
import math
import os
import re
from collections import Counter, defaultdict
from statistics import median

from . import contracts, store

REGISTER = "docs/data/k"
OUT = "docs/data/p"
BUCKETS = 16
SHOWN = 5             # contracts shown for one tender
POOL = 30             # the most alike contracts, from which the usual discount is worked out
COMMON = 0.08         # a word found in more of all contracts than this (and in over 50) says too little to match on
MIN_SCORE = 0.3       # less alike than this is not shown
SAME_BUYER = 0.15     # what a contract of the same buyer adds to its likeness
SUBJECT = 140         # characters of a contract's subject that are kept

STOP = set("""ձեռքբերում ձեռք բերում բերման ձեռքբերման ձեռքբերումը համար կարիքների կարիք կարիքներ ապրանք ապրանքներ
ապրանքի ապրանքների ծառայություն ծառայություններ ծառայության ծառայությունների աշխատանք աշխատանքներ աշխատանքի
աշխատանքների մատուցում մատուցման իրականացում իրականացման տարվա թվականի թվական թվականին տարի կողմից նպատակով
հետ վրա այլ որոնք որը նաև ինչպես նույն մասին ընթացքում համայնքի համայնքապետարանի մարզի մարզպետի աշխատակազմի
նախարարության ծածկագրով հայաստանի հանրապետության փբը սպը պոակ հոակ""".split())
PLACE = """երևան քաղաք վարչական շրջան թաղամաս փողոց պողոտա գյուղ մարզ համայնք կենտրոն արաբկիր աջափնյակ ավան
դավթաշեն էրեբունի մալաթիա սեբաստիա նորք մարաշ նուբարաշեն շենգավիթ քանաքեռ զեյթուն արագածոտն արարատ արմավիր
գեղարքունիք լոռի կոտայք շիրակ սյունիք վայոց ձոր տավուշ գյումրի վանաձոր աբովյան կապան հրազդան էջմիածին
վաղարշապատ արտաշատ գավառ իջևան գորիս սևան մեղրի սիսիան դիլիջան աշտարակ""".split()
SUFFIX = ("ներից", "ներին", "ներով", "ների", "ները", "ներ", "երից", "երին", "երով", "երի", "երը", "եր",
          "ից", "ով", "ում", "ին", "ի", "ը")     # not ն: too many words end in it (շրջան, երևան, համայնքապետարան)
SURNAME = re.compile(r"յան(ի|ց|ներ|ների)?$")         # streets and schools named after people


def stem(word: str) -> str:
    """The word without its case or plural ending, cut to eight letters."""
    for suffix in SUFFIX:
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            word = word[: -len(suffix)]
            break
    return word[:8]


PLACE_STEMS = {stem(contracts.norm(p).strip()) for p in PLACE}


def stems(text: str | None) -> set[str]:
    """The stems of the words of a subject that say what is bought."""
    out = set()
    for w in contracts.norm(text).split():
        if len(w) < 4 or not w.isalpha() or w in STOP or SURNAME.search(w):
            continue
        s = stem(w)
        if s not in PLACE_STEMS:
            out.add(s)
    return out


def _buyer_key(name: str | None) -> str:
    n = contracts.norm(re.sub(r"[«»\"“”]", "", name or ""))
    n = re.sub(r" (փբը|սպը|պոակ|հոակ|բբը|հկ) ", " ", n)
    return re.sub(r"^ հհ ", " ", n).strip()


def rows_of(page: dict) -> list[dict]:
    """One month of the register (as bot/contracts.py writes it) as plain rows."""
    out = []
    for r in page.get("R", []):
        day, b, s, value, est, form, kind, subj = r[:8]
        buyer, supplier = page["B"][b], page["S"][s]
        out.append({"d": f"{page['m']}-{day:02d}", "b": buyer[1], "s": "" if supplier[3] else supplier[1],
                    "v": value or 0, "e": est or 0, "f": page["F"][form], "k": kind or "", "subj": subj or ""})
    return out


class Register:
    """The contracts, with the stems of their subjects and how rare each stem is."""

    def __init__(self, rows: list[dict]):
        self.rows = rows
        df = Counter()
        for r in rows:
            r["st"] = stems(r["subj"])
            r["bk"] = _buyer_key(r["b"])
            df.update(r["st"])
        n = max(len(rows), 1)
        self.idf = {s: math.log(n / c) for s, c in df.items()}
        self.useful = {s for s, c in df.items() if c < max(COMMON * n, 50)}
        self.by_stem: dict[str, list[int]] = defaultdict(list)
        for i, r in enumerate(rows):
            for s in r["st"] & self.useful:
                self.by_stem[s].append(i)
        self.first = min((r["d"] for r in rows), default="")

    @classmethod
    def load(cls, folder: str = REGISTER) -> "Register | None":
        rows = []
        for path in sorted(glob.glob(os.path.join(folder, "[0-9][0-9][0-9][0-9]-[0-9][0-9].json"))):
            with open(path, encoding="utf-8") as fh:
                rows.extend(rows_of(json.load(fh)))
        return cls(rows) if rows else None

    def similar(self, t: dict, top: int = POOL) -> list[tuple[float, dict]]:
        """The contracts most like the tender, most alike first, then newest first."""
        words = stems(t.get("subject") or t.get("title"))
        mine = words & self.useful
        if not mine:
            return []
        norm_t = math.sqrt(sum(self.idf[s] ** 2 for s in mine))
        dot, shared = Counter(), Counter()
        for s in mine:
            for i in self.by_stem[s]:
                dot[i] += self.idf[s] ** 2
                shared[i] += 1
        need = min(2, len(words))                       # a long subject must meet a contract in two words at least
        buyers = {_buyer_key(t.get("buyer")), _buyer_key(t.get("buyer_official"))} - {""}
        found = []
        for i, d in dot.items():
            if shared[i] < need:
                continue
            r = self.rows[i]
            norm_c = math.sqrt(sum(self.idf[s] ** 2 for s in r["st"] & self.useful)) or 1.0
            score = d / (norm_t * norm_c) + (SAME_BUYER if r["bk"] in buyers else 0.0)
            if score >= MIN_SCORE:
                found.append((round(score, 3), r))
        found.sort(key=lambda x: (-x[0], tuple(-ord(c) for c in x[1]["d"])))
        return found[:top]


def entry(t: dict, found: list[tuple[float, dict]]) -> dict | None:
    """What the page needs for one tender: the contracts to show, and the usual discount below the estimate."""
    if not found:
        return None
    buyers = {_buyer_key(t.get("buyer")), _buyer_key(t.get("buyer_official"))} - {""}
    rows = [[r["d"], "" if r["bk"] in buyers else r["b"], r["s"], round(r["v"]), round(r["e"]), r["f"],
             r["subj"][:SUBJECT]] for _, r in found[:SHOWN]]
    cuts = [(r["e"] - r["v"]) / r["e"] for _, r in found if r["e"] > 0 and 0 < r["v"] <= r["e"] * 1.02]
    out = {"r": rows}
    if len(cuts) >= 4:
        out["u"] = [max(0, round(median(cuts) * 100)), len(cuts)]
    return out


def publish(tenders: list[dict], at, folder: str = REGISTER, out: str = OUT) -> int:
    """Write the past prices of every open tender. Returns how many tenders have some."""
    reg = Register.load(folder)
    if reg is None:
        return 0
    buckets: dict[int, dict] = {i: {} for i in range(BUCKETS)}
    for t in tenders:
        if not store.is_open(t, at):
            continue
        e = entry(t, reg.similar(t))
        if e:
            buckets[t["id"] % BUCKETS][str(t["id"])] = e
    os.makedirs(out, exist_ok=True)
    for i, items in buckets.items():
        with open(os.path.join(out, f"{i}.json"), "w", encoding="utf-8") as fh:
            json.dump({"updated": store.stamp(at), "from": reg.first, "t": items}, fh, ensure_ascii=False,
                      separators=(",", ":"))
    return sum(len(b) for b in buckets.values())
