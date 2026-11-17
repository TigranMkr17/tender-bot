---
name: Մրցույթներ
description: Armenian state tenders as dated notices on paper sheets, a site for looking, finding and reading
colors:
  ground: "#E8EAE4"
  sheet: "#FCFCFA"
  sheet-2: "#F0F1ED"
  seg: "#D8DBD3"
  ink: "#14161A"
  ink-2: "#454A53"
  ink-3: "#5F656F"
  rule: "#E0E2DB"
  press-blue: "#1B338A"
  press-blue-deep: "#132669"
  accent: "#1F3A93"
  on-press: "#FFFFFF"
  on-press-2: "#C9D3F7"
  tile: "#DFE5F8"
  tile-ink: "#1B338A"
  critical: "#B4231A"
  critical-tile: "#C22B21"
  warning: "#855600"
  warning-tile: "#F1BC4B"
  on-warning-tile: "#2B1D00"
  night-ground: "#0C0E12"
  night-sheet: "#171A20"
  night-ink: "#ECEBE5"
  night-shell: "#182B6E"
  night-accent: "#9DB4FF"
  night-tile: "#1F2B55"
typography:
  nameplate:
    fontFamily: "Noto Sans Armenian, Segoe UI, system-ui, sans-serif"
    fontSize: "2.25rem"
    fontWeight: 800
    lineHeight: 1.08
    letterSpacing: "normal"
  tile-numeral:
    fontFamily: "Noto Sans Armenian, Segoe UI, system-ui, sans-serif"
    fontSize: "1.625rem"
    fontWeight: 800
    lineHeight: 1
    letterSpacing: "normal"
  heading:
    fontFamily: "Noto Sans Armenian, Segoe UI, system-ui, sans-serif"
    fontSize: "1.0625rem"
    fontWeight: 750
    lineHeight: 1.3
    letterSpacing: "normal"
  row-title:
    fontFamily: "Noto Sans Armenian, Segoe UI, system-ui, sans-serif"
    fontSize: "1.0625rem"
    fontWeight: 650
    lineHeight: 1.28
    letterSpacing: "normal"
  body:
    fontFamily: "Noto Sans Armenian, Segoe UI, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.45
    letterSpacing: "normal"
  meta:
    fontFamily: "Noto Sans Armenian, Segoe UI, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.4
    letterSpacing: "normal"
  hero-title:
    fontFamily: "Noto Sans Armenian, Segoe UI, system-ui, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 750
    lineHeight: 1.2
    letterSpacing: "normal"
  due-numeral:
    fontFamily: "Noto Sans Armenian, Segoe UI, system-ui, sans-serif"
    fontSize: "2.125rem"
    fontWeight: 800
    lineHeight: 1
    letterSpacing: "normal"
  due-line:
    fontFamily: "Noto Sans Armenian, Segoe UI, system-ui, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 750
    lineHeight: 1.2
    letterSpacing: "normal"
  day-heading:
    fontFamily: "Noto Sans Armenian, Segoe UI, system-ui, sans-serif"
    fontSize: "1.1875rem"
    fontWeight: 750
    lineHeight: 1.25
    letterSpacing: "normal"
  tab:
    fontFamily: "Noto Sans Armenian, Segoe UI, system-ui, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 650
    lineHeight: 1.2
    letterSpacing: "normal"
  count:
    fontFamily: "Noto Sans Armenian, Segoe UI, system-ui, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "normal"
  tile-label:
    fontFamily: "Noto Sans Armenian, Segoe UI, system-ui, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 700
    lineHeight: 1.1
    letterSpacing: "normal"
rounded:
  hairline: "1px"
  tick: "4px"
  focus: "6px"
  control: "10px"
  tile: "12px"
  field: "14px"
  button: "14px"
  sheet: "16px"
  shell: "20px"
  pill: "20px"
spacing:
  gutter: "16px"
  row: "12px"
  sheet-gap: "12px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.on-press}"
    rounded: "{rounded.button}"
    padding: "8px 16px"
    height: "52px"
  button-secondary:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.ink}"
    rounded: "{rounded.button}"
    padding: "8px 16px"
    height: "52px"
  chip:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.ink-2}"
    rounded: "{rounded.pill}"
    padding: "0 14px 0 12px"
    height: "40px"
  chip-selected:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.on-press}"
  date-tile:
    backgroundColor: "{colors.tile}"
    textColor: "{colors.tile-ink}"
    rounded: "{rounded.tile}"
    width: "54px"
    height: "60px"
  date-tile-soon:
    backgroundColor: "{colors.warning-tile}"
    textColor: "{colors.on-warning-tile}"
  date-tile-last-day:
    backgroundColor: "{colors.critical-tile}"
    textColor: "{colors.on-press}"
  search-field:
    backgroundColor: "#FFFFFF"
    textColor: "{colors.ink}"
    rounded: "{rounded.field}"
    height: "48px"
