"""Read an invitation archive: what the lots are, what a bid has to carry, who to ask.

Invitations follow the Ministry of Finance's standard form, so the same two tables turn up
in every one: the list of lots (number, item code, name, technical description) and the
purchase schedule (unit, quantity, delivery address and time)."""
from __future__ import annotations

import io
import re
import zipfile

from . import docx_read

_NUM = re.compile(r"^\d{1,4}$")
_CPV = re.compile(r"\b(\d{8})(?:\s*/\s*(\d+))?\b")
_QUAL = re.compile(r"Որակավորման ապահովման չափը[^։:]{0,160}?(\d+(?:[.,]\d+)?)\s*տոկոս", re.I)
_CONTRACT = re.compile(r"Պայմանագրի ապահովման չափը[^։:]{0,160}?(\d+(?:[.,]\d+)?)\s*տոկոս", re.I)
_BID = re.compile(r"Հայտի ապահովման չափը[^։:]{0,160}?(\d+(?:[.,]\d+)?)\s*տոկոս", re.I)
_PHONE = re.compile(r"Հեռախոս\w*\s*[`՝:․.]?\s*((?:\+|0)[\d\s()\-]{6,20}\d)")
_MAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_REFERS = re.compile(r"կցված|կից ֆայլ|հայտ-տեխնիկական|տես\s+հավելված", re.I)
SPEC_LIMIT = 900


def _names(z: zipfile.ZipFile) -> list[str]:
    out = []
    for info in z.infolist():
        name = info.filename
        if not info.flag_bits & 0x800:                 # not marked UTF-8: undo the DOS code page
            try:
                name = name.encode("cp437").decode("utf-8")
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass
        out.append(name)
    return out


def _main_doc(z: zipfile.ZipFile) -> str | None:
    """The Armenian invitation: hraver.docx, or the largest .docx that is not the Russian copy."""
    docs = [i for i in z.infolist() if i.filename.lower().endswith(".docx")]
    for i in docs:
        if i.filename.lower().rsplit("/", 1)[-1] == "hraver.docx":
            return i.filename
    docs = [i for i in docs if not re.search(r"_ru\.docx$|rus", i.filename.lower())]
    return max(docs, key=lambda i: i.file_size).filename if docs else None


def _number(text: str) -> float | None:
    t = re.sub(r"[\s ]", "", text or "").replace(",", ".")
    try:
        return float(t) if t else None
    except ValueError:
        return None


def _lots(tables: list[list[list[str]]]) -> list[dict]:
    lots: dict[int, dict] = {}
    for rows in tables:                                  # the list of lots
        head = " ".join(" ".join(r) for r in rows[:3]).lower()
        if "չափաբաժնի համար" not in head or "բնութագ" not in head or not ("cpv" in head or "գմա" in head):
            continue
        for r in rows:
            if len(r) >= 3 and _NUM.match(r[0].strip()) and _CPV.search(r[1]):
                m = _CPV.search(r[1])
                n = int(r[0])
                spec = r[3].strip() if len(r) > 3 else ""
                if len(spec) < 80 and _REFERS.search(spec):
                    spec = ""                            # "see the attached file": nothing to show
                lots.setdefault(n, {"n": n, "cpv": m.group(1), "name": r[2].strip(),
                                    "spec": spec[:SPEC_LIMIT] + ("…" if len(spec) > SPEC_LIMIT else "")})
        if lots:
            break
    for rows in tables:                                  # the purchase schedule
        head = " ".join(" ".join(r) for r in rows[:3]).lower()
        if "չափման միավոր" not in head or "քանակ" not in head or "հասցե" not in head:
            continue
        for r in rows:
            if len(r) >= 5 and _NUM.match(r[0].strip()) and int(r[0]) in lots:
                lot = lots[int(r[0])]
                lot["unit"] = r[1].strip()
                lot["qty"] = _number(r[4])
                if len(r) > 5 and r[5].strip():
                    lot["addr"] = r[5].strip()[:200]
                if len(r) > 7 and r[7].strip():
                    lot["when"] = r[7].strip()[:260]
        break
    return [lots[n] for n in sorted(lots)]


def read(data: bytes) -> dict | None:
    """{'lots': [...], 'sec': {...}, 'ask': {...}, 'files': [...]} or None when it cannot be read."""
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
        main = _main_doc(z)
        if not main:
            return None
        blocks = docx_read.blocks(io.BytesIO(z.read(main)))
    except (zipfile.BadZipFile, KeyError, ValueError, SyntaxError, OSError):
        return None
    tables = [v for k, v in blocks if k == "T"]
    paras = [v for k, v in blocks if k == "P"]
    text = "\n".join(paras)
    sec = {}
    for key, rx in (("qual", _QUAL), ("contract", _CONTRACT), ("bid", _BID)):
        m = rx.search(text)
        if m:
            sec[key] = float(m.group(1).replace(",", "."))
    head = "\n".join(paras[:60])
    ask = {}
    m = _PHONE.search(head)
    if m:
        ask["phone"] = re.sub(r"[\s()\-]", "", m.group(1))
    m = _MAIL.search(head)
    if m:
        ask["mail"] = m.group(0).rstrip(".")
    return {"lots": _lots(tables), "sec": sec, "ask": ask,
            "files": [n.rsplit("/", 1)[-1] for n in _names(z)]}
