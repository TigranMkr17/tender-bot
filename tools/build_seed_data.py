"""Build the app's data file (docs/data/tenders.json) from the notices saved in tools/seed_*.json.

Used for tests and for the preview: it runs the same clean-up the live bot runs,
so the preview shows exactly what the real pipeline produces.
"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import store, textproc as tp  # noqa: E402

INV = "https://eauction.armeps.am/application/documents/public_invitation/tender_{id}.zip"


def t16(ts):
    return ts.replace(" ", "T")[:16]


def build(seed_path, out_path, note=None):
    with open(seed_path, encoding="utf-8") as fh:
        seed = json.load(fh)
    items = []
    for s in seed["tenders"]:
        t = {"id": s["id"], "code": s["code"], "lots": s["lots"], "title": s["title"],
             "status": store.status_key(s["status"]), "status_text": s["status"],
             "end": t16(s["deadline"]), "seen": seed["fetched"]}
        if s.get("buyer"):
            t.update(buyer_official=s["buyer"], kind=tp.kind_key(s["kind"]),
                     pub=t16(s["published"]), ask=t16(s["questions_until"]),
                     auc=t16(s["auction"]), inv=INV.format(id=s["id"]), dt=1)
        items.append(t)
    store.enrich(items)
    at = store.parse(seed["fetched"])
    meta = {"updated": seed["fetched"], "source": "eauction.armeps.am",
            "open": sum(store.is_open(t, at) for t in items)}
    if note:  # a preview: the app shows the note and keeps the clock at the fetch time
        meta["note"] = note
        meta["preview"] = True
    data = {"meta": meta, "tenders": [store.compact(t) for t in items]}
    store.publish(data, out_path)
    return data


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "tools/seed_2026-11-13.json"
    dst = sys.argv[2] if len(sys.argv) > 2 else "docs/data/tenders.json"
    note = sys.argv[3] if len(sys.argv) > 3 else None
    d = build(src, dst, note)
    print(f"{len(d['tenders'])} tenders -> {dst} ({os.path.getsize(dst)} bytes)")
