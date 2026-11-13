"""Turn official ARMEPS wording into something a person can read at a glance.

Everything here is plain string work on Armenian text:
  * smart_case   - "ՎԱՆԱՁՈՐԻ ԲԺՇԿԱԿԱՆ ԿԵՆՏՐՈՆ ՓԲԸ" -> "Վանաձորի բժշկական կենտրոն ՓԲԸ"
  * split_title  - official title -> (what is bought, for whose needs)
  * classify     - which sector a tender belongs to
  * date helpers - Armenian weekday / month names

Nothing is invented: every output is a rearrangement of words the source
already contains, and the official title is always kept alongside.
"""
from __future__ import annotations

import re
from datetime import datetime

# --------------------------------------------------------------------------
# Armenian casing
# --------------------------------------------------------------------------

VOWELS = set("աեէըիոօ")

#: Abbreviations that must stay in capitals.
ABBR = {
    "ՀՀ", "ՓԲԸ", "ՍՊԸ", "ԲԲԸ", "ՊՈԱԿ", "ՀՈԱԿ", "ՈԱԿ", "ՀԿ", "ՀԿՀ", "ԲԿ", "ԱԿ", "ԱՁ",
    "ԱՆ", "ՆԳՆ", "ՊՆ", "ԱԳՆ", "ՖՆ", "ԷՆ", "ԿԳՄՍՆ", "ՏԿԵՆ", "ԱՍՀՆ", "ՇՄՆ", "ԲՏԱՆ", "ԱԻՆ",
    "ՊԵԿ", "ԱԱԾ", "ՔԿ", "ՔԿԾ", "ՀԱԷԿ", "ԵՊՀ", "ՀԱՊՀ", "ԵՊԲՀ", "ԳԱԱ", "ԱԱՊԿ", "ԿՏ",
    "ՄՌՏ", "ՏՏ", "ՀՀՌ", "ԵՔ", "ՀԾԿՀ", "ՎԿ", "ՍԴ", "ԿԲ", "ԲՈՒՀ", "ՀՕՊ", "ՊՎԾ", "ՀԷՑ",
}

#: Short ordinary words that look like abbreviations when written in capitals.
SMALL_WORDS = {
    "և", "ու", "կամ", "թիվ", "ոչ", "բաց", "փակ", "մեծ", "նոր", "հին", "մեկ", "այլ", "ըստ",
    "հետ", "մեջ", "թվի", "թվ", "օր", "տուն", "ջուր", "գազ", "հաց", "միս", "կաթ", "ձու",
    "աղ", "թեյ", "սուրճ", "մաս", "տակ", "վրա", "կից", "համար", "մինչև", "կողմից",
}

