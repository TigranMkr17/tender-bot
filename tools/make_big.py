"""Make a 400-tender stress file from the sample notices (for speed tests only)."""
import json, sys, copy
from datetime import datetime, timedelta
src, dst, n = sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 400
d = json.load(open(src, encoding="utf-8"))
base = [t for t in d["tenders"] if t.get("status") == "open"]
t0 = datetime(2026, 11, 13, 19, 10)
out = []
for i in range(n):
    t = copy.deepcopy(base[i % len(base)])
    t["id"] = 60000 + i
    end = t0 + timedelta(hours=6 + i * 0.9)
    pub = t0 - timedelta(hours=(i * 0.35) % 96)
    t["end"] = end.strftime("%Y-%m-%dT%H:%M"); t["pub"] = pub.strftime("%Y-%m-%dT%H:%M")
    out.append(t)
d["tenders"] = out; d["meta"]["open"] = n
json.dump(d, open(dst, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print(n, "tenders ->", dst)
