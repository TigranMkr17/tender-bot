"""Draws the site's mark and cuts its icon files into docs/icons/:

    python tools/mark.py

The mark is the letter «Մ» as a paper ribbon. The band runs down, round and up; at the top of the right stem it
folds over to the right, and the back of the band, the letter's arm, is amber and ends in a swallowtail, like a
page marker. It sits on the header's press blue, with the header's dot screen growing toward the lower right.

Everything is drawn in 1024 units. Standard library only; the PNG files need rsvg-convert (librsvg) on the path.
"""
import math
import os
import shutil
import subprocess
import sys
import tempfile

S = 1024
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'docs', 'icons')


def n(v):
    return ('%.1f' % v).rstrip('0').rstrip('.')


def dot_screen(color='#fff', opacity='.2', start=0.6, biggest=17, pitch=46):
    """A print screen at 45 degrees: dots that grow toward the lower right corner and stop short of the middle."""
    out, k = [], pitch / math.sqrt(2)
    for i in range(-40, 80):
        for j in range(-40, 80):
            x, y = (i - j) * k + S / 2, (i + j) * k + S / 2 - 400
            if not (-biggest <= x <= S + biggest and -biggest <= y <= S + biggest):
                continue
            tone = max(0.0, min(1.0, ((x + y) / (2 * S) - start) / (1 - start)))
            r = biggest * tone ** 0.85
            if r >= 1.6:
                out.append(f'<circle cx="{n(x)}" cy="{n(y)}" r="{n(r)}"/>')
    return f'<g fill="{color}" fill-opacity="{opacity}">' + ''.join(out) + '</g>'


def field(dots=True):
    """Press blue, lighter at the top left, as in the header."""
    return ('<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2444AD"/>'
            '<stop offset=".52" stop-color="#1B338A"/><stop offset="1" stop-color="#10205A"/></linearGradient>'
            '<radialGradient id="gl" cx=".2" cy=".06" r=".95"><stop offset="0" stop-color="#fff" stop-opacity=".18"/>'
            '<stop offset=".6" stop-color="#fff" stop-opacity="0"/></radialGradient></defs>'
            f'<rect width="{S}" height="{S}" fill="url(#bg)"/><rect width="{S}" height="{S}" fill="url(#gl)"/>'
            + (dot_screen() if dots else ''))


def ribbon(lift=True, cx=478, top=228, width=460, height=572, band=143, arm=152, notch=50):
    """The letter. `cx` is the middle of the U, set left of the square's middle because the arm reaches out
    to the right; with these numbers the mass of the letter sits about 13 units from the centre of the square."""
    xl, xr = cx - width / 2, cx + width / 2
    big, small = width / 2, width / 2 - band          # the bowl's outer and inner radius
    bowl = top + height - big
    inner = xr - band                                 # the right stem's inner edge
    fold = top + band                                 # where the band turns over
    tip = xr + arm
    front = (f'M{n(xl)} {n(top)}H{n(xl + band)}V{n(bowl)}A{n(small)} {n(small)} 0 0 0 {n(inner)} {n(bowl)}'
             f'V{n(fold)}H{n(xr)}V{n(bowl)}A{n(big)} {n(big)} 0 0 1 {n(xl)} {n(bowl)}Z')
    # the back of the band: the crease runs from the stem's inner edge up to its outer corner
    back = f'M{n(xr)} {n(top)}H{n(tip)}L{n(tip - notch)} {n(top + band / 2)}L{n(tip)} {n(fold)}H{n(inner)}Z'
    mx, my = (inner + xr) / 2, top + band / 2         # the middle of the crease
    d = 0.56 * band / math.sqrt(2)                    # how far the shade along the crease reaches
    defs = ('<defs>'
            f'<linearGradient id="wh" gradientUnits="userSpaceOnUse" x1="0" y1="{n(top)}" x2="0" y2="{n(top + height)}">'
            '<stop offset="0" stop-color="#fff"/><stop offset="1" stop-color="#E4E9FA"/></linearGradient>'
            f'<linearGradient id="am" gradientUnits="userSpaceOnUse" x1="0" y1="{n(top)}" x2="0" y2="{n(fold)}">'
            '<stop offset="0" stop-color="#F8CC60"/><stop offset="1" stop-color="#EEB33B"/></linearGradient>'
            f'<linearGradient id="cr" gradientUnits="userSpaceOnUse" x1="{n(mx)}" y1="{n(my)}" x2="{n(mx + d)}" y2="{n(my + d)}">'
            '<stop offset="0" stop-color="#B26F12" stop-opacity=".5"/><stop offset="1" stop-color="#B26F12" stop-opacity="0"/></linearGradient>'
            f'<linearGradient id="un" gradientUnits="userSpaceOnUse" x1="0" y1="{n(fold)}" x2="0" y2="{n(fold + 30)}">'
            '<stop offset="0" stop-color="#0B1A55" stop-opacity=".34"/><stop offset="1" stop-color="#0B1A55" stop-opacity="0"/></linearGradient>'
            + ('<filter id="sh" x="-20%" y="-20%" width="140%" height="150%">'
               '<feDropShadow dx="0" dy="14" stdDeviation="16" flood-color="#081440" flood-opacity=".5"/></filter>' if lift else '')
            + '</defs>')
    body = (f'<path d="{front}" fill="url(#wh)"/>'
            f'<rect x="{n(inner)}" y="{n(fold)}" width="{n(band)}" height="30" fill="url(#un)"/>'    # the flap's shadow on the stem
            f'<path d="{back}" fill="url(#am)"/><path d="{back}" fill="url(#cr)"/>')
    return defs + (f'<g filter="url(#sh)">{body}</g>' if lift else body)


def about_centre(inner, k):
    return f'<g transform="translate(512 512) scale({k}) translate(-512 -512)">{inner}</g>'


def cornered(inner, r):
    return f'<defs><clipPath id="rr"><rect width="{S}" height="{S}" rx="{r}"/></clipPath></defs><g clip-path="url(#rr)">{inner}</g>'


def svg(inner):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {S} {S}" width="{S}" height="{S}">{inner}</svg>'


def full():        # a phone's Home Screen: square, to the edges; the phone cuts its own corners
    return svg(field() + ribbon())


def with_corners():  # the same with its own corners, for places that show the file as it is
    return svg(cornered(field() + ribbon(), 230))


def maskable():    # Android cuts a circle or a squircle out of the middle, so the letter keeps clear of the rim
    return svg(field() + about_centre(ribbon(), 0.8))


def tab():         # browser tabs: a larger letter and nothing finer than the fold
    return svg(cornered(field(dots=False) + about_centre(ribbon(lift=False), 1.14), 236))


FILES = [('apple-touch-icon.png', full, 180), ('icon-192.png', with_corners, 192), ('icon-512.png', with_corners, 512),
         ('icon-maskable-512.png', maskable, 512), ('favicon-32.png', tab, 32)]

if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, 'icon.svg'), 'w', encoding='utf-8') as f:
        f.write(tab())
    if not shutil.which('rsvg-convert'):
        sys.exit('icon.svg written; rsvg-convert is needed for the PNG files')
    with tempfile.TemporaryDirectory() as tmp:
        for name, draw, size in FILES:
            src = os.path.join(tmp, name + '.svg')
            with open(src, 'w', encoding='utf-8') as f:
                f.write(draw())
            subprocess.run(['rsvg-convert', '-w', str(size), '-h', str(size), src, '-o', os.path.join(OUT, name)], check=True)
            print(name, size, os.path.getsize(os.path.join(OUT, name)), 'bytes')
