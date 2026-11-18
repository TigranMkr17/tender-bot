"""Looks at pages the way the bot's reader does, from wherever this runs:

    URLS="https://… https://…" python tools/look.py

For each address it prints the status, the title, the forms with their fields, the links and the first rows of each
table. The registers answer GitHub's runners but not every network, so the Look workflow runs this there; it is how
a new source is studied before a reader is written for it. FIND limits the links to those that contain a text;
POST sends form data (a=b&c=d) instead of asking for the page; GREP prints the lines of the page's source that
match a pattern, and the scripts it loads.
"""
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title, self.forms, self.links, self.tables = "", [], [], []
        self._in, self._text, self._href, self._row, self._cell = [], [], None, None, None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "title":
            self._in.append("title")
        elif tag == "form":
            self.forms.append({"method": (a.get("method") or "get").lower(), "action": a.get("action") or "", "fields": []})
        elif tag in ("input", "select", "textarea") and self.forms and a.get("name"):
            self.forms[-1]["fields"].append(f'{a["name"]}' + (f'={a["value"][:30]}' if a.get("value") else "")
                                            + (f' [{a.get("type")}]' if a.get("type") else f" [{tag}]"))
        elif tag == "option" and self.forms and self.forms[-1]["fields"]:
            f = self.forms[-1]["fields"]
            if f[-1].count("|") < 8:
                f[-1] += " |" + (a.get("value") or "")[:24]
        elif tag == "a" and a.get("href"):
            self._href, self._text = a["href"], []
        elif tag == "table":
            self.tables.append([])
        elif tag == "tr" and self.tables:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag):
        if tag == "title" and self._in:
            self._in.pop()
        elif tag == "a" and self._href:
            self.links.append((" ".join("".join(self._text).split())[:70], self._href))
            self._href = None
        elif tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split())[:60])
            self._cell = None
        elif tag == "tr" and self._row is not None and self.tables:
            if self._row:
                self.tables[-1].append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._in:
            self.title += data
        if self._href is not None:
            self._text.append(data)
        if self._cell is not None:
            self._cell.append(data)


OPENER = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())   # cookies carry from one address to the next


def fetch(url: str, post: str = ""):
    headers = {"User-Agent": AGENT, "Accept-Language": "hy,en;q=0.8"}
    if post.startswith(("{", "[")):                          # a JSON body, for pages that load their data that way
        headers.update({"Content-Type": "application/json;charset=UTF-8", "Accept": "application/json, text/plain, */*"})
    req = urllib.request.Request(url, data=post.encode() if post else None, headers=headers)
    try:
        with OPENER.open(req, timeout=45) as r:
            return r.status, r.geturl(), r.headers.get("Content-Type", ""), r.read(3_000_000)
    except urllib.error.HTTPError as e:
        return e.code, url, e.headers.get("Content-Type", ""), e.read(200_000)
    except Exception as e:                                   # a look, not a reader: say what happened and go on
        return 0, url, "", repr(e).encode()


def look(url: str, find: str = "", post: str = "", grep: str = "") -> None:
    status, final, kind, body = fetch(url, post)
    print(f"\n=== {url}\n    {status} {kind} {len(body)} bytes" + (f" -> {final}" if final != url else ""))
    if "html" not in kind and "xml" not in kind and not grep:
        print("    " + body[:int(os.environ.get("SHOW", "1500"))].decode("utf-8", "replace").replace("\n", "\n    "))
        return
    m = re.search(rb"charset=[\"']?([\w-]+)", body[:2000])
    text = body.decode(m.group(1).decode() if m else "utf-8", "replace")
    if grep:
        for src in re.findall(r"<script[^>]+src=[\"']([^\"']+)", text)[:90]:
            print(f"    script {urllib.parse.urljoin(final, src)}")
        lines = (line.strip() for line in re.split(r"[\r\n]+|(?<=;)(?=[a-zA-Z$_.]{2,30}[=(])", text) if line)
        hits = [line for line in lines if line and re.search(grep, line)]
        for line in hits[:260]:
            i = re.search(grep, line).start()
            print(f"    > {line[max(0, i - 160):i + 400]}")
        if len(hits) > 260:
            print(f"    … and {len(hits) - 260} more lines")
        if "html" not in kind and "xml" not in kind:
            return
    page = Page()
    page.feed(text)
    print(f"    title: {' '.join(page.title.split())[:120]}")
    for f in page.forms[:12]:
        print(f"    form {f['method']} {f['action'][:110]}")
        for field in f["fields"][:40]:
            print(f"        {field[:150]}")
    seen, shown = set(), 0
    for label, href in page.links:
        href = urllib.parse.urljoin(final, href)
        if href in seen or (find and find.lower() not in (label + " " + href).lower()):
            continue
        seen.add(href)
        if shown < 90:
            print(f"    link {label or '-'} -> {href[:170]}")
        shown += 1
    if shown > 90:
        print(f"    … and {shown - 90} more links")
    for i, table in enumerate(page.tables[:8]):
        print(f"    table {i + 1}: {len(table)} rows")
        for row in table[:7]:
            print("        " + " | ".join(row[:10]))


if __name__ == "__main__":
    addresses = (os.environ.get("URLS") or " ".join(sys.argv[1:])).split()
    if not addresses:
        sys.exit(__doc__)
    for address in addresses[:25]:
        address, _, body = address.partition("@@")       # address@@form-data posts to that one address only
        look(address, os.environ.get("FIND", ""), body or os.environ.get("POST", ""), os.environ.get("GREP", ""))