#: Ordinary words that often appear inside organisation names (kept lower-case).
COMMON = set("""
նախարարություն նախարարության կոմիտե կոմիտեի ծառայություն ծառայության վարչություն
վարչության գործակալություն գործակալության տեսչական մարմին մարմնի աշխատակազմ աշխատակազմի
դեպարտամենտ դեպարտամենտի հիմնադրամ հիմնադրամի կենտրոն կենտրոնի համալսարան համալսարանի
ակադեմիա ակադեմիայի ինստիտուտ ինստիտուտի թանգարան թանգարանի գրադարան գրադարանի
հիվանդանոց հիվանդանոցի պոլիկլինիկա պոլիկլինիկայի դպրոց դպրոցի մանկապարտեզ մանկապարտեզի
քոլեջ քոլեջի վարժարան թատրոն թատրոնի համայնք համայնքի համայնքապետարան համայնքապետարանի
քաղաքապետարան քաղաքապետարանի մարզպետարան մարզպետարանի մարզ մարզի վարչական շրջան շրջանի
ընկերություն ընկերության կազմակերպություն կազմակերպության հիմնարկ հիմնարկի
հաստատություն հաստատության միություն միության բաժնետիրական պետական ազգային
հանրապետական հանրային համայնքային գիտական գիտահետազոտական բժշկական բժշկագիտական
առողջապահական առողջության առողջապահության հոգեկան ուռուցքաբանության մանկական կրթական
ուսումնական նախադպրոցական մշակութային մարզական սոցիալական տնտեսական տեխնիկական
տեխնոլոգիական էկոնոմիկայի ֆինանսների արդարադատության պաշտպանության կրթության գիտության
մշակույթի սպորտի աշխատանքի հարցերի տարածքային կառավարման ենթակառուցվածքների շրջակա
միջավայրի ներքին գործերի արտաքին արտակարգ իրավիճակների բարձր արդյունաբերության
արհեստական բանականության էկոպարեկային քրեակատարողական փրկարար ոստիկանության
անվտանգության եկամուտների վիճակագրական դատական ընտրական հանձնաժողով հանձնաժողովի
խորհուրդ խորհրդի ատոմային էլեկտրակայան էլեկտրակայանի էլեկտրացանցեր բարձրավոլտ
էլեկտրական ցանցեր մետրոպոլիտեն մետրոպոլիտենի երկաթուղի ջրմուղ աղբահանություն
սանիտարական մաքրում անվան առևտրային մասնագիտացված կլինիկական վերականգնողական
ախտորոշիչ ծրագրերի իրականացման գրասենյակ գրասենյակի կառավարության կարիքների
ձեռքբերում ձեռքբերման գնման ընթացակարգ ծառայությունների աշխատանքների ապրանքների
անհրաժեշտ հագեցման սարքավորման սարքավորումների տպագրական
""".split())

#: Words where "եվ" is two separate sounds and must not become "և".
EV_KEEP = {"ագեվազ", "հոգեվարք", "հոգեվիճակ", "տարեվերջ", "կարեվեր", "ոսկեվառ", "գերեվարել"}

_LETTERS = re.compile(r"[^\W\d_]+|[\W\d_]+", re.UNICODE)


def _fix_ev(word: str) -> str:
    """Lower-casing ԵՎ gives 'եվ'; inside a word modern spelling writes 'և'."""
    if word == "եվ":
        return "և"
    if any(word.startswith(k) for k in EV_KEEP) or "եվ" not in word[1:]:
        return word
    return word[0] + word[1:].replace("եվ", "և")


def is_shouting(text: str) -> bool:
    """True when a string is (almost) entirely in capitals."""
    letters = [c for c in text if c.isalpha()]
    if len(letters) < 4:
        return False
    return sum(c.isupper() for c in letters) / len(letters) > 0.8


def _looks_abbr(word: str) -> bool:
    low = word.lower()
    if word in ABBR:
        return True
    if low in SMALL_WORDS or _fix_ev(low) in SMALL_WORDS:
        return False
    if len(word) <= 3:
        return True
    return len(word) <= 6 and sum(c in VOWELS for c in low) <= 1


class Casing:
    """Learns from properly-cased text which words are names and which are not."""

    def __init__(self) -> None:
        self.lower: set[str] = set(COMMON) | SMALL_WORDS
        self.proper: set[str] = set()
        self.abbr: set[str] = set(ABBR)

    def learn(self, texts) -> "Casing":
        seen_proper: set[str] = set()
        for text in texts:
            if not text or is_shouting(text):
                continue
            first = True
            for tok in _LETTERS.findall(text):
                if not tok[0].isalpha():
                    if any(ch in tok for ch in "«(\"“"):
                        first = True  # a quote or bracket starts a new phrase
                    continue
                if len(tok) < 2:
                    first = False
                    continue
                if tok.isupper():
                    if len(tok) <= 6:
                        self.abbr.add(tok)
                elif tok.islower():
                    self.lower.add(tok)
                elif tok[0].isupper() and tok[1:].islower() and not first:
                    seen_proper.add(tok)
                first = False
        # A word seen both ways is an ordinary word someone capitalised by habit.
        self.proper |= {w for w in seen_proper if w.lower() not in self.lower}
        return self

    def fix(self, text: str, kind: str = "name") -> str:
        """Re-case an ALL-CAPS string. kind='name' for organisations, 'title' for notices."""
        if not text or not is_shouting(text):
            return text
        out: list[str] = []
        prev_abbr = False
        prev_sep = ""
        for tok in _LETTERS.findall(text):
            if not tok[0].isalpha():
                out.append(tok)
                prev_sep = tok
                continue
            low = _fix_ev(tok.lower())
            if prev_abbr and prev_sep == "-" and len(tok) <= 4:
                word = low  # case ending after an abbreviation: ՓԲԸ-Ի -> ՓԲԸ-ի
                prev_abbr = False
            elif tok in self.abbr or (_looks_abbr(tok) and low not in self.lower):
                word = tok
                prev_abbr = True
            else:
                prev_abbr = False
                if low in self.lower:
                    word = low
                elif low.capitalize() in self.proper:
                    word = low.capitalize()
                else:
                    word = low.capitalize() if kind == "name" else low
            out.append(word)
            prev_sep = ""
        result = "".join(out)
        return _cap_first(result)