---

# Design System: Մրցույթներ

## Overview

Dated notices on paper sheets. Every tender leads with a date tile, like the leaf of a wall calendar: weekday, a large day numeral, month. Days are gathered on white sheets that lie on a newsprint-grey board, under a press-blue header with a halftone dot screen, the texture of printed paper. The navigation is the standard furniture of a phone app: search, a segmented tab bar, filter chips, a list, a pushed notice view.

The reader is a non-technical business owner on a phone, usually in daylight. Body text is 16px, tap targets are 44px or more, and nothing relies on colour alone.

## Colors

- **Board and sheets.** `ground` is the board, `sheet` the paper. Neutrals lean slightly cool and green, like newsprint, never cream.
- **Press blue** is the one spot ink: the header, the notice hero, selection, the primary action, and (as a tint) the date tiles and icon tiles.
- **States.** A red tile means the deadline is today or tomorrow, an amber tile three days or less. They always come with words («վաղը, մինչև 10:00»), and nothing else on the screen may be red or amber.

### Named Rules

- **Two inks.** A screen prints in ink and press blue. A third colour may only be a deadline state.

## Typography

One family, Noto Sans Armenian (variable weight and width, self-hosted). The width axis gives two voices: condensed and heavy for the name, dates and headings (66 to 80%), normal width for reading.

### Hierarchy

Name 36/800 condensed; notice title 24/750; deadline numeral 34/800 with a 20/750 line beside it; tile numeral 26/800 condensed; day headings 19/750 and section headings 17/750 at 80% width; row titles 17/650 at 88%; body 16/400; tabs 15/650; meta 14/400; counts 13/700; tile labels 12/700. Sizes are fixed rem steps; the «ԱԱ» control scales the root to 112.5% and 125%.

### Named Rules

- **Never uppercase Armenian with CSS.** `text-transform: uppercase` turns «և» into «ԵՒ», which is wrong in modern spelling. Capitals are written out in the source (ԵՐՔ, ՆՈՅ, ԺԱՄԸ).

## Layout

On a phone: one column, at most 40rem wide, 16px gutters. The header scrolls away; the tab bar and day headings stick. A row is tile, text, and a small chevron. Titles clamp to two lines and buyers to one; the notice view shows everything in full. Long lists are drawn a screenful at a time.

From 64rem up the page is a fixed frame: the header across the top, the list in a 30rem column on the left, the chosen notice beside it. The list and the notice scroll separately, and a notice is always open. From 80rem the sector chips wrap above the notice; below that they stay one scrolling row over the list.

## Elevation & Depth

One elevation: a sheet. In the light theme a sheet carries a soft low shadow and no border; in the dark theme it is a lighter surface with no shadow. Rows inside a sheet are separated by hairlines that start after the tile. The toast is the only thing that floats above sheets.

## Shapes

Tab segments 10px, tiles 12px, fields and buttons 14px, sheets 16px, the header's bottom corners and the notice hero 20px, chips and tab counts fully rounded. Small parts: the progress bar 4px, focus rings 6px.

## Components

### Buttons

Primary: press-blue fill. Secondary: a sheet. Both 52px tall with a Lucide icon before the label; they shrink slightly when pressed.

### Chips

40px pills on sheet white, each with its sector icon and a count; the selected one is filled press blue.

### Inputs / Fields

One search field in the header: white on blue, 48px, with a clear button once text is typed. Typing waits for a short pause before the list redraws.

### Navigation

A three-part segmented control, «Նոր», «Բոլորը» and «Արդյունքներ», with a sliding thumb sized to each label; the active part's count turns press blue. On a phone every screen (a tender, a finished tender, a company, a buyer) is pushed over the last and the back button undoes one step; where the browser supports view transitions the row's date tile travels into the notice. On a wide screen the open row is tinted and its tile filled press blue, and the pane beside the list gets its own «Հետ» once it has gone a level deeper.

Names lead somewhere: a buyer's name opens the buyer, a bidder's name opens the company, a past purchase opens that tender's result.

### Date tile

The signature component. In «Նոր» it shows weekday, day numeral and month; in «Բոլորը», where the day is already the heading, it shows «ԺԱՄԸ» and the time. In the notice view it is larger and sits beside the deadline, above a bar that shows how much of the bidding period has passed. In «Արդյունքներ» the tile says «ԳԻՆԸ» and how far the auction took the price below the estimate; a tender that failed or was cancelled gets a grey tile with a dash.

### Price bar

