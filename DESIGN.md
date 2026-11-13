---
name: Մրցույթներ
description: Armenian state tenders as a dated column of notices
colors:
  paper: "#F1F2EE"
  paper-2: "#E5E7E1"
  field: "#FFFFFF"
  ink: "#14161A"
  ink-2: "#474C55"
  ink-3: "#626872"
  rule: "#C6C8C1"
  press-blue: "#1F3A93"
  on-press: "#FFFFFF"
  on-press-2: "#CBD5F6"
  critical: "#B4231A"
  critical-bg: "#F6DEDA"
  warning: "#855600"
  warning-bg: "#F3E6C8"
  night-paper: "#111317"
  night-paper-2: "#1C1F25"
  night-ink: "#ECEBE5"
  night-rule: "#2D3139"
  night-shell: "#1A2F6E"
  night-accent: "#9DB4FF"
typography:
  nameplate:
    fontFamily: "Noto Sans Armenian, Segoe UI, system-ui, sans-serif"
    fontSize: "2rem"
    fontWeight: 800
    lineHeight: 1.1
    letterSpacing: "normal"
  dateline:
    fontFamily: "Noto Sans Armenian, Segoe UI, system-ui, sans-serif"
    fontSize: "1.875rem"
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
rounded:
  field: "10px"
  button: "12px"
  pill: "20px"
spacing:
  gutter: "16px"
  row: "12px"
  section: "32px"
components:
  button-primary:
    backgroundColor: "{colors.press-blue}"
    textColor: "{colors.on-press}"
    rounded: "{rounded.button}"
    padding: "8px 16px"
    height: "48px"
  button-secondary:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.button}"
    padding: "8px 16px"
    height: "48px"
  chip:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink-2}"
    rounded: "{rounded.pill}"
    padding: "0 14px"
    height: "40px"
  chip-selected:
    backgroundColor: "{colors.press-blue}"
    textColor: "{colors.on-press}"
  search-field:
    backgroundColor: "{colors.field}"
    textColor: "{colors.ink}"
    rounded: "{rounded.field}"
    height: "46px"
---

# Design System: Մրցույթներ

## Overview

The announcements page of an Armenian daily, rebuilt as a phone tool. A tender is a dated notice: the deadline stands in its own narrow column at the left, a column rule separates it from the text, and heavy rules open each day. Everything else is the standard furniture of a mobile app: a header with search, tabs, filter chips, a list, a pushed detail view.

The reader is a non-technical business owner on a phone, usually in daylight. Body text is 16px, tap targets are 44px or more, and nothing relies on colour alone.

## Colors

- **Newsprint** (`paper`) is the ground, **ink** the text. Neutrals lean slightly cool and green, like newsprint, never cream.
- **Press blue** is the single spot ink: the shell, selection, primary action. In the dark theme the shell stays blue and the accent on dark paper lightens to `night-accent`.
- **Red** means the deadline is today or tomorrow; **amber** means three days or less. They are states, never decoration, and always come with words («վաղը, մինչև 10:00»).

### Named Rules

- **Two inks.** A screen prints in ink and press blue. A third colour may only be a deadline state.

## Typography

One family, Noto Sans Armenian (variable weight and width, self-hosted). Two voices come from the width axis: condensed and heavy for dates and headings (width 66 to 80%), normal width for reading.

### Hierarchy

Nameplate 32/800 condensed; dateline numeral 30/800 condensed; section and day headings 17/750 at 80% width; row titles 17/650 at 88%; body 16/400; meta 14/400. Sizes are fixed rem steps; the «ԱԱ» control scales the root to 112.5% and 125%.

### Named Rules

- **Never uppercase Armenian with CSS.** `text-transform: uppercase` turns «և» into «ԵՒ», which is wrong in modern spelling. Capitals are written out in the source (ԵՐՔ, ՆՈՅ).

## Layout

One column, at most 40rem wide, 16px gutters. The shell and tab bar are full-bleed; tabs and day rules are sticky. A row is a two-column grid: a 3.5rem dateline, then the text, with the save star in a 44px lane at the right. Titles clamp to two lines and buyers to one; the notice view shows everything in full.

## Elevation & Depth

Print has no shadows. Structure comes from rules: a 2px ink rule opens a day or a section, hairlines separate rows. The only shadow is under the toast, which floats above the page.

## Shapes

Fields 10px, buttons 12px, chips fully rounded. Rows and sections have no boxes at all.

## Components

### Buttons

Primary: press-blue fill. Secondary: 1.5px ink outline on paper. Both 48px tall, 12px radius, label at 88% width, an icon before the label.

### Chips

40px pills with a count; the selected one is filled press blue.

### Inputs / Fields

One search field in the shell: white on blue, 46px, with a clear button once text is typed.

### Navigation

Three tabs with counts and a 3px ink underline. The notice view is pushed, with a back button and Telegram's own back button when inside Telegram.

### Dateline column

The signature component. In «Նոր» and «Պահված» it shows weekday, a large day numeral and month; in «Ժամկետներ», where the day is already the section heading, it shows the time. The numeral turns amber or red as the deadline approaches.

## Do's and Don'ts

### Do:

- Lead with the deadline, then what is bought, then who buys.
- Keep official wording available, word for word, in the notice view.
- Write every label as a plain Armenian sentence or noun.

### Don't:

- Wrap rows in cards or add shadows.
- Add a metric hero, kicker labels or decorative icons.
- State anything the source does not say (prices, winners, eligibility).