def _cap_first(text: str) -> str:
    for i, ch in enumerate(text):
        if ch.isalpha():
            return text[:i] + ch.upper() + text[i + 1:]
        if ch.isdigit():
            break
    return text


# --------------------------------------------------------------------------
# Official title -> what is bought / for whose needs
# --------------------------------------------------------------------------

_WS = re.compile(r"\s+")
_QUOTES = "«»\"“”'`՝ "

#: Procedural boilerplate that says nothing about the subject.
_BOILERPLATE = [
    r"էլեկտրոնային\s+աճուրդի\s+(?:գնման\s+)?ընթացակարգ(?:ով|ի)?",
    r"(?:գնման\s+)?ընթացակարգի?\s+հայտար\w*\s*(?:և|եվ|ու|,)?\s*հրավեր\w*",
    r"հայտար\w*\s*(?:և|եվ|ու|,)\s*հրավեր\w*",
    r"էլեկտրոնային\s+աճուրդի\s+հայտար\S*",
    r"գնման\s+ընթացակարգի?",
    r"ծածկագրով",
    r"կենտրոնացված\s+կարգով",
    r"հայտար\w*\s*$",
    r"հրավեր\w*\s*$",
    r"էլեկտրոնային\s+աճուրդ(?:ով|ի)?\s*$",
]
_BOILER_RE = [re.compile(p, re.IGNORECASE | re.UNICODE) for p in _BOILERPLATE]
_PURPOSE = re.compile(r"\s+ձեռք\s?բերման\s+նպատակով", re.IGNORECASE)
_NEEDS = re.compile(r"\s+կարիքների\s+համար[`՝,:]?\s*", re.IGNORECASE)
_BY = re.compile(r"-?ի\s+կողմից\s+", re.IGNORECASE)
_YEAR_TAIL = re.compile(r"[\s,]*\d{4}\s*(?:թվականի|թ\.?)?\s*$")
_ACQ_END = re.compile(r"\s*ձեռք\s?բեր(?:ում|ման)\s*$", re.IGNORECASE)
_GENITIVE = re.compile(r"(?:ների|երի|ության|ման|ի)$")


_CODE_TOKEN = re.compile(r"[«\"“]?\S*ՁԲ\S*\d\S*")


def _strip_code(text: str, code: str) -> str:
    if code:
        for variant in {code, code.replace(" ", ""), code.replace("-", " ")}:
            text = re.sub(r"[«\"“]?\s*" + re.escape(variant) + r"\s*[»\"”]?", " ", text)
    return _CODE_TOKEN.sub(" ", text)


def _tidy(text: str) -> str:
    text = _WS.sub(" ", text).replace(" ,", ",").strip()
    text = text.strip(" ,.;:՝`-–—։")
    # drop wrapping quotes, close a bracket the source left open
    if text.startswith("«") and text.count("«") > text.count("»"):
        text = text[1:]
    if text.startswith("«") and text.endswith("»") and text.count("«") == 1:
        text = text[1:-1]
    text = text.rstrip("»") if text.count("»") > text.count("«") else text
    if text.count("(") > text.count(")"):
        text += ")"
    return _WS.sub(" ", text).strip()


