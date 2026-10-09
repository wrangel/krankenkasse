# Shared design

viaprima and [Abstract Altitudes](https://abstractaltitudes.com) are built by
one person and should look like it. They run on different stacks — React with
CSS modules, and Streamlit — so there is no shared stylesheet. What is shared
is this short list of decisions, taken from Abstract Altitudes, which had them
first.

Nothing here requires a change to that project. This file records what viaprima
copied, so that a change on either side is a deliberate divergence rather than
a drift nobody noticed.

## Tokens

Abstract Altitudes is dark only. viaprima follows the visitor's system setting
(Streamlit's System / Light / Dark switch), so it has a light variant that
Abstract Altitudes has no counterpart for. The dark variant is the shared one.

| | dark (shared) | light (viaprima only) | where it lives here |
|---|---|---|---|
| Background | `#000000` | `#ffffff` | `.streamlit/config.toml` |
| Text | `#ffffff` | `#111111` | `.streamlit/config.toml` |
| Accent | `#4da6ff` | `#1f73c2` | `primaryColor`, `linkColor` |
| Accent, dark | `#3b8cc2` | – | unused here so far |
| Hairline | `rgba(255, 255, 255, 0.1)` | `rgba(0, 0, 0, 0.1)` | `borderColor` |
| Base size | 16px | 16px | `baseFontSize` |

The light accent is darker because `#4da6ff` on white is about 2.6:1, well
under the 4.5:1 that body-size link text needs; `#1f73c2` is 4.9:1. The
wordmark keeps `#4da6ff` in both themes — a logotype is exempt, and it is the
one place the brand colour should not shift.

Custom CSS in `theme.py` must work on either background. That means no fixed
near-white or near-black: use `inherit`/`currentColor`, mid-grey at low alpha
(`rgba(128, 128, 128, …)`, also the footer rule), and mute text through
`color-mix(… currentColor 85% …)` rather than `opacity`, which would fade the
links inside it below 4.5:1 as well.

Abstract Altitudes keeps the dark values in `:root` in
`src/frontend/styles/Global.css`.

## Typography

Abstract Altitudes uses **Inter Variable**. viaprima deliberately does not: it
would mean either a webfont request, which hands every visitor's IP to whoever
hosts it and contradicts what `.github/SECURITY.md` promises, or self-hosting
the files. The stack in `.streamlit/config.toml` resolves to SF on Apple
devices and Segoe UI on Windows — both neutral grotesques close enough to Inter
that the two sites read as siblings.

To close that gap properly, self-host Inter under `static/` with
`server.enableStaticServing` and point `theme.fontFaces` at it.

## Footer

Copied from Abstract Altitudes' `.finalFooter` in `Grid.module.css`, rows in
the same order: actions (contact, licence, coffee), credits (the first, "wrangel", links
the repository and so stands in for a separate source link), "also by
me" with a dimmer leading label, copyright. Each row is separate links in a
centred flex row with a `1.5rem` gap — no separator characters — stacking into
a column below 768px. Hairline above, `5rem` margin and `4rem` padding, links
at `0.9rem` and 70% opacity brightening to the accent on hover, copyright at
`0.8rem`, 40% opacity and `1px` letterspacing. The copyright names the site,
not the person, as there.

One deliberate difference. On a photography portfolio the whole footer can
recede, because it is chrome. Here it also carries the data, Kipppunkt and PHARM
footnotes and the note on why the app exists — those are content, and they stay
at reading size. Only the credits and the copyright take the recessive
treatment.

## What is not shared

The language switch, the brand wordmark as a page title, and the person-colour
palette are specific to this app. Abstract Altitudes has no equivalent and does
not need one.
