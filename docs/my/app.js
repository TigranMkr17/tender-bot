/* Մեր դաշտը — what the public contracts register says about one group of companies:
   the open tenders that fit them, their own contracts, the suppliers they meet and the buyers they could have.
   Nothing here is private: every figure comes from armeps.am. The page only knows which companies to look for,
   and that comes from its own address (?c=tax numbers &w=lines), never from this file. */
(() => {
'use strict';

/* ---------- small helpers ---------- */
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const HOUR = 36e5, DAY = 864e5, TZ = 4 * HOUR;             // Yerevan is UTC+4 all year
const p2 = n => String(n).padStart(2, '0');
const toDate = s => (s ? new Date(s.slice(0, 16) + ':00+04:00') : null);
const dOnly = s => new Date(s.slice(0, 10) + 'T12:00:00+04:00');
const parts = d => { const x = new Date(d.getTime() + TZ); return {y: x.getUTCFullYear(), m: x.getUTCMonth(), d: x.getUTCDate(), wd: x.getUTCDay(), hh: x.getUTCHours(), mm: x.getUTCMinutes()}; };
const dayNo = d => Math.floor((d.getTime() + TZ) / DAY);
const iso = d => { const p = parts(d); return `${p.y}-${p2(p.m + 1)}-${p2(p.d)}`; };

const WD = ['Կիրակի', 'Երկուշաբթի', 'Երեքշաբթի', 'Չորեքշաբթի', 'Հինգշաբթի', 'Ուրբաթ', 'Շաբաթ'];
const MON = ['հունվարի', 'փետրվարի', 'մարտի', 'ապրիլի', 'մայիսի', 'հունիսի', 'հուլիսի', 'օգոստոսի', 'սեպտեմբերի', 'հոկտեմբերի', 'նոյեմբերի', 'դեկտեմբերի'];
const MON0 = ['Հունվար', 'Փետրվար', 'Մարտ', 'Ապրիլ', 'Մայիս', 'Հունիս', 'Հուլիս', 'Օգոստոս', 'Սեպտեմբեր', 'Հոկտեմբեր', 'Նոյեմբեր', 'Դեկտեմբեր'];
const MON3 = ['ՀՆՎ', 'ՓՏՐ', 'ՄՐՏ', 'ԱՊՐ', 'ՄՅՍ', 'ՀՆՍ', 'ՀԼՍ', 'ՕԳՍ', 'ՍԵՊ', 'ՀՈԿ', 'ՆՈՅ', 'ԴԵԿ'];
const fDay = d => { const p = parts(d); return `${p.d} ${MON[p.m]}`; };
const fDayY = d => fDay(d) + (parts(d).y !== parts(new Date(now())).y ? ` ${parts(d).y} թ.` : '');
const fTime = d => { const p = parts(d); return `${p2(p.hh)}:${p2(p.mm)}`; };

/* numbers the way they are written in Armenian: 11 520 000 · 11,5 մլն · 12% */
const NB = '\u00a0';
const group = n => String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, NB);
function short(n) {
  const a = Math.abs(n), f = (v, unit) => String(+v.toFixed(Math.abs(v) < 10 ? 2 : Math.abs(v) < 100 ? 1 : 0)).replace('.', ',') + NB + unit;
  return a >= 999.5e6 ? f(n / 1e9, 'մլրդ') : a >= 999.5e3 ? f(n / 1e6, 'մլն') : a >= 1e4 ? f(n / 1e3, 'հազ.') : group(n);
}
const money = n => (n ? short(n) + NB + 'դրամ' : '—');
const plural = (n, word) => `${group(n)}${NB}${word}`;
const pct = x => `${Math.round(x * 100)}%`;
const share = (part, whole) => { const x = whole ? part / whole : 0; return x > 0 && x < .005 ? '1%-ից պակաս' : pct(x); };
const ofLine = (part, whole) => { const x = whole ? part / whole : 0; return x > 0 && x < .005 ? 'ուղղության 1%-ից պակաս' : `ուղղության ${pct(x)}-ը`; };
const median = a => { if (!a.length) return null; const s = [...a].sort((x, y) => x - y), m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
const ic = (name, cls = '') => `<svg class="ic${cls ? ' ' + cls : ''}" aria-hidden="true"><use href="#i-${name}"/></svg>`;
const CALM = matchMedia('(prefers-reduced-motion: reduce)').matches;
const KIND = {g: 'ապրանք', s: 'ծառայություն', w: 'աշխատանք'};
const ARMEPS = 'https://eauction.armeps.am';
const REGISTER = 'https://www.armeps.am/ppcm/public/contracts';
const MAX_CO = 3;                                           // three checked colours, three companies

/* text as it is compared: lower case, Latin look-alikes typed inside Armenian words put right, «և» spelled out */
const LOOK = {a: 'ա', h: 'հ', o: 'օ', u: 'ս', p: 'ր', n: 'ո', g: 'ց', q: 'զ'};
function norm(s) {
  return ' ' + String(s || '').toLowerCase()
    .replace(/[a-z](?=[\u0561-\u0587])/g, ch => LOOK[ch] || ch)
    .replace(/([\u0561-\u0587])([a-z])/g, (m, a, ch) => a + (LOOK[ch] || ch))
    .replace(/\u0587/g, 'եվ')
    .replace(/[^0-9a-z\u0561-\u0586]+/g, ' ').trim() + ' ';
}
const buyerKey = name => norm(name).replace(/^ հհ /, ' ');
const hit = (n, key) => key.split(' ').every(w => n.includes(' ' + w));
const title = text => {
  const s = String(text || '').trim();
  if (!s) return 'Առարկան նշված չէ';
  const first = /[a-z]/i.test(s[0]) && /[\u0531-\u0587]/.test(s[1] || '') ? LOOK[s[0].toLowerCase()] || s[0] : s[0];
  return first.toUpperCase() + s.slice(1);
};
const shortName = name => String(name || '').replace(/[«»"“”]/g, '').replace(/\s+(ՍՊԸ|ՓԲԸ|ԲԲԸ|ՀՈԱԿ|ՊՈԱԿ)\s*$/u, '').trim();

/* ---------- the seal ---------- */
/* A guilloche seal drawn from a number: the tax number sets the lobes, the weave and the turn of every ring,
   so each company has its own and it never changes. Closed paths in a -50..50 box, outermost first. */
function sealPaths(number, detail = 1) {
  const d = String(number || '').replace(/\D/g, '').padStart(8, '0').slice(-8).split('').map(Number);
  const TAU = Math.PI * 2, steps = detail > 1 ? 540 : 360;
  const ring = (r0, a, n, strands, turn, wobble = 0) => {
    const out = [];
    for (let j = 0; j < strands; j++) {
      const ph = turn + TAU * j / strands;
      let p = '';
      for (let i = 0; i < steps; i++) {
        const t = TAU * i / steps;
        const r = r0 + a * Math.cos(n * t + ph) + wobble * Math.cos(2 * n * t - ph);
        p += (i ? 'L' : 'M') + (r * Math.cos(t)).toFixed(2) + ' ' + (r * Math.sin(t)).toFixed(2);
      }
      out.push(p + 'Z');
    }
    return out;
  };
  const n1 = 11 + (d[0] * 3 + d[1] + d[7]) % 10;            // 11..20 lobes on the rim
  const n2 = 5 + (d[2] + d[3] * 2 + d[6]) % 6;              // 5..10 petals in the lace
  const n3 = 3 + (d[4] + d[5]) % 5;                         // 3..7 in the heart
  const turn = TAU * (d[6] * 10 + d[7]) / 100;
  return [
    ...ring(42.6, 3.6, n1, detail > 1 ? 3 : 2, turn),
    ...ring(27.5, 8.6, n2, detail > 1 ? 6 : detail > 0 ? 4 : 3, -turn, 1.6 + d[1] % 3 * .5),
    ...ring(10.5, 4.4, n3, detail > 0 ? 3 : 2, turn * 2, .8)
  ];
}
function sealSVG(number, {detail = 1, size = 64, stroke = 1, cls = '', style = ''} = {}) {
  return `<svg class="seal ${cls}" viewBox="-50 -50 100 100" width="${size}" height="${size}" aria-hidden="true"${style ? ` style="${style}"` : ''}>` +
    `<path d="M48.6 0A48.6 48.6 0 1 1-48.6 0A48.6 48.6 0 1 1 48.6 0Z" fill="none" stroke="currentColor" stroke-width="${stroke * .8}" pathLength="1" style="--i:0"/>` +
    sealPaths(number, detail).map((p, i) => `<path d="${p}" fill="none" stroke="currentColor" stroke-width="${stroke}" stroke-linejoin="round" pathLength="1" style="--i:${i + 1}"/>`).join('') +
    `<circle r="1.7" fill="currentColor"/></svg>`;
}

/* ---------- state ---------- */
const TABS = ['today', 'us', 'rivals', 'buyers'];
const S = {tab: 'today', seg: {today: 'open', rivals: 'met', buyers: 'ours'}, line: -1, scroll: {}, loaded: false, frozen: null,
  lists: new Map(), chartMode: 'bars', pick: -1, stack: [], cache: {}};
const now = () => S.frozen ?? Date.now();
const store = {
  get(k) { try { return localStorage.getItem('md.' + k); } catch { return null; } },
  set(k, v) { try { localStorage.setItem('md.' + k, v); } catch { /* private mode or full: it lives for this visit only */ } }
};
const CFG = {tins: [], lines: null};                        // lines: [{name, keys: [stem, …]}], null until known
let D = null;                                               // everything read from the register
let G = [];                                                 // the companies: [{tin, s: supplier or null, name}]
let OPEN = [];                                              // open tenders, each with its lines

/* ---------- the address carries the choice ---------- */
const b64e = s => btoa(String.fromCharCode(...new TextEncoder().encode(s))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
const b64d = s => new TextDecoder('utf-8', {fatal: true}).decode(Uint8Array.from(atob(s.replace(/[- ]/g, '+').replace(/_/g, '/')), c => c.charCodeAt(0)));
const packLines = lines => lines.map(l => l.name + ':' + l.keys.join('|')).join(';');
function unpackLines(text) {
  const out = [];
  for (const part of String(text || '').split(';')) {
    const [name, keys] = part.split(':');
    const ks = (keys ?? name).split('|').map(k => norm(k).trim()).filter(Boolean);
    if (name && name.trim() && ks.length) out.push({name: name.trim().slice(0, 40), keys: ks.slice(0, 12)});
  }
  return out.slice(0, 16);
}
/* A link brings a choice in once. After that the choice lives on the device, so what is changed in the settings
   is still there when the same old link, saved on the Home Screen, is opened again. */
const seeds = () => { try { return JSON.parse(store.get('seeds') || '[]'); } catch { return []; } };
const addSeed = key => { const all = seeds().filter(k => k !== key); all.push(key); store.set('seeds', JSON.stringify(all.slice(-24))); };
function readConfig() {
  const q = new URLSearchParams(location.search);
  let c = q.get('c'), w = q.get('w');
  const key = c == null ? null : c + '|' + (w || '');
  if (key == null || seeds().includes(key)) { if (store.get('c') != null) { c = store.get('c'); w = store.get('w'); } }
  else addSeed(key);
  CFG.tins = [...new Set(String(c || '').split(/[.,\s]+/).filter(t => /^\d{8}$/.test(t)))].slice(0, MAX_CO);
  let lines = null;
  if (w) {                                                  // packed by "Copy link", or typed by hand as Name:stem|stem;Name:stem
    try { lines = unpackLines(/^[A-Za-z0-9_+/= -]+$/.test(w) ? b64d(w) : w); } catch { lines = unpackLines(w); }
  }
  CFG.lines = lines && lines.length ? lines : null;
  const at = q.get('at');
  if (at && /^\d{4}-\d\d-\d\dT\d\d:\d\d/.test(at)) S.frozen = toDate(at).getTime();     // a fixed "now", for checking the page
  const tab = q.get('tab') || store.get('tab');
  if (TABS.includes(tab)) S.tab = tab;
}
function myLink() {
  const q = new URLSearchParams(location.search), keep = new URLSearchParams();
  keep.set('c', CFG.tins.join('.'));
  if (CFG.lines) keep.set('w', b64e(packLines(CFG.lines)));
  if (q.get('at')) keep.set('at', q.get('at'));
  return location.origin + location.pathname + '?' + keep.toString();
}
function saveConfig() {
  const c = CFG.tins.join('.'), w = CFG.lines ? b64e(packLines(CFG.lines)) : '';
  store.set('c', c);
  store.set('w', w);
  addSeed(c + '|' + w);
  syncAddress();
}
/* The address always spells the current choice, so "Add to Home Screen" and "Copy link" agree. A sheet sits on its
   own history step, so the address is written once the sheets are closed. */
function syncAddress() {
  if (S.stack.length) return;
  try { history.replaceState(null, '', myLink()); } catch { /* a file: page cannot rewrite its address */ }
}

/* ---------- reading ---------- */
async function getJSON(url) {
  const r = await fetch(url, {cache: 'no-cache'});
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return r.json();
}
function progress(p) {
  const el = $('#loadline');
  el.style.setProperty('--p', p.toFixed(3));
  el.setAttribute('aria-valuenow', Math.round(p * 100));
}
async function load() {
  progress(.04);
  const meta = await getJSON('../data/k/meta.json');
  const names = meta.months.map(m => m[0]);
  let done = 0;
  const step = x => { done++; progress(.06 + .94 * done / (names.length + 2)); return x; };
  const soft = url => getJSON(url).catch(() => null).then(step);   // the tender list may be missing; the register may not
  const [tenders, lots, ...months] = await Promise.all([soft('../data/tenders.json'), soft('../data/lots.json'),
    ...names.map(m => getJSON(`../data/k/${m}.json`).then(step))]);
  D = ingest(meta, months);
  D.tenders = tenders?.tenders || [];
  D.tmeta = tenders?.meta || {};
  D.lots = lots?.t || {};
}

/* One table of suppliers, buyers and tenders for the whole year. A supplier is one tax number however many
   times it registered; a sole proprietor has no tax number here and stays a separate, unnamed line. */
function ingest(meta, months) {
  const sup = new Map(), buy = new Map(), ten = new Map(), bySid = new Map(), C = [];
  for (const mo of months) {
    const B = mo.B.map(([tin, name]) => {
      const key = tin || 'n:' + norm(name);
      let b = buy.get(key);
      if (!b) buy.set(key, b = {key, tin, name});
      b.name = name;                                         // months run oldest first: the latest spelling stays
      return b;
    });
    const Sx = mo.S.map(([sid, name, tin, person]) => {
      const key = tin || (person ? 'p:' + sid : 'n:' + norm(name));
      let s = sup.get(key);
      if (!s) sup.set(key, s = {key, tin, name, person: !!person, sids: new Set(), n: 0, v: 0, g: -1});
      if (sid) { s.sids.add(sid); bySid.set(sid, s); }
      return s;
    });
    const T = mo.T.map(([code, list]) => {
      let t = ten.get(code);
      if (!t) ten.set(code, t = {code, parts: new Set(), cs: []});
      for (const sid of list) t.parts.add(sid);
      return t;
    });
    for (const [day, b, s, v, est, f, kind, subj, t] of mo.R) {
      const odd = v > 5e11;                                  // a typing slip in the register: kept, never summed
      const c = {i: 0, d: `${mo.m}-${p2(day)}`, m: mo.m, b: B[b], s: Sx[s], v: odd ? 0 : v, est: odd || est > 5e11 ? 0 : est,
        f: mo.F[f], k: kind, subj, t: t >= 0 ? T[t] : null, n: norm(subj), L: 0};
      C.push(c);
      c.s.n++; c.s.v += c.v;
      if (c.t) c.t.cs.push(c);
    }
  }
  C.sort((x, y) => (x.d < y.d ? 1 : x.d > y.d ? -1 : 0));        // newest first, everywhere
  C.forEach((c, i) => { c.i = i; });
  const byName = new Map();
  for (const b of buy.values()) byName.set(buyerKey(b.name), b);
  return {meta, C, sup, buy, ten, bySid, byName, months: meta.months.map(m => m[0])};
}

/* Which lines a text belongs to, as bits: line 0 is bit 1, line 1 is bit 2 … */
function linesOf(n) {
  let mask = 0;
  CFG.lines.forEach((l, i) => { if (l.keys.some(k => hit(n, k))) mask |= 1 << i; });
  return mask;
}
const inLine = mask => (S.line < 0 ? mask !== 0 : (mask & (1 << S.line)) !== 0);
const lineNames = mask => CFG.lines.filter((l, i) => mask & (1 << i)).map(l => l.name);
const off = c => (c.est > 0 && c.v > 0 && c.est >= c.v ? 1 - c.v / c.est : null);

/* Words a company sells, guessed from its own contracts, for a visitor who came without a list. */
const STOP = new Set(['ձեռքբերում', 'ձեռքբերման', 'ծառայություն', 'ծառայություններ', 'ծառայության', 'ծառայությունների', 'ապրանք', 'ապրանքներ', 'ապրանքների',
  'մատուցում', 'մատուցման', 'աշխատանք', 'աշխատանքներ', 'աշխատանքների', 'կարիքների', 'համար', 'նպատակով', 'կազմակերպում', 'կազմակերպման', 'իրականացում',
  'իրականացման', 'հիմնադրամ', 'հիմնադրամի', 'պարագաներ', 'պարագաների', 'նյութեր', 'նյութերի', 'տարբեր', 'տեսակի', 'անհրաժեշտ', 'փաթեթ', 'երևանի', 'հայաստանի']);
function guessLines() {
  const seen = new Map();
  for (const c of D.C) {
    if (c.s.g < 0) continue;
    for (const w of new Set(c.n.trim().split(' '))) {
      if (w.length < 5 || STOP.has(w) || /\d/.test(w)) continue;
      const stem = w.slice(0, Math.max(5, w.length - 2));
      const e = seen.get(stem) || {stem, n: 0, word: w};
      e.n++; if (w.length < e.word.length) e.word = w;
      seen.set(stem, e);
    }
  }
  return [...seen.values()].sort((a, b) => b.n - a.n).slice(0, 8)
    .map(e => ({name: e.word.charAt(0).toUpperCase() + e.word.slice(1), keys: [e.stem]}));
}

/* Tie the choice to the data: who the companies are, which contracts and open tenders are in their lines. */
function apply() {
  for (const s of D.sup.values()) s.g = -1;
  G = CFG.tins.map((tin, i) => { const s = D.sup.get(tin) || null; if (s) s.g = i; return {tin, s, name: s ? s.name : `ՀՎՀՀ ${tin}`}; });
  if (!CFG.lines) CFG.lines = guessLines();
  for (const c of D.C) c.L = linesOf(c.n);
  const t = now();
  OPEN = D.tenders.filter(x => x.status === 'open' && toDate(x.end) && toDate(x.end).getTime() > t).map(x => {
    const lot = D.lots[x.id] || {};
    return {...x, L: linesOf(norm([x.title, x.subject, lot.ln].join(' '))), b: x.buyer ? D.byName.get(buyerKey(x.buyer)) || null : null, lot};
  }).sort((a, b) => (a.end < b.end ? -1 : a.end > b.end ? 1 : a.id - b.id));
  S.cache = {};
  if (S.line >= CFG.lines.length) S.line = -1;
}

/* ---------- what the register says, worked out once per choice ---------- */
const memo = (key, fn) => (key in S.cache ? S.cache[key] : (S.cache[key] = fn()));
const ours = () => memo('ours', () => D.C.filter(c => c.s.g >= 0));
const lined = () => memo('lined', () => D.C.filter(c => c.L && c.v));
const ourBuyers = () => memo('ourBuyers', () => new Set(ours().map(c => c.b)));
const sidsOf = g => (g.s ? g.s.sids : new Set());
const tookPart = (t, sids) => { for (const sid of sids) if (t.parts.has(sid)) return true; return false; };

/* Tenders a company took part in: with a contract of its own, or with every contract going elsewhere. */
function entries() {
  return memo('entries', () => {
    const out = [];
    for (const t of D.ten.values()) {
      G.forEach((g, gi) => {
        if (!g.s || !tookPart(t, g.s.sids)) return;
        const won = t.cs.filter(c => c.s === g.s);
        out.push({t, gi, won, lost: !won.length, d: t.cs.reduce((m, c) => (c.d > m ? c.d : m), '')});
      });
    }
    return out.sort((a, b) => (a.d < b.d ? 1 : -1));
  });
}
/* Suppliers met in those tenders. Only those the register names somewhere can be counted by name. */
function met() {
  return memo('met', () => {
    const map = new Map(), seenT = new Set();
    let unknown = 0;
    for (const e of entries()) {
      if (seenT.has(e.t)) continue;
      seenT.add(e.t);
      const here = new Set();
      for (const sid of e.t.parts) {
        const s = D.bySid.get(sid);
        if (!s) { unknown++; continue; }
        if (s.g >= 0 || here.has(s)) continue;
        here.add(s);
        const key = s.person ? 'person' : s.key;
        const r = map.get(key) || {key, s: s.person ? null : s, n: 0, won: 0, people: new Set()};
        r.n++;
        if (s.person) r.people.add(s);
        if (e.t.cs.some(c => c.s === s)) r.won++;
        map.set(key, r);
      }
    }
    const people = map.get('person') || null;
    map.delete('person');
    return {rows: [...map.values()].sort((a, b) => b.n - a.n || b.won - a.won), people, unknown, tenders: seenT.size};
  });
}
/* Everyone with a contract in the chosen lines, largest first; sole proprietors stand as one unnamed row. */
function ranking() {
  return memo('rank' + S.line, () => {
    const map = new Map();
    let total = 0;
    for (const c of lined()) {
      if (!inLine(c.L)) continue;
      const key = c.s.person ? 'person' : c.s.key;
      const r = map.get(key) || {key, s: c.s.person ? null : c.s, v: 0, n: 0, people: new Set()};
      r.v += c.v; r.n++; total += c.v;
      if (c.s.person) r.people.add(c.s);
      map.set(key, r);
    }
    const people = map.get('person') || null;
    map.delete('person');
    return {rows: [...map.values()].sort((a, b) => b.v - a.v), people, total};
  });
}
function buyersIn() {
  return memo('buy' + S.line, () => {
    const map = new Map();
    for (const c of lined()) {
      if (!inLine(c.L)) continue;
      const r = map.get(c.b) || {b: c.b, v: 0, n: 0, ourV: 0, sup: new Map()};
      r.v += c.v; r.n++;
      if (c.s.g >= 0) r.ourV += c.v;
      else if (!c.s.person) r.sup.set(c.s, (r.sup.get(c.s) || 0) + c.v);
      map.set(c.b, r);
    }
    return [...map.values()].sort((a, b) => b.v - a.v);
  });
}
function ourBuyerRows() {
  return memo('ourBuyerRows', () => {
    const map = new Map();
    for (const c of ours()) {
      const r = map.get(c.b) || {b: c.b, v: 0, n: 0, last: '', inV: 0, allV: 0};
      r.v += c.v; r.n++; if (c.d > r.last) r.last = c.d;
      map.set(c.b, r);
    }
    for (const c of lined()) { const r = map.get(c.b); if (r) { r.allV += c.v; if (c.s.g >= 0) r.inV += c.v; } }
    return [...map.values()].sort((a, b) => b.v - a.v);
  });
}
/* What was signed in our lines a year ago in the days now ahead: the same buyers may buy again. */
function expected() {
  return memo('exp', () => {
    const t = new Date(now()), a = iso(new Date(t.getTime() - 365 * DAY)), b = iso(new Date(t.getTime() - (365 - 60) * DAY));
    const map = new Map();
    for (const c of lined()) {
      if (c.d < a || c.d > b) continue;
      const key = c.b.key + '|' + c.d + '|' + (c.t ? c.t.code : c.L);
      const r = map.get(key) || {b: c.b, d: c.d, cs: [], v: 0, L: 0};
      r.cs.push(c); r.v += c.v; r.L |= c.L;
      map.set(key, r);
    }
    return [...map.values()].sort((x, y) => (x.d < y.d ? -1 : x.d > y.d ? 1 : y.v - x.v));
  });
}
const recent = () => memo('recent', () => { const from = iso(new Date(now() - 30 * DAY)); return lined().filter(c => c.d >= from); });
/* How far below the estimate contracts like this are usually signed: this buyer first, the whole line otherwise. */
function usualOff(buyer, mask) {
  const pick = list => list.map(off).filter(x => x != null);
  const same = lined().filter(c => c.b === buyer && (c.L & mask));
  let xs = pick(same);
  if (xs.length >= 3) return {x: median(xs), n: xs.length, own: true};
  xs = pick(lined().filter(c => c.L & mask));
  return xs.length >= 5 ? {x: median(xs), n: xs.length, own: false} : null;
}

/* ---------- pieces of a page ---------- */
const who = (s, {plain = false} = {}) => {
  if (!s) return '';
  if (s.g >= 0) return `<span class="who c${s.g + 1}"><i class="dot"></i><span class="nm">${esc(shortName(s.name))}</span></span>`;
  return esc(s.person && !plain ? 'անհատ ձեռնարկատեր' : shortName(s.name));
};
const dateTile = d => { const p = parts(dOnly(d)), old = p.y !== parts(new Date(now())).y; return `<span class="tile"><b>${p.d}</b><span>${MON3[p.m]}${old ? NB + String(p.y).slice(2) : ''}</span></span>`; };
function leftTile(end) {
  const ms = toDate(end).getTime() - now(), days = dayNo(toDate(end)) - dayNo(new Date(now()));
  if (ms < DAY) return `<span class="tile warn"><b>${ms < HOUR ? '<1' : Math.floor(ms / HOUR)}</b><span>ԺԱՄ</span></span>`;
  return `<span class="tile${days <= 2 ? ' warn' : ''}"><b>${days}</b><span>ՕՐ</span></span>`;
}
const left = end => { const ms = end.getTime() - now(), days = dayNo(end) - dayNo(new Date(now())); return ms < HOUR ? 'մնացել է մեկ ժամից քիչ' : ms < DAY ? `մնացել է ${plural(Math.floor(ms / HOUR), 'ժամ')}` : `մնացել է ${plural(days, 'օր')}`; };
const amt = v => { if (!v) return '<span class="amt">—</span>'; const [a, ...u] = short(v).split(NB); return `<span class="amt">${a}<small>${u.length ? u.join(NB) + NB : ''}դրամ</small></span>`; };
const bits = (...xs) => { const a = xs.filter(Boolean); return a.map((x, i) => `<span class="bit">${x}${i < a.length - 1 ? `${NB}·` : ''}</span>`).join(''); };
const nw = x => `<span class="nw">${x}</span>`;
const tag = (text, cls = '', icon = '') => `<span class="tag${cls ? ' ' + cls : ''}">${icon ? ic(icon, 's') : ''}${esc(text)}</span>`;
const lineTags = mask => lineNames(mask).map(n => tag(n)).join('');

/* A list that shows its first rows and offers the rest. `rows` is every row's markup, made on demand. */
function list(id, items, rowFn, {cap = 30, cls = ''} = {}) {
  S.lists.set(id, {items, rowFn, shown: Math.min(cap, items.length), cap});
  const html = items.slice(0, cap).map((it, i) => `<li${i < 12 ? ` style="--i:${i}"` : ' style="--i:12"'}>${rowFn(it, i)}</li>`).join('');
  const rest = items.length - cap;
  return `<ul class="list rise ${cls}" id="l-${id}">${html}</ul>` +
    (rest > 0 ? `<button class="more" type="button" data-act="more" data-id="${id}">Ցույց տալ ևս ${Math.min(rest, cap)}-ը</button>` : '');
}
function contractRow(c, {buyer = true, sup = true} = {}) {
  const o = off(c);
  return `<button class="row" type="button" data-act="contract" data-i="${c.i}">${dateTile(c.d)}
    <span><span class="t clamp">${esc(title(c.subj))}</span>${buyer ? `<span class="s clamp">${esc(c.b.name)}</span>` : ''}
    <span class="m">${bits(sup ? who(c.s) : '', esc(c.f), o != null && o >= .005 ? `${pct(o)} ցածր նախահաշվից` : '')}</span></span>${amt(c.v)}</button>`;
}
const chips = (counts, total) => `<div class="chips" role="group" aria-label="Ուղղություններ">
  <button class="chip" type="button" data-act="line" data-line="-1" aria-pressed="${S.line < 0}">Բոլորը<span class="n">${total}</span></button>
  ${CFG.lines.map((l, i) => `<button class="chip" type="button" data-act="line" data-line="${i}" aria-pressed="${S.line === i}">${esc(l.name)}<span class="n">${counts[i] || 0}</span></button>`).join('')}</div>`;
const seg = (tab, opts) => { const at = Math.max(0, opts.findIndex(o => o[0] === S.seg[tab])); return `<div class="seg" style="--n:${opts.length};--at:${at}" role="group"><span class="thumb" aria-hidden="true"></span>${opts.map(o => `<button type="button" data-act="seg" data-seg="${o[0]}" aria-pressed="${o[0] === S.seg[tab]}">${o[1]}</button>`).join('')}</div>`; };
const countBy = (items, maskOf) => { const n = CFG.lines.map(() => 0); for (const it of items) { const m = maskOf(it); CFG.lines.forEach((l, i) => { if (m & (1 << i)) n[i]++; }); } return n; };
const empty = (head, text) => `<div class="empty"><b>${head}</b>${text}</div>`;
const sec = (head, text = '') => `<div class="sec"><h3>${head}</h3>${text ? `<p>${text}</p>` : ''}</div>`;

/* ---------- Այսօր ---------- */
function todayPlate() {
  const fit = OPEN.filter(t => t.L), soon = fit.filter(t => toDate(t.end).getTime() - now() < 3 * DAY).length;
  const known = fit.filter(t => t.b && ourBuyers().has(t.b)).length, d = new Date(now());
  let lead = fit.length ? `Մեր ուղղություններով բաց է <b>${plural(fit.length, 'մրցույթ')}</b>։` : 'Մեր ուղղություններով այսօր բաց էլեկտրոնային աճուրդ չկա։';
  if (soon) lead += ` <b>${soon}-ը</b> փակվում է երեք օրվա ընթացքում։`;
  if (known) lead += ` <b>${known}-ը</b> մեր գնորդներից է։`;
  return `<h2 class="title">${WD[parts(d).wd]}, ${fDay(d)}</h2><p class="lead">${lead}</p>`;
}
function todayView() {
  const mode = S.seg.today;
  let html = `<div class="bar">${seg('today', [['open', 'Բաց'], ['next', 'Սպասվող'], ['done', 'Կնքված']])}`;
  if (mode === 'open') {
    const fit = OPEN.filter(t => t.L), rows = fit.filter(t => inLine(t.L));
    html += chips(countBy(fit, t => t.L), fit.length) + '</div>';
    html += rows.length ? list('open', rows, t => `<button class="row" type="button" data-act="tender" data-id="${t.id}">${leftTile(t.end)}
      <span><span class="t clamp">${esc(t.subject || t.title)}</span><span class="s clamp">${esc(t.buyer || t.for || '')}</span>
      <span class="m">${lineTags(t.L)}${t.b && ourBuyers().has(t.b) ? tag('Մեր գնորդը', 'ok', 'check') : ''}${t.lots > 1 ? `<span>${plural(t.lots, 'չափաբաժին')}</span>` : ''}</span></span>
      <span class="go">${ic('go')}</span></button>`, {cap: 40})
      : empty('Այս պահին բաց աճուրդ չկա', 'Նոր հայտարարությունները հայտնվում են օրը չորս անգամ՝ 08:50, 11:50, 14:50 և 17:50։');
    html += `<p class="foot" style="margin:1rem .25rem 0;padding:0;border:0">Ցանկում միայն էլեկտրոնային աճուրդներն են։ Գնանշման հարցումները և բաց մրցույթները այստեղ դեռ չկան։</p>`;
  } else if (mode === 'next') {
    const all = expected(), rows = all.filter(r => inLine(r.L));
    html += chips(countBy(all, r => r.L), all.length) + '</div>';
    html += sec('Անցյալ տարի այս օրերին', 'Այս գնորդները մեկ տարի առաջ՝ առաջիկա երկու ամսվա օրերին, պայմանագիր են կնքել մեր ուղղություններով։ Հնարավոր է՝ այս տարի էլ գնեն. արժե հետևել նրանց հայտարարություններին։');
    html += rows.length ? list('next', rows, (r, i) => {
      const first = r.cs[0], sup = [...new Set(r.cs.map(c => c.s))];
      return `<button class="row" type="button" data-act="next" data-i="${all.indexOf(r)}">${dateTile(r.d)}
        <span><span class="t clamp">${esc(title(first.subj))}${r.cs.length > 1 ? ` և ևս ${r.cs.length - 1}-ը` : ''}</span><span class="s clamp">${esc(r.b.name)}</span>
        <span class="m">${bits(sup.length === 1 ? who(sup[0]) : plural(sup.length, 'մատակարար'), esc(first.f))}</span></span>${amt(r.v)}</button>`;
    }, {cap: 40}) : empty('Այս օրերին անցյալ տարի պայմանագիր չի կնքվել', 'Փորձեք մեկ այլ ուղղություն կամ ավելացրեք նորը կարգավորումներում։');
  } else {
    const all = recent(), rows = all.filter(c => inLine(c.L));
    html += chips(countBy(all, c => c.L), all.length) + '</div>';
    html += sec('Վերջին 30 օրում կնքված', 'Մեր ուղղություններով կնքված պայմանագրերը՝ ում հետ և ինչ գնով։');
    html += rows.length ? list('done', rows, c => contractRow(c), {cap: 40}) : empty('Վերջին 30 օրում պայմանագիր չկա', 'Գրանցամատյանը թարմացվում է ամեն առավոտ։');
  }
  return html;
}

/* ---------- Մենք ---------- */
function usPlate() {
  const cs = ours(), total = cs.reduce((a, c) => a + c.v, 0), from = dOnly(D.meta.from);
  return `<div class="note-seals">${G.map((g, i) => sealSVG(g.tin, {detail: 1, size: 104, stroke: 1.15, cls: `draw c${i + 1}`, style: `--wait:${i * 220}ms;--step:60ms`})).join('')}</div>
    <p class="sum"><span class="vh">${group(total)} դրամ</span><span aria-hidden="true" data-count="${Math.round(total)}">${group(total)}</span><small aria-hidden="true">դրամ</small></p>
    <p class="lead"><b>${plural(cs.length, 'պայմանագիր')}</b>, ${plural(ourBuyers().size, 'գնորդ')}՝ ${parts(from).y} թ. ${MON[parts(from).m]} ${parts(from).d}-ից</p>`;
}
function usView() {
  const cs = ours(), lost = entries().filter(e => e.lost);
  if (!cs.length) return `<div class="sec"></div>` + empty('Պայմանագիր չի գտնվել', `Գրանցամատյանում ${esc(G.map(g => g.tin).join(', '))} ՀՎՀՀ-ով պայմանագիր չկա ${fDayY(dOnly(D.meta.from))}-ից ի վեր։ Ստուգեք համարները կարգավորումներում։`);
  let html = sec('Ամիս առ ամիս', 'Կնքված պայմանագրերի գումարը՝ ըստ ամիսների, մլն դրամ։') + chartShell();
  html += sec('Ընկերությունները');
  html += `<ul class="list rise">${G.map((g, i) => {
    const mine = cs.filter(c => c.s === g.s), v = mine.reduce((a, c) => a + c.v, 0);
    return `<li style="--i:${i}"><button class="row" type="button" data-act="co" data-i="${i}" style="align-items:center"><span class="c${i + 1}">${sealSVG(g.tin, {detail: 0, size: 44, stroke: 2.3})}</span>
      <span><span class="t">${esc(shortName(g.name))}</span><span class="s">${g.s ? `${plural(mine.length, 'պայմանագիր')}, ${plural(new Set(mine.map(c => c.b)).size, 'գնորդ')}` : 'պայմանագիր չի գտնվել'}</span></span>${amt(v)}</button></li>`;
  }).join('')}</ul>`;
  if (lost.length) {
    html += sec('Մասնակցել ենք, պայմանագիրն ուրիշի հետ է', 'Մրցույթներ, որտեղ եղել ենք մասնակից, բայց պայմանագիր չենք կնքել։ Տեսեք՝ ում հետ և ինչ գնով է կնքվել։');
    html += list('lost', lost, e => {
      const v = e.t.cs.reduce((a, c) => a + c.v, 0), sup = [...new Set(e.t.cs.map(c => c.s))], first = e.t.cs[0];
      return `<button class="row" type="button" data-act="entry" data-code="${esc(e.t.code)}">${dateTile(e.d)}
        <span><span class="t clamp">${esc(title(first.subj))}${e.t.cs.length > 1 ? ` և ևս ${e.t.cs.length - 1}-ը` : ''}</span><span class="s clamp">${esc(first.b.name)}</span>
        <span class="m">${bits(who(G[e.gi].s), `կնքվել է՝ ${sup.length === 1 ? who(sup[0]) : plural(sup.length, 'մատակարարի հետ')}`)}</span></span>${amt(v)}</button>`;
    }, {cap: 12});
  }
  html += sec('Մեր պայմանագրերը') + list('mine', cs, c => contractRow(c), {cap: 20});
  return html;
}
function chartData() {
  return memo('chart', () => {
    const idx = new Map(D.months.map((m, i) => [m, i])), rows = D.months.map(() => G.map(() => 0));
    for (const c of ours()) rows[idx.get(c.m)][c.s.g] += c.v;
    return {rows, totals: rows.map(r => r.reduce((a, b) => a + b, 0))};
  });
}
const monthName = m => `${MON0[+m.slice(5) - 1]} ${m.slice(0, 4)}`;
function chartShell() {
  return `<figure class="chart" id="chart"><div class="chart-top"><div class="legend">${G.map((g, i) => `<span class="c${i + 1}"><i class="dot"></i><span style="color:var(--ink-2)">${esc(shortName(g.name))}</span></span>`).join('')}</div>
    <button class="swap-btn" type="button" data-act="chartmode" aria-pressed="${S.chartMode === 'table'}">${S.chartMode === 'table' ? ic('bars', 's') + 'Գծապատկեր' : ic('table', 's') + 'Աղյուսակ'}</button></div><div id="chart-body"></div></figure>`;
}
function drawChart() {
  const box = $('#chart-body');
  if (!box) return;
  const {rows, totals} = chartData();
  if (S.chartMode === 'table') {
    const live = D.months.map((m, i) => i).filter(i => totals[i] > 0), mln = v => String(+(v / 1e6).toFixed(v < 1e7 ? 2 : 1)).replace('.', ',');
    box.innerHTML = `<table class="tbl"><thead><tr><th scope="col">Ամիս</th>${G.map((g, j) => `<th scope="col"><span class="c${j + 1}"><i class="dot" style="display:inline-block;margin-right:.3125rem"></i></span>${esc(shortName(g.name))}</th>`).join('')}</tr></thead><tbody>${
      live.map(i => `<tr><td>${monthName(D.months[i])}</td>${rows[i].map(v => `<td>${v ? mln(v) : '—'}</td>`).join('')}</tr>`).join('')}</tbody>
      <tfoot><tr><td>Ընդամենը</td>${G.map((g, j) => `<td>${mln(rows.reduce((a, r) => a + r[j], 0))}</td>`).join('')}</tr></tfoot></table>`;
    return;
  }
  const W = Math.max(280, box.clientWidth), H = 196, L = 30, R = 2, T = 20, B = 24, n = rows.length, band = (W - L - R) / n, bw = Math.min(24, band - 6);
  const max = Math.max(...totals, 1), unit = 1e6, raw = max / unit, mag = Math.pow(10, Math.floor(Math.log10(raw))), top = [1, 2, 2.5, 5, 10].map(k => k * mag).find(k => k >= raw) * unit;
  const y = v => T + (H - T - B) * (1 - v / top), fmt = v => String(+(v / unit).toFixed(1)).replace('.', ',');
  const best = totals.indexOf(max);
  let g = '';
  for (const tick of [0, top / 2, top]) g += `<line class="${tick ? 'grid' : 'base'}" x1="${L}" x2="${W - R}" y1="${y(tick)}" y2="${y(tick)}"/><text class="ax" x="${L - 6}" y="${y(tick) + 3.5}" text-anchor="end">${fmt(tick)}</text>`;
  rows.forEach((row, i) => {
    const x = L + band * i + (band - bw) / 2, cx = x + bw / 2, mo = +D.months[i].slice(5) - 1;
    let y0 = y(0), stack = '';
    const live = row.map((v, j) => [v, j]).filter(p => p[0] > 0);
    live.forEach(([v, j], k) => {
      const h = Math.max(3, y(0) - y(v)), y1 = y0 - h, lastOne = k === live.length - 1, hh = Math.max(1.5, h - (k ? 2 : 0)), r = lastOne ? Math.min(4, hh / 2, bw / 2) : 0;
      const yb = y0 - (k ? 2 : 0);                             // a 2px gap of sheet between touching fills
      stack += `<path class="c${j + 1}" fill="currentColor" d="M${x} ${yb}V${y1 + r}${r ? `Q${x} ${y1} ${x + r} ${y1}` : ''}H${x + bw - r}${r ? `Q${x + bw} ${y1} ${x + bw} ${y1 + r}` : ''}V${yb}Z"/>`;
      y0 = y1;
    });
    g += `<g class="col" data-i="${i}">${stack ? `<g class="seg-r" style="--i:${i}">${stack}</g>` : ''}${i === best && totals[i] ? `<text class="top" x="${cx}" y="${y0 - 6}" text-anchor="middle">${fmt(totals[i])}</text>` : ''}
      ${i % 2 === 0 ? `<text class="ax" x="${cx}" y="${H - 7}" text-anchor="middle">${MON3[mo]}</text>` : ''}<rect class="hit" x="${L + band * i}" y="${T - 12}" width="${band}" height="${H - T - B + 12}" data-act="col" data-i="${i}"/></g>`;
  });
  const said = totals.map((t, i) => (t ? `${monthName(D.months[i])}՝ ${short(t)} դրամ` : '')).filter(Boolean).join(', ');
  box.innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="Պայմանագրերի գումարը ըստ ամիսների. ${esc(said)}">${g}</svg>`;
  box.dataset.geo = JSON.stringify({L, band, T, W});
  S.pick = -1;
}
function pickCol(i) {
  const box = $('#chart-body'), svg = $('svg', box), fig = $('#chart');
  $('.tip', fig)?.remove();
  $$('.col.on', box).forEach(c => c.classList.remove('on'));
  if (i === S.pick || i < 0) { S.pick = -1; svg?.classList.remove('pick'); return; }
  S.pick = i;
  const {rows, totals} = chartData(), geo = JSON.parse(box.dataset.geo), col = $(`.col[data-i="${i}"]`, box);
  svg.classList.add('pick'); col.classList.add('on');
  const tip = document.createElement('div');
  tip.className = 'tip';
  tip.innerHTML = `<b>${monthName(D.months[i])}</b>` + (totals[i] ? rows[i].map((v, j) => (v ? `<div class="c${j + 1}"><i class="dot"></i><span style="color:var(--sheet)">${esc(shortName(G[j].name))}</span><span style="color:var(--sheet)">${short(v)}</span></div>` : '')).join('') +
    (rows[i].filter(Boolean).length > 1 ? `<div><span>Ընդամենը</span><span>${short(totals[i])}</span></div>` : '') : '<div><span>Պայմանագիր չի կնքվել</span></div>');
  fig.append(tip);
  const scale = box.clientWidth / geo.W, cx = box.offsetLeft + (geo.L + geo.band * (i + .5)) * scale, half = geo.band * scale / 2 + 6;
  const x = cx > fig.clientWidth / 2 ? cx - half - tip.offsetWidth : cx + half;        // beside the column, never over it
  tip.style.left = Math.max(6, Math.min(fig.clientWidth - tip.offsetWidth - 6, x)) + 'px';
  tip.style.top = box.offsetTop + geo.T * scale + 'px';
}

/* ---------- Մրցակիցներ ---------- */
function rivalsPlate() {
  const all = new Set(lined().filter(c => c.s.g < 0).map(c => (c.s.person ? 'p' : c.s.key))).size, m = met().rows.filter(r => r.s).length;
  return `<h2 class="title">Մրցակիցներ</h2><p class="lead">Մեր ուղղություններով մեկ տարում պայմանագիր է կնքել <b>${plural(all, 'մատակարար')}</b>։${m ? ` Մրցույթներում հանդիպել ենք <b>${m}-ին</b>։` : ''}</p>`;
}
/* Sole proprietors are people: together, as one line, never by name and never ranked. */
const peopleRow = (text, right = '<span></span>') => `<ul class="list" style="margin-top:.625rem"><li><div class="row"><span class="tile">${ic('people')}</span><span><span class="t">Անհատ ձեռնարկատերեր</span><span class="s">${text}</span></span>${right}</div></li></ul>`;
const meter = (w, i, text = '') => `<span class="meter"><span class="track"><i style="--w:${Math.max(0, Math.min(1, w)).toFixed(3)};--i:${Math.min(i, 12)}"></i></span>${text ? `<span class="cap">${text}</span>` : ''}</span>`;
function rivalsView() {
  const mode = S.seg.rivals;
  let html = `<div class="bar">${seg('rivals', [['met', 'Հանդիպել ենք'], ['line', 'Մեր ուղղություններում']])}`;
  if (mode === 'met') {
    const m = met(), max = m.rows[0]?.n || 1;
    html += '</div>' + sec('Նույն մրցույթների մասնակիցները', `Մեր մասնակցած ${plural(m.tenders, 'մրցույթի')} մյուս մասնակիցները։ Մասնակիցների ցուցակ գրանցամատյանում լինում է հիմնականում էլեկտրոնային աճուրդների համար։`);
    html += m.rows.length ? list('met', m.rows, (r, i) => `<button class="row" type="button" data-act="sup" data-key="${esc(r.key)}"><span class="tile rank"><b>${i + 1}</b></span>
        <span><span class="t clamp">${esc(shortName(r.s.name))}</span><span class="s">${nw(`${plural(r.n, 'մրցույթ')} միասին ·`)} ${nw(`պայմանագիր՝ ${r.won}-ում`)}</span></span>
        <span class="go">${ic('go')}</span>${meter(r.n / max, i)}</button>`, {cap: 30})
      : empty('Մասնակիցների ցուցակ դեռ չկա', 'Երբ ընկերություններից մեկը մասնակցի էլեկտրոնային աճուրդի, այստեղ կերևան մյուս մասնակիցները։');
    if (m.people) html += peopleRow(`${plural(m.people.people.size, 'անհատ ձեռնարկատեր')}՝ ${plural(m.people.n, 'մրցույթում')} միասին, ${nw(`պայմանագիր՝ ${m.people.won}-ում`)}`);
    if (m.unknown) html += `<p class="foot" style="margin:1rem .25rem 0;padding:0;border:0">Եվս ${plural(m.unknown, 'մասնակցություն')} անանուն է. այդ մասնակիցները մեկ տարում ոչ մի պայմանագիր չեն կնքել, և գրանցամատյանը նրանց անունը չի տալիս։</p>`;
  } else {
    const rk = ranking(), max = rk.rows[0]?.v || 1, counts = CFG.lines.map((l, i) => new Set(lined().filter(c => c.L & (1 << i)).map(c => (c.s.person ? 'p' : c.s.key))).size);
    html += chips(counts, new Set(lined().map(c => (c.s.person ? 'p' : c.s.key))).size) + '</div>';
    html += sec(S.line < 0 ? 'Ով է կնքում մեր ուղղություններով' : `Ով է կնքում. ${esc(CFG.lines[S.line].name.toLowerCase())}`, `Մեկ տարում՝ ${money(rk.total)}, ${plural(rk.rows.reduce((a, r) => a + r.n, rk.people ? rk.people.n : 0), 'պայմանագիր')}։ Շարքը՝ ըստ գումարի։`);
    const folk = rk.people ? peopleRow(`${plural(rk.people.people.size, 'անհատ ձեռնարկատեր')} · ${plural(rk.people.n, 'պայմանագիր')} · ${nw(ofLine(rk.people.v, rk.total))}`, amt(rk.people.v)) : '';
    if (rk.people && rk.people.v > max) html += folk.replace('margin-top:.625rem', 'margin:0 0 .625rem');
    html += rk.rows.length ? list('rank', rk.rows, (r, i) => `<button class="row" type="button" data-act="${r.s.g >= 0 ? 'co' : 'sup'}" data-key="${esc(r.key)}" data-i="${r.s.g}"><span class="tile rank"><b>${i + 1}</b></span>
        <span><span class="t clamp">${r.s.g >= 0 ? who(r.s).replace('class="nm"', 'class="nm" style="color:var(--ink)"') : esc(shortName(r.s.name))}</span><span class="s">${nw(`${plural(r.n, 'պայմանագիր')} ·`)} ${nw(ofLine(r.v, rk.total))}</span></span>
        ${amt(r.v)}${meter(r.v / max, i)}</button>`, {cap: 30})
      : empty('Այս ուղղությամբ պայմանագիր չկա', 'Ընտրեք մեկ այլ ուղղություն։');
    if (rk.people && rk.people.v <= max) html += folk;
  }
  return html;
}

/* ---------- Գնորդներ ---------- */
function buyersPlate() {
  const all = new Set(lined().map(c => c.b)), mine = [...all].filter(b => ourBuyers().has(b)).length;
  return `<h2 class="title">Գնորդներ</h2><p class="lead">Մեր ուղղություններով գնում է կատարել <b>${plural(all.size, 'գնորդ')}</b>${mine ? `, նրանցից <b>${mine}-ը</b>՝ մեզնից` : ''}։</p>`;
}
function buyersView() {
  const mode = S.seg.buyers;
  let html = `<div class="bar">${seg('buyers', [['ours', 'Մեր գնորդները'], ['new', 'Հնարավոր գնորդներ']])}`;
  if (mode === 'ours') {
    const rows = ourBuyerRows();
    html += '</div>' + sec('Ովքեր են գնել մեզնից', 'Գծիկը ցույց է տալիս մեր բաժինը այդ գնորդի՝ մեր ուղղություններով գնումներում։');
    html += rows.length ? list('ours', rows, (r, i) => {
      const part = r.allV ? r.inV / r.allV : 0;
      return `<button class="row" type="button" data-act="buyer" data-key="${esc(r.b.key)}"><span class="tile rank"><b>${i + 1}</b></span>
        <span><span class="t clamp">${esc(r.b.name)}</span><span class="s">${nw(`${plural(r.n, 'պայմանագիր')} ·`)} ${nw(`վերջինը՝ ${fDayY(dOnly(r.last))}`)}</span></span>
        ${amt(r.v)}${r.allV ? meter(part, i, `մեր բաժինը՝ ${share(r.inV, r.allV)}`) : ''}</button>`;
    }) : empty('Գնորդ դեռ չկա', 'Երբ ընկերություններից մեկը պայմանագիր կնքի, գնորդը կհայտնվի այստեղ։');
  } else {
    const all = buyersIn().filter(r => !ourBuyers().has(r.b)), max = all[0]?.v || 1;
    const counts = CFG.lines.map((l, i) => new Set(lined().filter(c => (c.L & (1 << i)) && !ourBuyers().has(c.b)).map(c => c.b)).size);
    html += chips(counts, new Set(lined().filter(c => !ourBuyers().has(c.b)).map(c => c.b)).size) + '</div>';
    html += sec('Գնում են, բայց ոչ մեզնից', 'Գնորդներ, որոնք մեկ տարում պայմանագիր են կնքել մեր ուղղություններով, բայց ոչ մեր ընկերությունների հետ։');
    html += all.length ? list('new', all, (r, i) => {
      const top = [...r.sup.entries()].sort((a, b) => b[1] - a[1])[0];
      return `<button class="row" type="button" data-act="buyer" data-key="${esc(r.b.key)}"><span class="tile rank"><b>${i + 1}</b></span>
        <span><span class="t clamp">${esc(r.b.name)}</span><span class="s clamp">${nw(plural(r.n, 'պայմանագիր') + (top ? ' ·' : ''))}${top ? ` հիմնականում՝ ${esc(shortName(top[0].name))}` : ''}</span></span>
        ${amt(r.v)}${meter(r.v / max, i)}</button>`;
    }) : empty('Նոր գնորդ չի գտնվել', 'Ընտրեք մեկ այլ ուղղություն։');
  }
  return html;
}

/* ---------- the frame ---------- */
const PLATE = {today: todayPlate, us: usPlate, rivals: rivalsPlate, buyers: buyersPlate};
const VIEW = {today: todayView, us: usView, rivals: rivalsView, buyers: buyersView};
function setPlate(html, animate) {
  const body = $('#plate-body'), h0 = body.offsetHeight;
  body.style.height = '';
  body.innerHTML = `<div class="plate-in${animate ? ' swap' : ''}">${html}</div>`;
  const h1 = body.offsetHeight;
  if (animate && !CALM && h0 && Math.abs(h1 - h0) > 2) {
    body.style.height = h0 + 'px';
    void body.offsetHeight;
    body.style.height = h1 + 'px';
    clearTimeout(body.timer);
    body.timer = setTimeout(() => { body.style.height = ''; }, 560);
  }
}
function countUp(root) {
  for (const el of $$('[data-count]', root)) {
    const to = +el.dataset.count;
    if (CALM || !to) continue;
    const t0 = performance.now(), dur = 1500;
    const tick = t => {
      const k = Math.min(1, (t - t0) / dur);
      el.textContent = group(k === 1 ? to : to * (1 - Math.pow(2, -10 * k)));
      if (k < 1 && el.isConnected) requestAnimationFrame(tick);
    };
    el.textContent = '0';
    requestAnimationFrame(tick);
  }
}
function render({plate = true} = {}) {
  const at = TABS.indexOf(S.tab);
  $$('#tabs .tab').forEach(b => { if (b.dataset.tab === S.tab) b.setAttribute('aria-current', 'page'); else b.removeAttribute('aria-current'); });
  $('#tabs .tab-ind').style.setProperty('--at', at);
  $('#wheel').style.setProperty('--turn', at);
  $('#plate').dataset.tab = S.tab;
  S.lists.clear();
  if (plate) { setPlate(PLATE[S.tab](), true); countUp($('#plate-body')); }
  $('#view').innerHTML = !CFG.lines.length && S.tab !== 'us'
    ? `<div class="sec"></div>${empty('Ուղղություն դեռ չկա', 'Գրեք, թե ինչ եք վաճառում, և էջը կգտնի համապատասխան մրցույթները, մրցակիցներին ու գնորդներին։')}<div class="actions"><button class="btn" type="button" data-act="settings">Բացել կարգավորումները</button></div>`
    : VIEW[S.tab]();
  if (S.tab === 'us') drawChart();
  footer();
  S.loaded = true;
}
function footer() {
  const f = $('#foot'), up = toDate(D.meta.updated), from = dOnly(D.meta.from);
  f.hidden = false;
  f.innerHTML = `Աղբյուրը՝ <a href="${REGISTER}" target="_blank" rel="noopener">armeps.am-ի պայմանագրերի գրանցամատյանը</a> և էլեկտրոնային աճուրդների համակարգը։ Պայմանագրերը՝ ${parts(from).y} թ. ${MON[parts(from).m]} ${parts(from).d}-ից, թարմացվել է ${fDay(up)}, ${fTime(up)}։ Ներառված են մրցակցային ընթացակարգերը և 1 մլն դրամից բարձր մեկ անձից գնումները։ <a href="../">Բոլոր մրցույթները</a>`;
}
function go(tab) {
  if (tab === S.tab) { scrollTo({top: 0, behavior: CALM ? 'auto' : 'smooth'}); return; }
  S.scroll[S.tab] = scrollY;
  S.tab = tab;
  store.set('tab', tab);
  render();
  scrollTo(0, S.scroll[tab] || 0);
}
function toast(text) {
  const t = $('#toast');
  t.textContent = text;
  t.classList.add('on');
  clearTimeout(t.timer);
  t.timer = setTimeout(() => t.classList.remove('on'), 2400);
}

/* ---------- sheets ---------- */
const headline = text => { const t = title(text); return t.length > 130 ? `<h2>${esc(t.slice(0, 110).replace(/\s+\S*$/, ''))}…</h2><p class="sub">${esc(t)}</p>` : `<h2>${esc(t)}</h2>`; };
const facts = rows => `<dl class="facts">${rows.filter(Boolean).map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join('')}</dl>`;
const stat = (b, text) => `<div class="stat"><b>${b}</b><span>${text}</span></div>`;
const hint = html => `<p class="hint">${ic('bulb')}<span>${html}</span></p>`;
const supLink = s => (s.person ? esc(s.name) : s.g >= 0 ? `<button class="lnk" type="button" data-act="co" data-i="${s.g}">${esc(s.name)}</button>` : `<button class="lnk" type="button" data-act="sup" data-key="${esc(s.key)}">${esc(s.name)}</button>`);
const buyLink = b => `<button class="lnk" type="button" data-act="buyer" data-key="${esc(b.key)}">${esc(b.name)}</button>`;
const offHint = u => (u && u.x >= .005 ? hint(u.own
  ? `Այս գնորդի նման պայմանագրերի կեսը կնքվել է նախահաշվից առնվազն <b>${pct(u.x)}</b> ցածր գնով։ Հաշվարկը՝ ${plural(u.n, 'պայմանագրով')}։`
  : `Այս ուղղությամբ պայմանագրերի կեսը կնքվել է նախահաշվից առնվազն <b>${pct(u.x)}</b> ցածր գնով։ Հաշվարկը՝ բոլոր գնորդների ${plural(u.n, 'պայմանագրով')}։`) : '');

const SHEETS = {
  tender(id) {
    const t = OPEN.find(x => x.id === +id);
    if (!t) return '<h2>Մրցույթը փակվել է</h2>';
    const end = toDate(t.end), ask = toDate(t.ask), auc = toDate(t.auc), before = t.b ? lined().filter(c => c.b === t.b && (c.L & t.L)) : [];
    const names = (t.lot.ln || '').split('; ').filter(Boolean);
    return `${headline(t.subject || t.title)}
      <div class="tags">${lineTags(t.L)}${t.b && ourBuyers().has(t.b) ? tag('Մեր գնորդը', 'ok', 'check') : ''}</div>
      ${facts([
        ['Գնորդ', t.b ? buyLink(t.b) : esc(t.buyer || t.for || '—')],
        ['Հայտերը՝ մինչև', `${fDay(end)}, ${fTime(end)}<small>${left(end)}</small>`],
        ask && ['Հարցերը՝ մինչև', `${fDay(ask)}, ${fTime(ask)}`],
        auc && ['Աճուրդը', `${fDay(auc)}, ${fTime(auc)}`],
        ['Չափաբաժին', `${group(t.lots || t.lot.n || 1)}${names.length ? `<small>${esc(names.slice(0, 6).join(', '))}${names.length > 6 ? ' և այլն' : ''}</small>` : ''}`],
        ['Ծածկագիր', esc(t.code)]
      ])}
      ${offHint(usualOff(t.b, t.L))}
      ${before.length ? sec('Ում հետ է այս գնորդը կնքել նախկինում', 'Նույն ուղղությամբ, վերջին մեկ տարում։') + list('before', before, c => contractRow(c, {buyer: false}), {cap: 8})
        : t.b ? sec('Այս գնորդի նախորդ պայմանագրերը', 'Նույն ուղղությամբ վերջին մեկ տարում պայմանագիր չի գտնվել։') : ''}
      <div class="actions"><a class="btn" href="../#t${t.id}">Բացել մրցույթի էջը${ic('go', 's')}</a>
      <a class="btn quiet" href="${ARMEPS}/hy/public/tender_details/by_end_bid_time/2/tid/${t.id}/" target="_blank" rel="noopener">Բացել ARMEPS-ում${ic('out', 's')}</a></div>`;
  },
  contract(i) {
    const c = D.C[+i], o = off(c), others = c.t ? c.t.cs.filter(x => x !== c) : [];
    let people = '';
    if (c.t) {
      const known = [], seen = new Set();
      let unknown = 0;
      for (const sid of c.t.parts) { const s = D.bySid.get(sid); if (!s) unknown++; else if (!seen.has(s)) { seen.add(s); known.push(s); } }
      people = sec(`Մասնակիցներ՝ ${known.length + unknown}`) + `<ul class="list">${known.map(s => `<li><div class="row" style="grid-template-columns:minmax(0,1fr) auto;min-height:0"><span class="t" style="font-weight:500">${s.g >= 0 ? who(s) : supLink(s)}</span>${c.t.cs.some(x => x.s === s) ? tag('պայմանագիր', 'ok', 'check') : '<span></span>'}</div></li>`).join('')}</ul>` +
        (unknown ? `<p class="sub">Եվս ${plural(unknown, 'մասնակից')}, որոնց անունը գրանցամատյանը չի տալիս։</p>` : '');
    }
    return `${headline(c.subj)}
      ${facts([
        ['Գնորդ', buyLink(c.b)],
        ['Մատակարար', supLink(c.s)],
        ['Կնքվել է', fDayY(dOnly(c.d))],
        ['Պայմանագրի գին', c.v ? `${group(c.v)} դրամ${o != null && o >= .005 ? `<small>նախահաշվից ${pct(o)} ցածր</small>` : ''}` : '—<small>գրանցամատյանում գինը սխալ է գրված</small>'],
        c.est ? ['Նախահաշիվ', `${group(c.est)} դրամ`] : null,
        ['Ընթացակարգ', esc(D.meta.forms[c.f] || c.f) + ` <span style="color:var(--ink-3)">(${esc(c.f)})</span>`],
        KIND[c.k] ? ['Տեսակ', KIND[c.k]] : null,
        c.t ? ['Մրցույթի ծածկագիր', esc(c.t.code)] : null
      ])}
      ${people}
      ${others.length ? sec('Նույն մրցույթի մյուս պայմանագրերը') + list('same', others, x => contractRow(x, {buyer: false}), {cap: 8}) : ''}
      <div class="actions"><a class="btn quiet" href="${REGISTER}" target="_blank" rel="noopener">Բացել գրանցամատյանը${ic('out', 's')}</a></div>`;
  },
  next(i) {
    const r = expected()[+i], d = dOnly(r.d);
    return `<h2>${esc(r.b.name)}</h2><p class="sub">Մեկ տարի առաջ՝ ${fDay(d)} ${parts(d).y} թ., ${r.cs.length > 1 ? `կնքել է ${plural(r.cs.length, 'պայմանագիր')}՝ ${money(r.v)}` : `կնքել է պայմանագիր՝ ${money(r.v)}`}։</p>
      <div class="tags">${lineTags(r.L)}${ourBuyers().has(r.b) ? tag('Մեր գնորդը', 'ok', 'check') : ''}</div>
      ${offHint(usualOff(r.b, r.L))}
      ${sec('Այն ժամանակ կնքված')}${list('nextc', r.cs, c => contractRow(c, {buyer: false}), {cap: 12})}
      <div class="actions"><button class="btn" type="button" data-act="buyer" data-key="${esc(r.b.key)}">Գնորդի բոլոր գնումները${ic('go', 's')}</button></div>`;
  },
  entry(code) {
    const t = D.ten.get(code), first = t.cs[0], v = t.cs.reduce((a, c) => a + c.v, 0);
    const known = [], seen = new Set();
    let unknown = 0;
    for (const sid of t.parts) { const s = D.bySid.get(sid); if (!s) unknown++; else if (!seen.has(s)) { seen.add(s); known.push(s); } }
    return `${headline(first.subj)}<p class="sub">${esc(first.b.name)}</p>
      ${facts([['Մրցույթի ծածկագիր', esc(code)], ['Կնքված պայմանագրեր', `${group(t.cs.length)}<small>${money(v)}</small>`], ['Մասնակիցներ', group(known.length + unknown)]])}
      ${sec('Ում հետ է կնքվել')}${list('entryc', t.cs, c => contractRow(c, {buyer: false}), {cap: 12})}
      ${sec('Մասնակիցները')}<ul class="list">${known.map(s => `<li><div class="row" style="grid-template-columns:minmax(0,1fr) auto;min-height:0"><span class="t" style="font-weight:500">${s.g >= 0 ? who(s) : supLink(s)}</span>${t.cs.some(x => x.s === s) ? tag('պայմանագիր', 'ok', 'check') : '<span></span>'}</div></li>`).join('')}</ul>
      ${unknown ? `<p class="sub">Եվս ${plural(unknown, 'մասնակից')}, որոնց անունը գրանցամատյանը չի տալիս։</p>` : ''}`;
  },
  sup(key) {
    const s = D.sup.get(key);
    if (!s) return '<h2>Մատակարարը չի գտնվել</h2>';
    const cs = lined().filter(c => c.s === s), v = cs.reduce((a, c) => a + c.v, 0), offs = cs.map(off).filter(x => x != null), m = met().rows.find(r => r.s === s);
    const buyers = new Map();
    for (const c of cs) buyers.set(c.b, (buyers.get(c.b) || 0) + c.v);
    const top = [...buyers.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5), max = top[0]?.[1] || 1;
    return `<h2>${esc(s.name)}</h2><p class="sub">${s.tin ? `ՀՎՀՀ ${esc(s.tin)} · ` : ''}մեկ տարում՝ ընդամենը ${plural(s.n, 'պայմանագիր')}, ${money(s.v)}</p>
      <div class="stats">${stat(money(v), `${plural(cs.length, 'պայմանագիր')} մեր ուղղություններով`)}
        ${offs.length >= 2 ? stat(pct(median(offs)), 'սովորական զեղչը նախահաշվից') : stat('—', 'նախահաշվից զեղչի տվյալ չկա')}
        ${m ? stat(group(m.n), 'մրցույթում հանդիպել ենք') + stat(group(m.won), 'դրանցից պայմանագիր է կնքել') : ''}</div>
      ${top.length ? sec('Հիմնական գնորդները', 'Մեր ուղղություններով։') + `<ul class="list">${top.map(([b, bv], i) => `<li><button class="row" type="button" data-act="buyer" data-key="${esc(b.key)}"><span class="tile rank"><b>${i + 1}</b></span><span><span class="t clamp">${esc(b.name)}</span></span>${amt(bv)}${meter(bv / max, i)}</button></li>`).join('')}</ul>` : ''}
      ${cs.length ? sec('Պայմանագրերը մեր ուղղություններով') + list('supc', cs, c => contractRow(c, {sup: false}), {cap: 10}) : sec('Մեր ուղղություններով պայմանագիր չունի', 'Հանդիպել ենք միայն որպես մասնակցի։')}`;
  },
  buyer(key) {
    const b = D.buy.get(key);
    if (!b) return '<h2>Գնորդը չի գտնվել</h2>';
    const cs = lined().filter(c => c.b === b), v = cs.reduce((a, c) => a + c.v, 0), ourV = cs.filter(c => c.s.g >= 0).reduce((a, c) => a + c.v, 0);
    const offs = cs.map(off).filter(x => x != null), open = OPEN.filter(t => t.b === b && t.L);
    const sup = new Map();
    for (const c of cs) { const k = c.s.person ? 'person' : c.s; const r = sup.get(k) || {s: c.s.person ? null : c.s, v: 0, n: 0}; r.v += c.v; r.n++; sup.set(k, r); }
    const folk = sup.get('person') || null;
    sup.delete('person');
    const top = [...sup.values()].sort((x, y) => y.v - x.v).slice(0, 6), max = top[0]?.v || 0;
    const byMonth = D.months.map(m => cs.filter(c => c.m === m).reduce((a, c) => a + c.v, 0)), mmax = Math.max(...byMonth, 1);
    return `<h2>${esc(b.name)}</h2><p class="sub">${b.tin ? `ՀՎՀՀ ${esc(b.tin)}` : ''}</p>
      <div class="stats">${stat(money(v), `${plural(cs.length, 'պայմանագիր')} մեր ուղղություններով`)}
        ${stat(v ? pct(ourV / v) : '—', 'մեր բաժինը այդ գնումներում')}
        ${offs.length >= 2 ? stat(pct(median(offs)), 'սովորական զեղչը նախահաշվից') : ''}
        ${stat(group(new Set(cs.map(c => c.s)).size), 'տարբեր մատակարար')}</div>
      ${open.length ? sec('Այժմ բաց մրցույթները') + `<ul class="list">${open.map(t => `<li><button class="row" type="button" data-act="tender" data-id="${t.id}">${leftTile(t.end)}<span><span class="t clamp">${esc(t.subject || t.title)}</span><span class="m">${lineTags(t.L)}</span></span><span class="go">${ic('go')}</span></button></li>`).join('')}</ul>` : ''}
      ${cs.length ? sec('Երբ է կնքում', 'Մեր ուղղություններով կնքված գումարը՝ ըստ ամիսների։') + `<div class="mini" role="img" aria-label="${esc(D.months.map((m, i) => (byMonth[i] ? `${monthName(m)}՝ ${short(byMonth[i])}` : '')).filter(Boolean).join(', '))}">${byMonth.map((x, i) => `<i class="${x ? '' : 'z'}" style="height:${x ? Math.max(6, x / mmax * 100) : 3}%;--i:${i}"></i>`).join('')}</div><div class="mini-x" aria-hidden="true">${D.months.map((m, i) => `<span>${i % 2 ? '' : MON3[+m.slice(5) - 1].slice(0, 3)}</span>`).join('')}</div>` : ''}
      ${top.length || folk ? sec('Ումից է գնում') + (folk && folk.v > max ? peopleRow(plural(folk.n, 'պայմանագիր'), amt(folk.v)).replace('margin-top:.625rem', 'margin:0 0 .625rem') : '') + (top.length ? `<ul class="list">${top.map((r, i) => `<li><button class="row" type="button" data-act="${r.s.g >= 0 ? 'co' : 'sup'}" data-key="${esc(r.s.key)}" data-i="${r.s.g}"><span class="tile rank"><b>${i + 1}</b></span><span><span class="t clamp">${r.s.g >= 0 ? who(r.s).replace('class="nm"', 'class="nm" style="color:var(--ink)"') : esc(shortName(r.s.name))}</span><span class="s">${plural(r.n, 'պայմանագիր')}</span></span>${amt(r.v)}${meter(r.v / max, i)}</button></li>`).join('')}</ul>` : '') + (folk && folk.v <= max ? peopleRow(plural(folk.n, 'պայմանագիր'), amt(folk.v)) : '') : ''}
      ${cs.length ? sec('Վերջին պայմանագրերը') + list('buyc', cs, c => contractRow(c, {buyer: false}), {cap: 10}) : sec('Մեր ուղղություններով պայմանագիր չկա')}`;
  },
  co(i) {
    const g = G[+i];
    if (!g) return '';
    const cs = ours().filter(c => c.s === g.s), v = cs.reduce((a, c) => a + c.v, 0), es = entries().filter(e => e.gi === +i), lost = es.filter(e => e.lost);
    const offs = cs.map(off).filter(x => x != null), mask = cs.reduce((a, c) => a | c.L, 0);
    return `<div class="co-head"><span class="c${+i + 1}">${sealSVG(g.tin, {detail: 1, size: 84, stroke: 1.2, cls: 'draw', style: '--step:55ms'})}</span><div><h2>${esc(g.name)}</h2><p class="sub">ՀՎՀՀ ${esc(g.tin)}</p></div></div>
      <div class="tags">${lineTags(mask)}</div>
      <div class="stats">${stat(money(v), plural(cs.length, 'պայմանագիր'))}
        ${stat(group(new Set(cs.map(c => c.b)).size), 'գնորդ')}
        ${es.length ? stat(`${es.length - lost.length} / ${es.length}`, 'պայմանագիր՝ մասնակցած մրցույթներից') : ''}
        ${offs.length >= 2 ? stat(pct(median(offs)), 'սովորական զեղչը նախահաշվից') : ''}</div>
      ${cs.length ? sec('Պայմանագրերը') + list('coc', cs, c => contractRow(c, {sup: false}), {cap: 12}) : sec('Պայմանագիր չի գտնվել', 'Գրանցամատյանում այս ՀՎՀՀ-ով պայմանագիր չկա։')}
      ${lost.length ? sec('Մասնակցել է, պայմանագիրն ուրիշի հետ է') + list('colost', lost, e => {
        const sup = [...new Set(e.t.cs.map(c => c.s))], first = e.t.cs[0];
        return `<button class="row" type="button" data-act="entry" data-code="${esc(e.t.code)}">${dateTile(e.d)}<span><span class="t clamp">${esc(title(first.subj))}</span><span class="s clamp">${esc(first.b.name)}</span>
          <span class="m">${bits(`կնքվել է՝ ${sup.length === 1 ? who(sup[0]) : plural(sup.length, 'մատակարարի հետ')}`)}</span></span>${amt(e.t.cs.reduce((a, c) => a + c.v, 0))}</button>`;
      }, {cap: 12}) : ''}`;
  },
  settings() {
    const link = myLink();
    return `<h2>Կարգավորումներ</h2>
      ${sec('Ընկերությունները', `Մինչև ${MAX_CO} ընկերություն։ Որոնեք անունով կամ ՀՎՀՀ-ով։`)}
      <div id="set-co">${coRows()}</div>
      ${CFG.tins.length < MAX_CO ? `<div class="field"><input class="inp" id="co-q" type="search" inputmode="search" autocomplete="off" enterkeyhint="search" placeholder="Ընկերության անունը կամ ՀՎՀՀ-ն" aria-label="Որոնել ընկերություն"></div><div id="co-found"></div>` : ''}
      ${sec('Ուղղությունները', 'Գրեք բառի սկիզբը. «կահույք»-ը կգտնի նաև «կահույքի»-ն։')}
      <div class="picked" id="set-lines">${lineRows()}</div>
      <form class="field" data-form="line"><input class="inp" name="w" autocomplete="off" enterkeyhint="done" placeholder="Նոր ուղղություն, օրինակ՝ վարագույր" aria-label="Նոր ուղղություն"><button class="btn" type="submit" style="min-height:2.875rem">${ic('plus', 's')}Ավելացնել</button></form>
      ${sec('Իմ հղումը', 'Այս հղումով էջը բացվում է հենց այս ընկերություններով և ուղղություններով։ Ավելացրեք այն հեռախոսի գլխավոր էկրանին։')}
      <div class="actions" style="margin-top:.625rem"><button class="btn" type="button" data-act="copy" data-link="${esc(link)}">${ic('link', 's')}Պատճենել հղումը</button></div>
      ${sec('Տվյալների մասին', `Էջը ոչինչ չի պահում և ոչ մի տեղ չի ուղարկում. ընտրությունը մնում է միայն հղման մեջ և այս սարքում։ Բոլոր թվերը պետական գնումների բաց գրանցամատյանից են, ${plural(D.C.length, 'պայմանագիր')}՝ ${fDayY(dOnly(D.meta.from))}-ից։ Անհատ ձեռնարկատերերը ցանկերում անունով չեն երևում։`)}`;
  }
};
const coRows = () => (G.length ? G.map((g, i) => `<div class="co-row"><span class="c${i + 1}">${sealSVG(g.tin, {detail: 0, size: 40, stroke: 2.4})}</span><span><span class="t">${esc(g.name)}</span><br><span class="s">ՀՎՀՀ ${esc(g.tin)}${g.s ? ` · ${plural(g.s.n, 'պայմանագիր')}` : ' · պայմանագիր չի գտնվել'}</span></span>
  <button class="ibtn" style="margin:0;color:var(--ink-3)" type="button" data-act="co-del" data-tin="${esc(g.tin)}" aria-label="Հեռացնել ${esc(g.name)}">${ic('x')}</button></div>`).join('') : '<p class="sub">Ընկերություն ընտրված չէ։</p>');
const lineRows = () => CFG.lines.map((l, i) => `<span class="pill">${esc(l.name)}<button type="button" data-act="line-del" data-i="${i}" aria-label="Հեռացնել ${esc(l.name)}">${ic('x', 's')}</button></span>`).join('') || '<p class="sub">Ուղղություն չկա։</p>';
function findCompanies(q) {
  const n = norm(q).trim();
  if (n.length < 2) return [];
  const digits = /^\d+$/.test(n);
  return [...D.sup.values()].filter(s => s.tin && !s.person && !CFG.tins.includes(s.tin) && (digits ? s.tin.startsWith(n) : norm(s.name).includes(n)))
    .sort((a, b) => b.n - a.n).slice(0, 6);
}
const foundRows = rows => (rows.length ? `<ul class="list" style="margin-top:.5rem">${rows.map(s => `<li><button class="row" type="button" data-act="co-add" data-tin="${esc(s.tin)}" style="grid-template-columns:minmax(0,1fr) auto"><span><span class="t">${esc(s.name)}</span><span class="s">ՀՎՀՀ ${esc(s.tin)} · ${plural(s.n, 'պայմանագիր')}</span></span><span class="go">${ic('plus')}</span></button></li>`).join('')}</ul>` : '');

const dialog = $('#sheet');
function paintSheet(swap, keep = false) {
  const top = S.stack[S.stack.length - 1], body = $('#sheet-body'), y = body.scrollTop;
  body.classList.remove('swap');
  body.innerHTML = SHEETS[top[0]](top[1]);
  body.scrollTop = keep ? y : 0;
  if (swap) { void body.offsetWidth; body.classList.add('swap'); }
  $('#sheet-back').hidden = S.stack.length < 2;
}
function openSheet(name, arg) {
  S.stack.push([name, arg]);
  try { history.pushState({sheet: S.stack.length}, ''); } catch { /* no history here: the buttons still close it */ }
  if (!dialog.open) {
    dialog.classList.remove('out');
    if (dialog.showModal) dialog.showModal(); else { dialog.setAttribute('open', ''); dialog.classList.add('plain'); }
    document.documentElement.classList.add('lock');
    paintSheet(false);
  } else paintSheet(true);
}
function shutSheet() {
  if (!dialog.open) return;
  const done = () => { if (dialog.close) dialog.close(); else dialog.removeAttribute('open'); dialog.classList.remove('out'); dialog.style.transform = ''; document.documentElement.classList.remove('lock'); $('#sheet-body').innerHTML = ''; };
  if (CALM) return done();
  dialog.classList.add('out');
  dialog.addEventListener('animationend', done, {once: true});
}
addEventListener('popstate', () => {
  if (!S.stack.length) return;
  S.stack.pop();
  if (S.stack.length) paintSheet(true); else { shutSheet(); syncAddress(); }
});
const backOne = () => { if (history.state?.sheet) history.back(); else { S.stack.pop(); if (S.stack.length) paintSheet(true); else { shutSheet(); syncAddress(); } } };
const closeAll = () => { const n = S.stack.length; if (!n) return; if (history.state?.sheet) { S.stack.length = 1; history.go(-n); } else { S.stack.length = 0; shutSheet(); syncAddress(); } };
dialog.addEventListener('cancel', e => { e.preventDefault(); closeAll(); });
{
  const head = $('.sheet-head', dialog);
  let pull = null;
  head.addEventListener('pointerdown', e => {
    if (e.target.closest('button') || CALM) return;
    pull = {y: e.clientY, t: e.timeStamp, dy: 0};
    head.setPointerCapture(e.pointerId);
  });
  head.addEventListener('pointermove', e => {
    if (!pull) return;
    pull.dy = Math.max(0, e.clientY - pull.y);
    dialog.style.transform = `translateY(${pull.dy}px)`;
  });
  const drop = e => {
    if (!pull) return;
    const fast = pull.dy / Math.max(1, e.timeStamp - pull.t) > .55, far = pull.dy > 120;
    pull = null;
    if (far || fast) { closeAll(); return; }                // the closing animation starts from where the finger left it
    dialog.style.transition = 'transform .32s cubic-bezier(.16,1,.3,1)';
    dialog.style.transform = '';
    setTimeout(() => { dialog.style.transition = ''; }, 340);
  };
  head.addEventListener('pointerup', drop);
  head.addEventListener('pointercancel', drop);
}
dialog.addEventListener('click', e => { if (e.target === dialog) closeAll(); });

/* ---------- changing the choice ---------- */
function reapply({sheet = true} = {}) {
  apply();
  saveConfig();
  paintSig();
  if (!CFG.tins.length || S.setup) { S.stack.length = 0; if (dialog.open) { if (dialog.close) dialog.close(); else dialog.removeAttribute('open'); document.documentElement.classList.remove('lock'); } return firstRun(); }
  $('#tabs').hidden = false; $('#b-set').hidden = false;
  render();
  if (sheet && dialog.open) paintSheet(false, true);
}
function paintSig() {
  $('#sig').innerHTML = CFG.tins.map((tin, i) => sealSVG(tin, {detail: 0, size: 30, stroke: 2.6, cls: `draw c${i + 1}`, style: `--wait:${300 + i * 160}ms;--step:50ms;--dur:1.1s`})).join('');
  const sum = CFG.tins.reduce((a, t) => a + +t, 0) || 20261117;
  $('#wheel').innerHTML = sealSVG(String(sum % 1e8), {detail: 2, size: 352, stroke: .6, cls: 'draw', style: '--step:120ms;--dur:2.6s'});
}
function firstRun() {
  S.setup = true;
  $('#tabs').hidden = true; $('#b-set').hidden = true; $('#foot').hidden = true;
  setPlate('<h2 class="title">Ո՞ր ընկերությունների համար</h2><p class="lead">Գտեք ձեր ընկերությունը պետական գնումների պայմանագրերի գրանցամատյանում։ Էջը ցույց կտա նրա պայմանագրերը, մրցակիցներին և գնորդներին։</p>', S.loaded);
  $('#view').innerHTML = `<div class="setup"><div id="set-co">${CFG.tins.length ? coRows() : ''}</div>
    ${CFG.tins.length < MAX_CO ? `<div class="field"><input class="inp" id="co-q" type="search" autocomplete="off" enterkeyhint="search" placeholder="Ընկերության անունը կամ ՀՎՀՀ-ն" aria-label="Որոնել ընկերություն"></div><div id="co-found"></div>` : ''}
    ${CFG.tins.length ? `<div class="actions"><button class="btn" type="button" data-act="start">Շարունակել${ic('go', 's')}</button></div>` : ''}
    <p class="foot" style="margin:1.25rem .25rem 0;padding:0;border:0">Որոնվում են այն ընկերությունները, որոնք ${fDayY(dOnly(D.meta.from))}-ից ի վեր գոնե մեկ պայմանագիր են կնքել։ Ընտրությունը մնում է միայն այս սարքում և էջի հղման մեջ։</p></div>`;
  S.loaded = true;
}

/* ---------- every tap ---------- */
const ACT = {
  tab: el => go(el.dataset.tab),
  seg(el) { S.seg[S.tab] = el.dataset.seg; store.set('seg.' + S.tab, el.dataset.seg); const y = scrollY; render({plate: false}); scrollTo(0, Math.min(y, $('#view').offsetTop)); },
  line(el) { S.line = +el.dataset.line; const y = scrollY, x = $('.chips')?.scrollLeft || 0; render({plate: false}); const c = $('.chips'); if (c) c.scrollLeft = x; scrollTo(0, Math.min(y, $('#view').offsetTop)); },
  more(el) {
    const l = S.lists.get(el.dataset.id), ul = $('#l-' + el.dataset.id);
    if (!l || !ul) return;
    const next = l.items.slice(l.shown, l.shown + l.cap);
    ul.insertAdjacentHTML('beforeend', next.map((it, i) => `<li style="--i:${Math.min(i, 8)}">${l.rowFn(it, l.shown + i)}</li>`).join(''));
    l.shown += next.length;
    const rest = l.items.length - l.shown;
    if (rest > 0) el.textContent = `Ցույց տալ ևս ${Math.min(rest, l.cap)}-ը`; else el.remove();
  },
  tender: el => openSheet('tender', el.dataset.id),
  contract: el => openSheet('contract', el.dataset.i),
  next: el => openSheet('next', el.dataset.i),
  entry: el => openSheet('entry', el.dataset.code),
  sup: el => openSheet('sup', el.dataset.key),
  buyer: el => openSheet('buyer', el.dataset.key),
  co: el => openSheet('co', el.dataset.i),
  settings: () => openSheet('settings'),
  start() { S.setup = false; reapply(); scrollTo(0, 0); },
  'sheet-back': backOne,
  'sheet-close': closeAll,
  chartmode() { S.chartMode = S.chartMode === 'table' ? 'bars' : 'table'; $('#chart').outerHTML = chartShell(); drawChart(); },
  col: el => pickCol(+el.dataset.i),
  async copy(el) {
    let ok = false;
    try { await navigator.clipboard.writeText(el.dataset.link); ok = true; } catch {
      const box = document.createElement('textarea');
      box.value = el.dataset.link; box.setAttribute('readonly', ''); box.style.cssText = 'position:fixed;opacity:0';
      el.after(box); box.select();
      try { ok = document.execCommand('copy'); } catch { ok = false; }
      box.remove();
    }
    toast(ok ? 'Հղումը պատճենվեց' : 'Չհաջողվեց պատճենել. պատճենեք հասցեի տողից');
  },
  'co-add'(el) { if (CFG.tins.length < MAX_CO && !CFG.tins.includes(el.dataset.tin)) { CFG.tins.push(el.dataset.tin); CFG.lines = S.guessed ? null : CFG.lines; reapply(); } },
  'co-del'(el) { CFG.tins = CFG.tins.filter(t => t !== el.dataset.tin); if (S.guessed) CFG.lines = null; reapply(); },
  'line-del'(el) { CFG.lines.splice(+el.dataset.i, 1); S.guessed = false; S.line = -1; reapply(); }
};
document.addEventListener('click', e => {
  const el = e.target.closest('[data-act]');
  if (el) { ACT[el.dataset.act]?.(el, e); return; }
  if (S.pick >= 0 && !e.target.closest('#chart')) pickCol(-1);
});
document.addEventListener('pointerover', e => { if (e.pointerType === 'mouse') { const el = e.target.closest?.('.hit'); if (el && +el.dataset.i !== S.pick) pickCol(+el.dataset.i); } });
document.addEventListener('input', e => { if (e.target.id === 'co-q') $('#co-found').innerHTML = foundRows(findCompanies(e.target.value)); });
document.addEventListener('submit', e => {
  const form = e.target.closest('[data-form=line]');
  if (!form) return;
  e.preventDefault();
  const text = form.w.value.trim(), n = norm(text).trim();
  if (n.length < 3) { toast('Գրեք առնվազն երեք տառ'); return; }
  if (CFG.lines.length >= 16) { toast('Ուղղությունները շատ են. նախ հեռացրեք մեկը'); return; }
  const stem = n.split(' ').map(w => (w.length >= 8 ? w.slice(0, -2) : w)).join(' ');
  CFG.lines.push({name: text.charAt(0).toUpperCase() + text.slice(1), keys: [stem]});
  S.guessed = false;
  reapply();
  toast(`Ավելացվեց՝ ${text}`);
});
let resizeTimer = 0, lastW = innerWidth;
addEventListener('resize', () => { if (innerWidth === lastW) return; lastW = innerWidth; clearTimeout(resizeTimer); resizeTimer = setTimeout(() => { if (D && S.tab === 'us' && CFG.tins.length) drawChart(); }, 150); });

/* Left open in a pocket, the page looks for newer data when it is looked at again. */
let seen = Date.now();
document.addEventListener('visibilitychange', async () => {
  if (document.hidden) { seen = Date.now(); return; }
  if (!D || Date.now() - seen < 20 * 60e3 || S.stack.length || S.setup) return;
  try {
    const [m, t] = await Promise.all([getJSON('../data/k/meta.json'), getJSON('../data/tenders.json').catch(() => null)]);
    if (m.updated === D.meta.updated && (!t || t.meta.updated === D.tmeta.updated)) return;
    await load();
    apply();
    if (!S.stack.length) render({plate: true});
  } catch { /* no connection now: what is on screen stays */ }
});

/* ---------- start ---------- */
async function boot() {
  const deep = /^#t(\d{1,9})$/.exec(location.hash);          // a tender sent here from the full list
  readConfig();
  const SEGS = {today: ['open', 'next', 'done'], rivals: ['met', 'line'], buyers: ['ours', 'new']};
  for (const t in SEGS) { const v = store.get('seg.' + t); if (SEGS[t].includes(v)) S.seg[t] = v; }
  paintSig();
  try {
    await load();
  } catch (err) {
    console.error(err);
    $('#loadline').classList.add('done');
    setPlate('<h2 class="title">Տվյալները չբեռնվեցին</h2><p class="lead">Ստուգեք կապը և փորձեք կրկին։</p>', true);
    $('#view').innerHTML = `<div class="actions" style="margin-top:1.25rem"><button class="btn" type="button" onclick="location.reload()">Կրկին փորձել</button></div>`;
    return;
  }
  S.guessed = !CFG.lines;
  apply();
  $('#loadline').classList.add('done');
  if (!CFG.tins.length) return firstRun();
  saveConfig();
  $('#tabs').hidden = false; $('#b-set').hidden = false;
  render();
  if (!CALM) $('#sheen').classList.add('go');
  if (deep && OPEN.some(t => t.id === +deep[1])) openSheet('tender', deep[1]);
}
boot();
})();