The estimate is the full track in tile blue; the first-place price is the press-blue fill. One bar per comparison, 8px, 10px in a result's summary. It is the only chart on the site.

### Lot rows and bids

A lot is a number badge, a name and, at the right, a quantity; its description opens in place. A bid is its place, the bidder and the price, with the price before tax and the opening price in a smaller line beneath. First place gets a filled badge and bold type; a rejected bid is grey with its price struck through.

### Three figures

A company and a buyer open with three figures in quiet tiles (tenders, lots, first places). Supporting facts, not a headline: they sit in a sheet under the name.

## Mark

The letter «Մ» as a paper ribbon. The band runs down, round and up; at the top of the right stem it folds over to the right, and the back of the band, the letter's arm, ends in a swallowtail like a page marker. The band is white and its back amber, on press blue with the header's dot screen growing toward the lower right corner. `tools/mark.py` draws it and cuts the files in `docs/icons/`.

- **On a phone's Home Screen** the icon is square and runs to the edges; the phone rounds it. Android cuts a shape of its own, so its file keeps the letter at 80% of the size.
- **In a browser tab** the letter is larger and the dot screen is left out.
- **Amber stays in the mark.** On a screen amber still means a deadline three days away or less, so the header carries the name in type and no mark.

## Motion

Motion reports what happened. The one composed moment is a result opening: the bar falls from the estimate to the first-place price while the figure counts down with it, about 0.9s on an exponential ease-out. Around it: the header numbers count up on the first visit, the deadline bar fills, a sheet rises as its data arrives, a lot's description unfolds. Only what has just arrived moves; pressing «Ցույց տալ բոլորը» adds rows without replaying anything. With reduced motion everything appears in place.

## Do's and Don'ts

### Do:

- Lead with the deadline, then what is bought, then who buys.
- Keep official wording available, word for word, in the notice view.
- Write every label as a plain Armenian sentence or noun.
- Animate only state: the tab thumb, a row entering, the tile travelling, a price falling to where the auction left it.
- Say "first place", never "winner": the register publishes the auction's order, and the buyer decides the contract.
- Show a number with what it is measured against: a price beside its estimate, a company's first places beside the lots it bid for.

### Don't:

- Give each row its own card, or nest sheets.
- Add accounts, saved lists or settings: the site is for looking, finding and reading.
- Add a metric hero, kicker labels or decorative illustrations.
- Colour sectors; the sector is an icon and a word.
- State anything the source does not say: a winner, an estimate before the auction, who may take part.
- Give a sole proprietor a page, or list one outside the tender they bid in.
- Add a second chart type, or colour a bar by anything but press blue.

## A second surface: Մեր դաշտը (`docs/my/`)

A company's own view of the contracts register is a different thing from the public list, and it looks different on purpose: the list is a notice board, this is a ledger about money. Its world is the security print of a banknote, and it lends four things only: type, palette, density and one signature move.

- **Signature: the seal.** A guilloche rosette drawn from a tax number: the digits set the lobes of the rim, the petals of the lace, the heart and the turn (`sealPaths` in `app.js`). Every company has its own, it never changes, and it stands wherever the company does: beside its name, in the legend, on the plate. The same drawing, large and in foil, is the wheel behind the plate; it turns a notch with every tab. Seals draw themselves line by line once, when they appear.
- **Palette.** Paper `#F2EDE1`, sheet `#FBF8F1`, ink `#17201D`; one deep-green plate `#0E3B34` with foil `#D8B45A`; the plate keeps its colour in both themes. The three companies are `#B9541E`, `#2D62B5`, `#B03A7A` on the light sheet and `#DE6E3A`, `#4C8BDF`, `#D06AA6` on the dark sheet and on the plate. Both sets were run through the colour-blind separation and contrast checks against their surface; that is why there are three companies and not four. Magnitude bars are one green; amber is only for a deadline that is close.
- **Type.** Noto Serif Armenian for titles and section heads, the digits of Bodoni Moda for the one large figure and for ranks, Noto Sans Armenian for everything that is read or tapped. No serif in labels, buttons or data rows.
- **Lists are ledgers.** One sheet with hairlines, a tile on the left (days left, a date, a rank), the amount on the right in tabular figures. Elevation is a hairline border; only the bottom sheet has a shadow.
- **Text never wears a company's colour.** A dot or a seal beside the name carries it.
- **Motion.** The plate changes height and its text swaps; the wheel turns; the total counts up; columns grow from the baseline; rows rise with a short stagger; the sheet slides up and can be pulled down. Everything has a still state: with reduced motion nothing moves and nothing is missing.
- **Sole proprietors** are one unnamed row beside every ranking, never inside it.

