"""Read a .docx with the standard library: paragraphs and tables in document order.

Invitations of the register keep their list of lots in a table inside a text box, so the
reader looks inside text boxes too, and skips the duplicate copy Word stores as a fallback."""
import re
import zipfile
import xml.etree.ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
MC = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"
_SKIP = {MC + "Fallback"}


def _clean(text: str) -> str:
    return re.sub(r"[ \t \r\n]+", " ", text).strip()


def _text(el, stop=frozenset()) -> str:
    """Text under el, in order, not entering Fallback copies or the tags in stop."""
    out, stack = [], [el]
    while stack:
        node = stack.pop()
        if node is not el and (node.tag in _SKIP or node.tag in stop):
            continue
        if node.tag == W + "t":
            out.append(node.text or "")
        elif node.tag in (W + "tab", W + "br", W + "cr"):
            out.append(" ")
        elif node.tag == W + "p" and node is not el:
            out.append(" ")
        stack.extend(reversed(list(node)))
    return "".join(out)


def _table(tbl):
    return [[_clean(_text(tc)) for tc in tr.findall(W + "tc")] for tr in tbl.findall(W + "tr")]


def _inner(p):
    """Tables and text boxes found inside a paragraph (outermost ones, Fallback copies left out)."""
    found, stack = [], list(reversed(list(p)))
    while stack:
        node = stack.pop()
        if node.tag in _SKIP:
            continue
        if node.tag in (W + "txbxContent", W + "tbl"):
            found.append(node)
            continue
        stack.extend(reversed(list(node)))
    return found


def _walk(container, out):
    for el in container:
        if el.tag == W + "p":
            t = _clean(_text(el, stop=frozenset({W + "txbxContent", W + "tbl"})))
            if t:
                out.append(("P", t))
            for node in _inner(el):
                if node.tag == W + "tbl":
                    out.append(("T", _table(node)))
                else:
                    _walk(node, out)
        elif el.tag == W + "tbl":
            out.append(("T", _table(el)))
        elif el.tag == W + "sdt":
            content = el.find(W + "sdtContent")
            if content is not None:
                _walk(content, out)


def blocks(path_or_file):
    """[('P', text) | ('T', [[cell, ...], ...])] for the blocks of the document, in order."""
    root = ET.fromstring(zipfile.ZipFile(path_or_file).read("word/document.xml"))
    out = []
    _walk(root.find(W + "body"), out)
    return out
