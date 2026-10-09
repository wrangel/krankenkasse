"""Draw the favicon and the link-preview image into seo/.

Run once on a Mac when the brand changes; the PNGs are committed, so the image
build needs neither fonts nor this script. Helvetica Neue Bold stands in for
the system stack the page uses - on Apple devices the page renders in SF,
which macOS does not ship as a static file Pillow can load by weight.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SEO = Path(__file__).resolve().parent.parent / "seo"
FONT = "/System/Library/Fonts/HelveticaNeue.ttc"
BOLD, REGULAR = 1, 0  # face indices inside the .ttc
BLACK, WHITE, ACCENT, MUTED = "#000000", "#ffffff", "#4da6ff", "#9a9a9a"


def font(size, index=BOLD):
    return ImageFont.truetype(FONT, size, index=index)


def wordmark(draw, x, y, size):
    """'via' in white, 'prima' in the accent, kerned tight like the page."""
    f = font(size)
    tracking = -0.035 * size
    for part, colour in (("via", WHITE), ("prima", ACCENT)):
        for ch in part:
            draw.text((x, y), ch, font=f, fill=colour)
            x += draw.textlength(ch, font=f) + tracking
    return x


def favicon():
    # A lowercase "v" in the accent on black: the first letter of the
    # wordmark, legible at 16px where the full word would not be.
    size = 512
    img = Image.new("RGB", (size, size), BLACK)
    d = ImageDraw.Draw(img)
    f = font(420)
    box = d.textbbox((0, 0), "v", font=f)
    w, h = box[2] - box[0], box[3] - box[1]
    d.text(((size - w) / 2 - box[0], (size - h) / 2 - box[1]), "v", font=f, fill=ACCENT)
    img.resize((192, 192), Image.LANCZOS).save(SEO / "favicon.png", optimize=True)


def og_image():
    # 1200x630 is what Facebook, LinkedIn, Slack and WhatsApp all crop to.
    img = Image.new("RGB", (1200, 630), BLACK)
    d = ImageDraw.Draw(img)
    wordmark(d, 96, 170, 150)
    d.text((100, 380), "Die Grundversicherung:", font=font(46), fill=WHITE)
    d.text((100, 440), "die günstigste Lösung für deine Situation", font=font(46, REGULAR), fill=WHITE)
    d.text((100, 540), "viaprima.ch", font=font(30, REGULAR), fill=MUTED)
    img.save(SEO / "og-image.png", optimize=True)


if __name__ == "__main__":
    favicon()
    og_image()
    print("wrote", ", ".join(p.name for p in sorted(SEO.glob("*.png"))))