def _with_acquisition(subject: str, quoted: bool) -> str:
    """'մալուխի' -> 'մալուխի ձեռքբերում' when the phrase is in the genitive."""
    if _ACQ_END.search(subject):
        return _ACQ_END.sub("", subject).rstrip() + " ձեռքբերում"
    if quoted:
        return subject
    words = subject.split()
    last = re.sub(r"[^\w]", "", words[-1]) if words else ""
    ordinary = last.islower() or (len(words) == 1 and last[1:].islower())
    if len(last) > 3 and ordinary and _GENITIVE.search(last):
        return subject + " ձեռքբերում"
    return subject


def split_title(title: str, code: str = "") -> tuple[str | None, str | None]:
    """Return (subject, for_whom). Either can be None when the title does not say."""
    if not title:
        return None, None
    text = _WS.sub(" ", title).strip()
    cut_off = text.endswith(("…", "..."))  # the source itself shortened this title
    text = text.rstrip("….").strip()
    for_whom = None

    m = _NEEDS.search(text)
    if m and m.start() > 2:
        for_whom = _YEAR_TAIL.sub("", text[: m.start()]).strip(" ,")
        rest = text[m.end():]
    else:
        m = _BY.search(text)
        if m and m.start() > 2:
            rest = text[m.end():]
        else:
            rest = text

    rest = _strip_code(rest, code)
    quoted = False
    m = _PURPOSE.search(rest)
    if m:
        head = rest[: m.start()].strip()
        quoted = head.startswith("«") or head.endswith("»")
        rest = head + " ձեռքբերում" if not quoted else head
    for rx in _BOILER_RE:
        rest = rx.sub(" ", rest)
    rest = _tidy(rest)
    if len(re.sub(r"[^\w]", "", rest)) < 3:
        return None, for_whom or None
    subject = _cap_first(_with_acquisition(rest, quoted or cut_off))
    return subject, (for_whom or None)


def _stems(text: str) -> set[str]:
    words = re.findall(r"[^\W\d_]{3,}", text.lower())
    return {_fix_ev(w)[:5] for w in words}


def same_party(for_whom: str | None, buyer: str | None) -> bool:
    """True when 'for whose needs' adds nothing to the buyer's name."""
    if not for_whom or not buyer:
        return False
    words = re.findall(r"[^\W\d_]+", for_whom)
    if words and all(w.isupper() for w in words):
        initials = "".join(w[0].upper() if not w.isupper() else w
                           for w in re.findall(r"[^\W\d_]+", buyer))
        return all(w in initials for w in words)
    a, b = _stems(for_whom), _stems(buyer)
    if not a or not b:
        return False
    if a <= b:
        return True
    return len(a & b) / len(a | b) >= 0.5


# --------------------------------------------------------------------------
# Sectors
# --------------------------------------------------------------------------

