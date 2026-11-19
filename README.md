# Մրցույթներ: Armenian tenders, easy to look through

A website that reads the state e-auction register (eauction.armeps.am) and shows every open tender in plain Armenian: what is bought, who buys it, when bids close. Three lists (new, all open ones by deadline, and finished ones), a search box, a sector filter, and for each tender the key dates and a direct link to the invitation. On a wide screen the list and the chosen tender sit side by side.

It also opens what the register keeps in files and on separate pages:

- **Inside a tender**: the lots with quantities and descriptions, the delivery address and term, what a bid has to contain, the guarantees a winner provides, and the buyer's contact. All read from the invitation.
- **How finished tenders went**: the estimated price, every bid, who came first and by how much the auction lowered the price.
- **Last time**: for each lot of an open tender, the latest purchase of the same thing, by the same buyer where there is one.
- **Who takes part**: a page for every company (where it bids, how often it comes first, how far below the estimate) and for every buyer (open tenders, past ones, who usually comes first).

It needs no server. GitHub reads the register on a schedule and hosts the page, both free.

## Set it up

1. **Put these files in a GitHub repository.** Create a new **public** repository and upload everything in this folder, including the hidden `.github` folder.
2. **Turn on the page.** Settings → Pages → Source: *Deploy from a branch* → Branch: `main`, folder: `/docs` → Save. After a minute the site is live at `https://<your-username>.github.io/<repository-name>/`.
3. **Read the register once.** Actions → Tenders → Run workflow. After a few minutes the site shows today's tenders.
4. **Give it a clock.** Settings → Environments → `clock` (it appears after the first run; otherwise *New environment*, named `clock`) → tick **Wait timer** and enter `175` → *Save protection rules*. From then on the site is updated at 08:50, 11:50, 14:50 and 17:50, Monday to Saturday.

## On a phone's Home Screen

The site has its own icon, so it can sit among the apps.

- **iPhone**: open the site in Safari → Share → *Add to Home Screen*.
- **Android**: open it in Chrome → ⋮ → *Add to Home screen*.

A phone keeps the icon it was given when the shortcut was made. If the icon changes later, remove the shortcut and add it again.

From the Home Screen the site opens as an app, without the browser's bar. It opens at once and works without a connection: a service worker (`docs/sw.js`) keeps the pages, fonts and icons on the phone and refreshes them behind the scenes; data is asked for first, and the phone's last copy is used after 3.5 seconds or with no connection, and the list then says so. A page that changed reloads itself if the reader has not opened anything yet; otherwise the new one shows next time.

## Where the tenders come from

Two ARMEPS systems, both public and read without logging in:

- **eauction.armeps.am**: electronic auctions (`bot/armeps.py`).
- **www.armeps.am/epps**: everything else open for bids: price quotations, open and urgent tenders, two-stage and framework procedures, grant competitions (`bot/epps.py`). EPPS keeps its search in the visitor's session and pages it 75 at a time; the reader takes the pager's key from the first results page, then reads the page of every new call (and every call again after 20 hours, in case a deadline moved) for its code, buyer, procedure, deadline, question period, opening time and publication time. A call on both systems is shown once, as the auction. EPPS also keeps listing some old calls whose deadline passed long ago; once such a call leaves the site it is remembered (`epps_done` in `bot/state/tenders.json`) and not added again.

`python -m bot.epps --probe 5` (or the *EPPS look* workflow) reads the list and five calls and prints what the reader understood, without saving anything.

**What keeps the list right.**

- EPPS says how many calls it has. A list that comes back shorter is asked for again once, as a new visitor; if it stays short it adds and updates calls but never closes one (on 19 Nov 2026 a short list closed 222 calls before this rule existed).
- The auction list ordered by number is walked down to the oldest open auction at every update. An open auction missing from two whole walks in a row has been taken off ARMEPS's list (cancelled or suspended, most likely): it stops looking open, and its page says so. One that comes back is open again. A walk cut short by an error decides nothing.
- **The safety net** (`hold_sudden_closing` in `bot/main.py`): a run that would close more than 15 open tenders (or 5% of them) before their deadlines keeps them open and remembers them; only a second run in a row that closes mostly the same ones is believed.
- The page knows the update times and says so as soon as one is late (45 minutes after its slot).

## Past prices

Every open tender's page shows **«Նման պայմանագրեր»**: the contracts most like it in the contracts register (every procedure, since October 2025), who got each one, for how much, against what estimate, and how far below the estimate such contracts usually close. `bot/past.py` works them out at each update from `docs/data/k/` and writes `docs/data/p/<id % 16>.json`, so a phone loads a few kilobytes. Likeness is by the rare words of the subject: words about buying, places, and people's names are left out; the same buyer counts a little more; a long subject must share two words with a contract. Sole proprietors are not named. Auctions also keep «Նախորդ անգամ», the earlier auction results for the same item codes.

