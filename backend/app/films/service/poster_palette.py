"""Deriving a Material 3 seed palette from a film's poster (FR-LIB-13/14).

The poster is a user-entered URL on an arbitrary host (§4.1): the frontend
cannot read its pixels itself (CORS), so the backend fetches it once and
stores a ranked list of up to four ``"#rrggbb"`` seed colours for the
client's dynamic-colour theming — most dominant first, so the client can map
roles by position (surfaces from the first, primary/secondary/tertiary from
the rest). A palette is a nicety, never a write-blocking concern — every
failure path here returns ``None`` rather than raising.
"""

import colorsys
import io
import logging
import urllib.request
from typing import cast

from PIL import Image

_TIMEOUT_SECONDS = 5
_MAX_BYTES = 10 * 1024 * 1024
_USER_AGENT = "FilmRewatchApp/1.0 (poster colour fetch)"
# Below these, hue is meaningless (black/gray/white) — bucketed as "neutral"
# instead of by hue so a grayscale poster still yields its own seed.
_NEUTRAL_SATURATION = 0.08
_NEUTRAL_VALUE = 0.15
_HUE_BUCKETS = 12
_MAX_PALETTE_SIZE = 4

logger = logging.getLogger(__name__)


def palette_from_url(url: str) -> list[str] | None:
    """Fetch ``url`` and derive its seed palette, or ``None`` on any failure.

    Never raises: a fetch/decode error is logged at ``warning`` and swallowed
    — the film write this feeds must never fail because a poster host is
    slow, unreachable, or serves something Pillow can't open.
    """
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
            data = response.read(_MAX_BYTES + 1)
    except Exception:
        logger.warning("poster fetch failed for %s", url, exc_info=True)
        return None
    if len(data) > _MAX_BYTES:
        logger.warning("poster at %s exceeds the %d byte cap, skipping", url, _MAX_BYTES)
        return None
    return palette_from_image_bytes(data)


def palette_from_image_bytes(data: bytes) -> list[str] | None:
    """The pure half: image bytes to a ranked seed palette, or ``None`` on decode failure.

    The dominant colour always wins, black/white/gray/beige included (repo
    owner's call) — a colourless-looking poster still yields a valid seed, it
    just lands in the "neutral" bucket below rather than a hue bucket. No
    bucket is ever dropped: the whole ranking (capped at four) comes back so
    the client can map surfaces/primary/secondary/tertiary by position.

    # ponytail: hue-bucket dominance heuristic — quantize to a small palette,
    # bucket each swatch by hue (or "neutral" when saturation/value are too
    # low for hue to mean anything), rank buckets by total population, and
    # return each bucket's representative swatch — the most populous one for
    # the first bucket (it drives the surfaces, so the commonest shade is the
    # faithful one) and for neutral (saturation means nothing there), the most
    # saturated one for the accent buckets (so a vivid accent beats a duller,
    # more common shade of the same hue). Ranking buckets rather than swatches beats picking the
    # single most populous swatch outright: a dominant colour that spans
    # several near-identical quantizer swatches (e.g. a beige poster split
    # into ~8 shades) would otherwise lose to a smaller, uniform patch.
    # Ceiling: the neutral bucket lumps black + gray + white into one swatch
    # pick, and hue buckets are a coarse 30° split rather than perceptual
    # clustering. Upgrade path if palettes look off in practice: port
    # Material's QuantizerCelebi + Score algorithm (what the Android/web M3
    # libraries actually use) instead of this thumbnail-and-quantize shortcut.
    """
    try:
        image = Image.open(io.BytesIO(data)).convert("RGB")
        image.thumbnail((64, 64))
        palette_image = image.quantize(colors=16)
    except Exception:
        logger.warning("poster image could not be decoded", exc_info=True)
        return None

    # A quantized (P-mode) image's getcolors() always pairs a count with an
    # integer palette index — the stub's ``float`` alternative covers other
    # image modes this function never passes it.
    counts = cast("list[tuple[int, int]]", palette_image.getcolors(maxcolors=16) or [])
    palette = palette_image.getpalette() or []
    if not counts:
        return None

    buckets: dict[str | int, list[tuple[int, float, tuple[int, int, int]]]] = {}
    for count, index in counts:
        r, g, b = palette[index * 3 : index * 3 + 3]
        h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        bucket: str | int = (
            "neutral" if s < _NEUTRAL_SATURATION or v < _NEUTRAL_VALUE else int(h * _HUE_BUCKETS)
        )
        buckets.setdefault(bucket, []).append((count, s, (r, g, b)))

    ranked = sorted(
        buckets.items(),
        key=lambda bucket: sum(count for count, _s, _rgb in bucket[1]),
        reverse=True,
    )
    result: list[str] = []
    for position, (key, swatches) in enumerate(ranked[:_MAX_PALETTE_SIZE]):
        by_population = position == 0 or key == "neutral"
        _count, _s, (r, g, b) = max(
            swatches, key=lambda item: item[0] if by_population else item[1]
        )
        result.append(f"#{r:02x}{g:02x}{b:02x}")
    return result
