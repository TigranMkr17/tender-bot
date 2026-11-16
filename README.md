# Մրցույթներ: Armenian tender alerts in Telegram

A Telegram bot that reads the state e-auction register (eauction.armeps.am) and tells you, in plain Armenian, which tenders are new and which are about to close. One button in the chat opens a small app with every open tender: tabs, sector filter, search, saved tenders, key dates and a direct link to the invitation.

It needs no server. GitHub runs it on a schedule and hosts the app page, both free.

## Set it up (about 5 minutes)

1. **Create the bot.** In Telegram open `@BotFather`, send `/newbot`, choose a name (for example `Մրցույթներ`) and a username ending in `bot`. BotFather replies with a token that looks like `1234567890:AA...`. Keep it private.
2. **Put these files in a GitHub repository.** Create a new **public** repository and upload everything in this folder, including the hidden `.github` folder.
3. **Give GitHub the token.** In the repository: Settings → Secrets and variables → Actions → New repository secret. Name: `TELEGRAM_BOT_TOKEN`. Value: the token from step 1.
4. **Turn on the app page.** Settings → Pages → Source: *Deploy from a branch* → Branch: `main`, folder: `/docs` → Save. After a minute the app is live at `https://<your-username>.github.io/<repository-name>/`.
5. **Start it.** Open your bot in Telegram and press **Start**. Then in the repository open Actions → Tenders → Run workflow. Within a minute the bot sends a welcome and the first message.

Anyone else who should get the messages only has to open the bot and press Start. They are answered within the hour.

## When it runs (Yerevan time)

| When | What |
|---|---|
| 09:07, Monday to Saturday | Morning message: new tenders, what closes in the next 3 days, what closes today |
| 13:07, Monday to Friday | Quiet refresh of the app |
| 18:07, Monday to Friday | Evening message, only if new tenders were published during the day |
| Every hour | Answers people who pressed Start or sent `/stop` |

GitHub sometimes starts scheduled jobs 5 to 30 minutes late. To change the times, edit the `cron` lines in `.github/workflows/tenders.yml`. They are in UTC: Yerevan time minus 4 hours.

## Change things

- **Highlight your own topics.** Put words in `config.json`, for example `{"focus_keywords": ["շնչառական", "հակագազ"]}`. Tenders whose title contains one of them are listed first in the message.
- **Send to a group or channel as well.** Add the bot to it, then add a secret `TELEGRAM_CHAT_ID` with the chat's numeric id (several ids separated by commas).
- **Use your own address for the app.** Add a repository *variable* `APP_URL`.
- **Sector words.** The lists are in `bot/textproc.py` under `SECTORS`.

## If something goes wrong

- **No message arrived.** Open Actions and look at the latest run. If it says nobody pressed Start, press Start in the bot and run the workflow again. If it mentions the token, repeat step 3.
- **A run failed with "no tender rows were found".** The portal changed its page layout or was down. The page it received is attached to the failed run as `debug`. Titles are read by shape rather than by CSS class, so small changes are tolerated; a full redesign needs an update to `bot/armeps.py`.
- **Messages stopped after a long time.** GitHub pauses schedules in repositories with no activity for 60 days. The bot's own daily updates count as activity, but if it ever happens, open Actions and press Enable.

## What it does not cover yet

- Only ARMEPS electronic auctions. Open tenders and price quotations announced only on gnumner.am, and donor or private tenders, are not included.
- It shows what the notice page shows. Estimated prices and the contents of each lot are inside the invitation ZIP, which the app links to.
- The first live run is the real test of the reader. It was built from the portal's pages as seen on 13 November 2026 and tested offline against rebuilt copies of them (`python -m unittest discover -s tests`).

## How it is built

```
bot/armeps.py      reads the list and notice pages (Python standard library only)
bot/textproc.py    official wording -> short subject, readable buyer name, sector
bot/store.py       bot/state/tenders.json (everything the bot knows) and the slim
                   docs/data/tenders.json the app downloads
bot/digest.py      the Telegram messages
bot/telegram.py    Bot API calls; the list of chats, stored encrypted
bot/main.py        entry point:  python -m bot.main --mode digest|refresh|inbox [--dry-run]
docs/index.html    the app (one file, no build step)
docs/fonts/        Noto Sans Armenian (SIL Open Font License, see OFL.txt)
tools/, tests/     sample notices and offline tests
DESIGN.md          the app's colours, type and components
```

The app opens from a copy of the last data kept on the device, then refreshes in the background. Long lists are drawn a screenful at a time, so several hundred tenders stay quick on an older phone.

The repository is public, so the list of people who pressed Start is stored encrypted in `bot/state/subscribers.enc`. The key is derived from the bot token, which only GitHub's secret store holds. If you ever replace the token, everyone presses Start once more.

Saved tenders stay on each person's own device (and in their Telegram cloud storage); the bot never sees them.

Icons are from [Lucide](https://lucide.dev) (ISC License).
