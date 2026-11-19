/* The tenders site without a connection, and at once with one (a service worker, for the whole site: the tenders
   page and «Մեր դաշտը» in my/).

   Pages, fonts and icons come from this phone's copy at once; a fresh copy is fetched behind them and kept for the
   next visit. When a page has changed, the open page is told, and reloads if the reader has not started reading.
   Data (data/...) is asked for first: the answer is used when it comes within a few seconds, this phone's last copy
   when it does not, or when there is no connection at all.

   To change how this works, change the file: a phone fetches it again on its next visit and replaces the old one. */
const VERSION = 1;
const SHELL = `shell-${VERSION}`, DATA = `data-${VERSION}`;
const CORE = ['./', 'manifest.webmanifest', 'fonts/nsa-armenian.woff2', 'fonts/nsa-latin.woff2',
  'fonts/nse-armenian.woff2', 'fonts/nse-latin.woff2', 'fonts/bodoni-num.woff2',
  'icons/icon.svg', 'icons/favicon-32.png', 'icons/apple-touch-icon.png', 'icons/icon-192.png'];
const WAIT = 3500;            // ms data may take before this phone's copy is used instead
const KEEP = 300;             // data files kept on the phone
const ROOT = new URL('./', self.registration.scope).pathname;
let puts = 0;                 // copies saved since the worker started: every 25th, the oldest are let go

self.addEventListener('install', e => {
  e.waitUntil(caches.open(SHELL).then(c => c.addAll(CORE)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(k => k !== SHELL && k !== DATA).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener('fetch', e => {
  const req = e.request, url = new URL(req.url);
  if (req.method !== 'GET' || url.origin !== location.origin || !url.pathname.startsWith(ROOT)) return;
  if (url.pathname.startsWith(ROOT + 'data/')) e.respondWith(data(e, req));
  else if (req.mode === 'navigate') e.respondWith(page(e, url));
  else e.respondWith(asset(e, req));
});

/* a page: the same for ./ and ./index.html, whatever follows ? or # */
const pageKey = url => url.origin + url.pathname.replace(/index\.html$/, '');

async function page(e, url) {
  const cache = await caches.open(SHELL), key = pageKey(url), kept = await cache.match(key);
  const reader = e.resultingClientId || e.clientId;
  const was = kept ? kept.clone().text() : Promise.resolve(null);   // read now: the page is about to use the copy
  const fresh = fetch(url.href, {cache: 'no-cache', credentials: 'same-origin'}).then(async res => {
    if (!res.ok || res.type !== 'basic') return res;
    const body = await res.clone().text(), before = await was;
    await cache.put(key, res.clone());
    if (before !== null && before !== body) await tell(reader, 'page-updated');
    return res;
  });
  if (kept) {
    e.waitUntil(fresh.catch(() => null));
    return kept;
  }
  try {
    return await fresh;
  } catch (err) {                                           // no copy of this page and no connection
    return (await cache.match(pageKey(new URL(ROOT, url)))) || new Response(
      '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width">' +
      '<p style="font:16px system-ui;padding:2rem">Ինտերնետ կապ չկա։ Միացեք և փորձեք նորից։</p>',
      {headers: {'Content-Type': 'text/html; charset=utf-8'}});
  }
}

/* the page being opened may not exist yet when its fresh copy arrives: wait for it, three seconds at most */
async function tell(id, type) {
  for (let i = 0; id && i < 30; i++) {
    const reader = await self.clients.get(id);
    if (reader) { reader.postMessage({type}); return; }
    await new Promise(r => setTimeout(r, 100));
  }
}

/* fonts, icons, the group page's script and style: this phone's copy at once, refreshed behind it */
async function asset(e, req) {
  const cache = await caches.open(SHELL), kept = await cache.match(req);
  const fresh = fetch(req).then(res => (res.ok && res.type === 'basic'
    ? cache.put(req, res.clone()).then(() => (++puts % 25 === 0 ? trim(cache, 80) : null)).then(() => res, () => res) : res));
  if (kept) {
    e.waitUntil(fresh.catch(() => null));
    return kept;
  }
  return fresh;
}

/* data: the network first, this phone's copy when the network is slow or gone */
async function data(e, req) {
  const cache = await caches.open(DATA);
  const fresh = fetch(req).then(res => {
    if (!res.ok) return res;
    return cache.put(req.url, res.clone()).then(() => (++puts % 25 === 0 ? trim(cache) : null)).then(() => res, () => res);
  });
  try {
    const res = await Promise.race([fresh, new Promise(r => setTimeout(r, WAIT, null))]);
    if (res) return res;
  } catch (err) { /* no connection: this phone's copy, below */ }
  const kept = await cache.match(req.url);
  if (kept) {
    e.waitUntil(fresh.catch(() => null));                  // a late answer still refreshes the copy
    return kept;
  }
  return fresh;
}

/* the oldest entries go first: an old version of a script, a tender page not opened for long */
async function trim(cache, keep = KEEP) {
  const keys = await cache.keys();
  await Promise.all(keys.slice(0, Math.max(0, keys.length - keep)).map(k => cache.delete(k)));
}
