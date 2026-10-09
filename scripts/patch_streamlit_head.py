"""Give Streamlit's static page what search engines and link previews read.

Streamlit serves one fixed index.html and fills in the page with JavaScript
over a websocket. A crawler or a WhatsApp/Slack preview that does not run it
saw <title>Streamlit</title>, lang="en", no description and Streamlit's logo.
Streamlit offers no hook for the <head>, so this edits the installed copy at
image build time, and drops robots.txt, sitemap.xml and the images next to
it - Streamlit serves every file in that folder from the site root, the way
it already serves favicon.png.

The static head is German: there is one URL, and German is the language most
visitors read. Runs in CI as well, so a Streamlit update that moves the
anchors below fails the check instead of silently shipping "Streamlit" again.

    python scripts/patch_streamlit_head.py
"""

import html
import json
import shutil
import sys
from pathlib import Path

import streamlit

ROOT = Path(__file__).resolve().parent.parent
STATIC = Path(streamlit.__file__).parent / "static"
SITE = "https://viaprima.ch/"

TITLE = json.loads((ROOT / "locales" / "de.json").read_text(encoding="utf-8"))["page_title"]
DESCRIPTION = (
    "Welche Krankenkasse, welches Modell und welche Franchise kosten dich am "
    "wenigsten? viaprima rechnet aus den offiziellen BAG-Prämien deine "
    "Gesamtkosten, für den ganzen Haushalt. Kostenlos und ohne Werbung."
)
# For clients that never run the app: what it does, in plain text.
NOSCRIPT = (
    "<h1>viaprima</h1>"
    "<p>Die Grundversicherung: die günstigste Lösung für deine Situation.</p>"
    "<p>Du sagst, was du im Jahr an Arztkosten erwartest. Die App rechnet aus "
    "den offiziellen Prämiendaten des BAG für jede Person im Haushalt "
    "Versicherer, Modell und Franchise mit den tiefsten Gesamtkosten aus – "
    "Prämien, Franchise und Selbstbehalt zusammen.</p>"
    "<p>Für die Berechnung braucht es JavaScript.</p>"
)
STRUCTURED = {
    "@context": "https://schema.org",
    "@type": "WebApplication",
    "name": "viaprima",
    "url": SITE,
    "description": DESCRIPTION,
    "applicationCategory": "FinanceApplication",
    "operatingSystem": "Web",
    "inLanguage": ["de", "fr", "it", "en"],
    "isAccessibleForFree": True,
    "offers": {"@type": "Offer", "price": "0", "priceCurrency": "CHF"},
}


def head() -> str:
    t, d = html.escape(TITLE), html.escape(DESCRIPTION)
    image = f"{SITE}og-image.png"
    return f"""<title>{t}</title>
    <meta name="description" content="{d}" />
    <link rel="canonical" href="{SITE}" />
    <meta name="theme-color" content="#000000" />
    <meta property="og:type" content="website" />
    <meta property="og:site_name" content="viaprima" />
    <meta property="og:locale" content="de_CH" />
    <meta property="og:title" content="{t}" />
    <meta property="og:description" content="{d}" />
    <meta property="og:url" content="{SITE}" />
    <meta property="og:image" content="{image}" />
    <meta property="og:image:width" content="1200" />
    <meta property="og:image:height" content="630" />
    <meta name="twitter:card" content="summary_large_image" />
    <meta name="twitter:title" content="{t}" />
    <meta name="twitter:description" content="{d}" />
    <meta name="twitter:image" content="{image}" />
    <link rel="apple-touch-icon" href="./favicon.png" />
    <script type="application/ld+json">{json.dumps(STRUCTURED, ensure_ascii=False)}</script>"""


# Each anchor must occur exactly once in Streamlit's index.html.
REPLACEMENTS = {
    '<html lang="en">': '<html lang="de">',
    "<title>Streamlit</title>": head(),
    "<noscript>You need to enable JavaScript to run this app.</noscript>":
        f"<noscript>{NOSCRIPT}</noscript>",
}


def main() -> int:
    index = STATIC / "index.html"
    page = index.read_text(encoding="utf-8")
    if 'content="' + html.escape(DESCRIPTION) in page:
        print("index.html already patched")
    else:
        for anchor, replacement in REPLACEMENTS.items():
            if page.count(anchor) != 1:
                print(f"Streamlit's index.html changed: expected {anchor!r} once, "
                      f"found it {page.count(anchor)} times. Update the anchors in "
                      f"{Path(__file__).name}.", file=sys.stderr)
                return 1
            page = page.replace(anchor, replacement)
        index.write_text(page, encoding="utf-8")

    # favicon.png overwrites Streamlit's own; the rest are new.
    for name in ("favicon.png", "og-image.png", "robots.txt", "sitemap.xml"):
        shutil.copyfile(ROOT / "seo" / name, STATIC / name)
    print(f"patched {index}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
