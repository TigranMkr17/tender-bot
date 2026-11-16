# Մրցույթներ: Armenian tenders, easy to look through

A website that reads the state e-auction register (eauction.armeps.am) and shows every open tender in plain Armenian: what is bought, who buys it, when bids close. Two lists (new, and all open ones by deadline), a search box, a sector filter, and for each tender the key dates and a direct link to the invitation. On a wide screen the list and the chosen tender sit side by side.

It needs no server. GitHub reads the register on a schedule and hosts the page, both free.

## Set it up

1. **Put these files in a GitHub repository.** Create a new **public** repository and upload everything in this folder, including the hidden `.github` folder.
2. **Turn on the page.** Settings → Pages → Source: *Deploy from a branch* → Branch: `main`, folder: `/docs` → Save. After a minute the site is live at `https://<your-username>.github.io/<repository-name>/`.
3. **Read the register once.** Actions → Tenders → Run workflow. After a few minutes the site shows today's tenders.

## When it reads the register (Yerevan time)

| When | What |
|---|---|
| 08:52, Monday to Saturday | Reads the register |
| Every hour from 09:37 to 17:37, Monday to Friday | Reads the register |
| 17:52, Monday to Friday | Reads the register |

GitHub sometimes starts scheduled jobs 5 to 30 minutes late. To change the times, edit the `cron` lines in `.github/workflows/tenders.yml`. They are in UTC: Yerevan time minus 4 hours.

## Optional: messages in Telegram

The same data can be sent as a Telegram message: new tenders and the day's deadlines at about 09:00, and at about 18:00 on days when something new was published.

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

- Only ARMEPS electronic auctions. Open tenders and price quotations announced only on gnumner.am, and donor or private tenders, are not included.
- It shows what the notice page shows. Estimated prices and the contents of each lot are inside the invitation ZIP, which the site links to.
- The Telegram messages have only been tested against a stand-in for Telegram (`python -m unittest discover -s tests`); the reader itself runs against the live register.

## How it is built

```
bot/armeps.py      reads the list and notice pages (Python standard library only)
bot/textproc.py    official wording -> short subject, readable buyer name, sector
bot/store.py       bot/state/tenders.json (everything the bot knows) and the slim
                   docs/data/tenders.json the app downloads
bot/digest.py      the Telegram messages
bot/telegram.py    Bot API calls; the list of chats, stored encrypted
bot/main.py        entry point:  python -m bot.main --mode digest|refresh|inbox [--dry-run]
docs/index.html    the site (one file, no build step)
docs/fonts/        Noto Sans Armenian (SIL Open Font License, see OFL.txt)
tools/, tests/     sample notices and offline tests
DESIGN.md          the site's colours, type and components
```

The site opens from a copy of the last data kept on the device, then refreshes in the background. Long lists are drawn a screenful at a time, so several hundred tenders stay quick on an older phone.

The repository is public, so the list of people who pressed Start is stored encrypted in `bot/state/subscribers.enc`. The key is derived from the bot token, which only GitHub's secret store holds. If you ever replace the token, everyone presses Start once more.

Icons are from [Lucide](https://lucide.dev) (ISC License).