#: (key, Armenian label, [(pattern, weight), ...]) - order breaks ties.
SECTORS = [
    ("med", "Բժշկական", [
        ("դեղ", 2), ("բժշկ", 2), ("լաբորատոր", 2), ("ռեագենտ", 2), ("ազդանյութ", 2),
        ("մանրէաբան", 2), ("ախտորոշ", 2), ("վիրաբուժ", 2), ("ստոմատոլոգ", 2),
        ("ատամնաբուժ", 2), ("պատվաստ", 2), ("թթվածին", 2), ("սոնոգրաֆ", 3),
        ("շերտագր", 3), ("ռենտգեն", 3), ("ախտահան", 2), ("ներարկիչ", 2),
        ("վիրակապ", 2), ("հիվանդ", 1), ("արյան", 2),
    ]),
    ("food", "Սնունդ", [
        ("սննդ", 2), ("սնունդ", 2), ("մթերք", 2), ("հացաբուլկեղեն", 2), (r"\bհաց", 2),
        ("մսամթերք", 2), (r"\bմիս", 2), ("կաթնամթերք", 2), (r"\bկաթ", 1), ("պանիր", 2),
        ("բանջարեղեն", 2), ("միրգ", 2), (r"\bձու", 2), ("ձեթ", 2), ("շաքար", 2),
        ("ալյուր", 2), ("խմելու ջ", 2), ("հյութ", 2), ("մակարոն", 2), ("կարագ", 2),
    ]),
    ("fuel", "Վառելիք", [
        ("բենզին", 3), ("դիզել", 3), ("վառելիք", 3), (r"\bգազ(?:ի|ով|ը)?\b", 3),
        ("քսայուղ", 2), ("վառելափայտ", 3), ("ածուխ", 2), ("էլեկտրաէներգ", 3),
    ]),
    ("build", "Շինարարություն", [
        ("շինարար", 3), ("վերանորոգ", 3), ("հիմնանորոգ", 3), ("նորոգման", 2),
        ("շինանյութ", 3), ("ասֆալտ", 3), ("բետոն", 2), ("ցեմենտ", 2), ("տանիք", 2),
        ("ճանապարհ", 2), ("բարեկարգ", 2), ("սալիկ", 2), ("խողովակ", 2), ("կոյուղ", 2),
        ("ջրագ", 2), ("նախագծանախահաշվ", 3), ("ներկ", 1),
    ]),
    ("it", "ՏՏ և կապ", [
        ("համակարգչ", 2), ("համակարգիչ", 2), ("ծրագրային", 2), ("լիցենզիա", 2),
        ("սերվեր", 2), ("տպիչ", 2), ("քարթրիջ", 2), ("պատճենահան", 2), ("հեռախոս", 2),
        ("ինտերնետ", 2), ("կապի ծառայ", 2), ("մոնիտոր", 2), ("տեսախց", 2),
        ("տեսահսկ", 2), ("ցանցային", 2), ("նոութբուք", 2), ("պլանշետ", 2),
    ]),
    ("auto", "Տրանսպորտ", [
        ("ավտոմեքենա", 2), ("ավտոբուս", 2), ("ավտոմոբիլ", 2), ("անվադող", 2),
        ("ուղևորափոխադր", 2), ("փոխադրման", 2), ("տրանսպորտ", 2), ("տրակտոր", 2),
        ("աղբատար", 2), ("ավտոպահեստամաս", 2), ("մեքենաների", 1), ("ավտոտեխսպասարկ", 2),
    ]),
    ("elec", "Էլեկտրական", [
        ("մալուխ", 2), ("էլեկտրական", 1), ("էլեկտրաապրանք", 2), ("լուսատու", 2),
        ("լամպ", 2), ("լուսավորութ", 2), ("կուտակիչ", 2), ("մարտկոց", 2),
        ("կենցաղային տեխնիկա", 2), ("տրանսֆորմատոր", 2), ("էլեկտրատեխնիկ", 2),
    ]),
    ("furn", "Կահույք", [
        ("կահույք", 2), ("կահավոր", 2), ("մարզագույք", 2), ("գույք", 1), ("աթոռ", 2),
        ("սեղան", 2), ("պահարան", 2), ("դարակաշար", 2), ("մահճակալ", 2),
        ("ճոճանակ", 2), ("սահարան", 2), ("խաղահրապարակ", 2), ("նստարան", 2),
    ]),
    ("home", "Տնտեսական", [
        ("տնտեսական", 2), ("հիգիեն", 2), ("մաքրող", 2), ("լվացող", 2), ("սանիտար", 1),
        ("զուգարան", 3), ("աղբ", 1), ("օճառ", 2), ("անձեռոցիկ", 2), ("կենցաղային", 1),
    ]),
    ("cloth", "Հագուստ", [
        ("հագուստ", 2), ("համազգեստ", 2), ("կոշիկ", 2), ("անկողն", 2), ("սպիտակեղեն", 2),
        ("հանդերձանք", 1), ("գործվածք", 2), ("փափուկ գույք", 3), ("արտահագուստ", 2),
    ]),
    ("office", "Գրասենյակ", [
        ("գրենական", 2), ("գրասենյակ", 2), ("թուղթ", 2), ("թղթ", 1), ("տպագր", 2),
        ("թերմոժապավեն", 2), ("գրքեր", 2), ("բլանկ", 2), ("հրատարակ", 2),
        ("կազմման", 1), ("ձևաթ", 2),
    ]),
    ("equip", "Սարքեր", [
        ("կապարակնիք", 3), ("սարք", 1), ("գործիք", 1), ("մետաղ", 1), ("պահեստամաս", 1),
        ("տուրբին", 2), ("տվիչ", 1), ("պոմպ", 2), ("խոզանակ", 1), ("տեխնիկա", 1),
        ("հաստոց", 2), ("նյութեր", 1),
    ]),
    ("serv", "Ծառայություններ", [
        ("ծառայությ", 1), ("ապահովագր", 2), ("պահպանությ", 2), ("սպասարկ", 1),
        ("վարձակալ", 2), ("խորհրդատվ", 2), ("աուդիտ", 2), ("թարգման", 2),
        ("վերապատրաստ", 2), ("առաքման", 1),
    ]),
]
SECTOR_LABELS = {key: label for key, label, _ in SECTORS}
SECTOR_LABELS["other"] = "Այլ"
_SECTOR_RX = [(key, [(re.compile(p), w) for p, w in pats]) for key, _, pats in SECTORS]


