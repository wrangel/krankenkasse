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

| | value | where it lives here |
|---|---|---|
| Background | `#000000` | `.streamlit/config.toml` |
| Text | `#ffffff` | `.streamlit/config.toml` |
| Accent | `#4da6ff` | `.streamlit/config.toml` (`primaryColor`, `linkColor`) |
| Accent, dark | `#3b8cc2` | unused here so far |
| Hairline | `rgba(255, 255, 255, 0.1)` | `borderColor`, and the footer rule |
| Base size | 16px | `baseFontSize` |

Abstract Altitudes keeps the same values in `:root` in
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

Copied from Abstract Altitudes' `.finalFooter` in `Grid.module.css`: a centred
column capped at 800px, a hairline rule above it, credits at `0.9rem` and 70%
opacity brightening to the accent on hover, copyright at `0.8rem`, 40% opacity
and `1px` letterspacing.

One deliberate difference. On a photography portfolio the whole footer can
recede, because it is chrome. Here it also carries the Kipppunkt and PHARM
footnotes and the note on why the app exists — those are content, and they stay
at reading size. Only the credits and the copyright take the recessive
treatment.

## What is not shared

The language switch, the brand wordmark as a page title, and the person-colour
palette are specific to this app. Abstract Altitudes has no equivalent and does
not need one.