## Search

The search box takes Armenian or Latin letters typed the usual way (`mankapartez`, `qaxaqapetaran`, `dexorayq`): text and query both become a rough key of how they sound, where letters people mix up fall together (տ/թ, կ/ք, ր/ռ, ե/է, խ/ղ, ց/ծ/չ/ճ...). When nothing matches as written, one letter may be wrong in each long word, and the list says the matches are approximate.

## A company's own view: `my/`

`https://<your-username>.github.io/<repository-name>/my/` is a second page, built on the contracts register (every signed contract, whatever the procedure). Give it up to three companies and the things they sell, and it shows:

- **Այսօր**: the open e-auctions that fit, with a mark on the ones from a buyer the companies have already sold to; what was signed a year ago in the days now ahead (the same buyers may buy again); and what was signed in the last 30 days, with whom and at what price.
- **Մենք**: the companies' own contracts month by month, and the tenders they took part in where the contract went to someone else.
- **Մրցակիցներ**: the suppliers met in the same tenders, and who signs the most in each line of goods.
- **Գնորդներ**: who has bought from the companies and what share of that buyer's purchases they hold, and who buys the same things from others.

Tap anything for its detail: a buyer's past contracts in the same line and how far below the estimate they were signed, a rival's usual discount and main buyers, a tender's participants.

The page is the same for everyone and holds no names. Which companies to show comes from its address: `?c=` carries the tax numbers and `&w=` the lines, and *Settings → Copy link* writes that address out. The choice is also kept on the device, so the plain address opens the same view next time. Nothing is sent anywhere, and everything shown is already public in the register; the address only saves the typing. It is not a password: anyone who has the link sees the same page.

With no choice made, the page opens on the group in `docs/my/home.json`. For that group it reads only `data/k/home.json` (about 60 KB), its slice of the year, which the contracts run writes every morning; any other choice, or a search for a company, fetches the whole year first.

A line is a name and the beginnings of the words that belong to it, so «կահույք» also finds «կահույքի». Sole proprietors are counted together as one unnamed row in every ranking.

## When it reads the register (Yerevan time)

**On time: 08:50, 11:50, 14:50 and 17:50, Monday to Saturday.** Each time it reads the register and takes a 15-minute look inside new invitations and at tenders that have just finished. Every night at 20:50, 23:50, 02:50 and 05:50 it reads for 170 minutes further back through the past year of finished tenders, so the reading hardly pauses until morning. At 05:50 it also reads the last 45 days of the contracts register, which takes a few minutes.

GitHub's own schedule cannot be relied on for this: on this repository it started only a few of the jobs it was asked to, some of them hours late. So the `Clock` workflow keeps the time. GitHub holds each of its runs for 175 minutes (the wait timer of step 4, during which nothing runs); the run wakes a few minutes before the next of eight moments a day, starts the next run and whatever is due at that moment. The update jobs start the clock if they find none, so it starts by itself and mends itself. Without the wait timer it starts nothing. To stop it: Actions → Clock → ⋯ → Disable workflow. To change the times, edit `UPDATES` and `NIGHTS` in `bot/clock.py`; they are in UTC, Yerevan time minus 4 hours.

**And whenever GitHub's schedule does fire**, as a second way in:

| When | What |
|---|---|
| 08:52, Monday to Saturday | Reads the register |
| Every hour from 09:37 to 17:37, Monday to Friday | Reads the register |
| 17:52, Monday to Friday | Reads the register |
| Every hour from 09:17 to 18:17, Monday to Friday | A short look inside new invitations and at tenders that have just finished |
| 21:17, 23:17, 01:17 and 03:17, every night | Long runs: finished tenders, back through the past 400 days |

These are the `cron` lines in `.github/workflows/tenders.yml` and `history.yml`, in UTC.

The past year is read a part each night, because the register answers slowly and resets hurried connections. Until it is done, the «Արդյունքներ» list says how far back it reaches. To read more at once: Actions → History → Run workflow, and give it up to 140 minutes.

## Optional: messages in Telegram

The same data can be sent as a Telegram message: new tenders and the day's deadlines at about 09:00, and at about 12:00, 15:00 and 18:00 whatever was published since the last message (nothing when nothing is new). Every tender in a message opens its page on the site; EPPS calls say which procedure they are; tenders in the lines of «Մեր դաշտը» (`docs/my/home.json`) come first, with a star.

1. In Telegram open `@BotFather`, send `/newbot`, choose a name and a username ending in `bot`. BotFather replies with a token. Keep it private.
2. In the repository: Settings → Secrets and variables → Actions → New repository secret. Name: `TELEGRAM_BOT_TOKEN`. Value: the token.
3. Open the bot and press **Start**. Anyone who presses Start is answered within the hour and gets the messages from then on; `/stop` ends them.