def classify(text: str, kind: str | None = None) -> str:
    """Pick a sector from the words in the title. kind is goods/services/works."""
    low = _fix_ev((text or "").lower())
    best, best_score = "other", 0
    for key, pats in _SECTOR_RX:
        score = sum(w for rx, w in pats if rx.search(low))
        if score > best_score:
            best, best_score = key, score
    if kind == "works" and best_score < 2:
        return "build"
    if kind == "services" and best_score < 2:
        return "serv"
    return best


# --------------------------------------------------------------------------
# Dates in Armenian
# --------------------------------------------------------------------------

MONTHS_GEN = ["հունվարի", "փետրվարի", "մարտի", "ապրիլի", "մայիսի", "հունիսի", "հուլիսի",
              "օգոստոսի", "սեպտեմբերի", "հոկտեմբերի", "նոյեմբերի", "դեկտեմբերի"]
WEEKDAYS = ["երկուշաբթի", "երեքշաբթի", "չորեքշաբթի", "հինգշաբթի", "ուրբաթ", "շաբաթ", "կիրակի"]


def hy_date(dt: datetime, weekday: bool = False) -> str:
    """13 նոյեմբերի  /  ուրբաթ, 13 նոյեմբերի"""
    text = f"{dt.day} {MONTHS_GEN[dt.month - 1]}"
    return f"{WEEKDAYS[dt.weekday()]}, {text}" if weekday else text


def hy_short(dt: datetime) -> str:
    """30.11"""
    return f"{dt.day:02d}.{dt.month:02d}"


KIND_KEYS = {"Ապրանք": "goods", "Ծառայություն": "services", "Աշխատանք": "works",
             "Goods": "goods", "Services": "services", "Service": "services",
             "Works": "works", "Work": "works"}


def kind_key(raw: str | None) -> str | None:
    if not raw:
        return None
    raw = raw.strip()
    for name, key in KIND_KEYS.items():
        if raw.lower().startswith(name.lower()):
            return key
    return None


def kind_from_code(code: str | None) -> str | None:
    """ԱՊՁԲ = goods, ԾՁԲ = services, ԱՇՁԲ = works (the letters before ՁԲ in the code)."""
    if not code:
        return None
    c = code.upper().replace(" ", "").replace("-", "")
    if "ԱՇՁԲ" in c:
        return "works"
    if "ԱՊՁԲ" in c:
        return "goods"
    if "ԾՁԲ" in c:
        return "services"
    return None