## Change things

- **Highlight your own topics in the Telegram message.** Put words in `config.json`, for example `{"focus_keywords": ["շնչառական", "հակագազ"]}`. Tenders whose title contains one of them are listed first.
- **Send the message to a group or channel as well.** Add the bot to it, then add a secret `TELEGRAM_CHAT_ID` with the chat's numeric id (several ids separated by commas).
- **Use your own address for the site.** Add a repository *variable* `APP_URL` so the Telegram button opens it.
- **Sector words.** The lists are in `bot/textproc.py` under `SECTORS`.

## If something goes wrong

- **The site shows old data.** Open Actions and look at the latest run. Press Run workflow to read the register now.
- **No Telegram message arrived.** If the latest run says nobody pressed Start, press Start in the bot and run the workflow again. If it mentions the token, add the secret again.
- **A run failed with "no tender rows were found".** The portal changed its page layout or was down. The page it received is attached to the failed run as `debug`. Titles are read by shape rather than by CSS class, so small changes are tolerated; a full redesign needs an update to `bot/armeps.py`.
- **Updates stopped after a long time.** GitHub pauses schedules in repositories with no activity for 60 days. The daily data updates count as activity, but if it ever happens, open Actions and press Enable.

## What it does not cover yet

- Only ARMEPS: its electronic auctions and the calls on EPPS. Tenders announced only on gnumner.am, and donor or private tenders, are not included.
- Neither system publishes most tenders' estimated price before the bids, so an open tender shows the prices of earlier purchases instead.
- The register names no winner. The site shows who came first in the auction and which bids were turned down; the contract is the buyer's decision, and while it is being made a tender is marked «Հաղթողը որոշվում է» and read again every two days.
- "The same thing" is judged by the item code and the lot's name. Quantities differ from one purchase to the next, so compare prices per unit where the site shows them.
- Sole proprietors are people, not companies: they are named only in the record of the tender they bid in, and have no page of their own. Bidders' application files are not downloaded. Buyers' bank details in an invitation are not read.
- Bids are filled in and signed in ARMEPS itself, so the site lists what a bid needs but does not prepare or submit one.
- The Telegram messages have only been tested against a stand-in for Telegram (`python -m unittest discover -s tests`); the reader itself runs against the live register.

## How it is built

```
bot/armeps.py      reads the list and notice pages (Python standard library only)
bot/textproc.py    official wording -> short subject, readable buyer name, sector
bot/store.py       bot/state/tenders.json (everything the bot knows) and the slim
                   docs/data/tenders.json the app downloads
bot/invite.py      what is inside an invitation ZIP: lots, quantities, guarantees, contact
bot/docx_read.py   reads paragraphs and tables out of a .docx (standard library only)
bot/results.py     the bids on a finished tender's page
bot/deep.py        the slow job:  python -m bot.deep --minutes 30
                   writes docs/data/t/<id>.json (one open tender), docs/data/lots.json,
                   and docs/data/h/ (finished tenders, companies, buyers, item codes)
bot/digest.py      the Telegram messages
bot/telegram.py    Bot API calls; the list of chats, stored encrypted
bot/main.py        entry point:  python -m bot.main --mode digest|refresh|inbox [--dry-run]
bot/clock.py       keeps the time for the Clock workflow: when to wake, what to start
bot/contracts.py   the contracts register: who signed what with whom, for every procedure
                   (bot/state/contracts/, one contract a line; docs/data/k/ for the site)
docs/index.html    the site (one file, no build step)
docs/my/           a company's own view of the contracts register: index.html, app.css, app.js
                   (no build step; the seal on its icon is drawn by the same code as the page's)
docs/fonts/        Noto Sans Armenian and Noto Serif Armenian (SIL Open Font License, see OFL.txt),
                   and the digits of Bodoni Moda (same licence, see OFL-BodoniModa.txt)
docs/icons/        the mark, cut for a phone's Home Screen and for browser tabs;
                   docs/manifest.webmanifest gives phones the site's name and these files
tools/mark.py      draws the mark and cuts the files in docs/icons/
tools/look.py      prints what is on a page as a GitHub runner sees it (the Look workflow)
tools/, tests/     sample notices and offline tests
DESIGN.md          the site's colours, type and components
```

The site opens from a copy of the last data kept on the device, then refreshes in the background. Long lists are drawn a screenful at a time, so several hundred tenders stay quick on an older phone. What belongs to one screen (a tender's lots, a company's bids) is a small file of its own, fetched when that screen is opened.

The repository is public, so the list of people who pressed Start is stored encrypted in `bot/state/subscribers.enc`. The key is derived from the bot token, which only GitHub's secret store holds. If you ever replace the token, everyone presses Start once more.

Icons are from [Lucide](https://lucide.dev) (ISC License).
