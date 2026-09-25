"""Offline tests for the poster-palette heuristic (FR-LIB-13/14, §9).

Only the pure half, :func:`palette_from_image_bytes`, is exercised here —
images built in-memory with Pillow, no network. The fetch half
(:func:`palette_from_url`) is exercised indirectly through the service and
API tests, which fake or override it rather than hit a real host.
"""

import colorsys
import io

from PIL import Image

from app.films.service.poster_palette import palette_from_image_bytes

_HUE_BUCKETS = 12


def _png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    return int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)


def _hue_bucket(r: int, g: int, b: int) -> int:
    h, _s, _v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    return int(h * _HUE_BUCKETS)


def test_a_solid_colour_poster_yields_a_one_entry_palette() -> None:
    image = Image.new("RGB", (64, 64), (220, 20, 20))
    palette = palette_from_image_bytes(_png_bytes(image))
    assert palette is not None
    assert len(palette) == 1
    r, g, b = _hex_to_rgb(palette[0])
    assert r > g and r > b


def test_a_dominant_beige_ranks_above_a_smaller_saturated_brown_patch() -> None:
    # Regression for the Sicario bug: quantize splits one dominant beige area
    # into several near-identical shades, so a naive "most populous single
    # swatch" pick loses to a smaller but uniform brown patch. Bucketing by
    # hue and ranking buckets by total population fixes that — beige stays
    # first even though no single beige swatch outnumbers the brown, and the
    # brown still shows up as the second entry rather than being dropped.
    beige_bands = [(0xDB, 0xCE, 0xB5), (0xE7, 0xDA, 0xC3), (0xEA, 0xDF, 0xC9), (0xE1, 0xD4, 0xBA)]
    brown = (0x93, 0x74, 0x5A)
    image = Image.new("RGB", (64, 64))
    for y in range(64):
        row = beige_bands[y % len(beige_bands)] if y < 38 else brown  # ~60% beige, ~40% brown
        for x in range(64):
            image.putpixel((x, y), row)

    palette = palette_from_image_bytes(_png_bytes(image))

    assert palette is not None
    assert len(palette) == 2
    assert _hue_bucket(*_hex_to_rgb(palette[0])) == _hue_bucket(*beige_bands[0])
    r1, g1, b1 = _hex_to_rgb(palette[1])
    assert r1 > g1 > b1  # brownish, the smaller but still-present second bucket


def test_a_dominant_neutral_ranks_first_and_a_smaller_chromatic_patch_still_shows_up() -> None:
    # Black and white both fall in the "neutral" bucket (ceiling noted in the
    # module docstring), so a poster that's mostly black/white with a small
    # red patch ranks neutral first — the true majority — with red as the
    # smaller second entry, never dropped.
    image = Image.new("RGB", (64, 64))
    for y in range(64):
        for x in range(64):
            image.putpixel((x, y), (0, 0, 0) if y < 32 else (255, 255, 255))
    for y in range(20):
        for x in range(20):
            image.putpixel((x, y), (220, 20, 20))  # a red patch inside the black half

    palette = palette_from_image_bytes(_png_bytes(image))

    assert palette is not None
    assert len(palette) == 2
    r0, g0, b0 = _hex_to_rgb(palette[0])
    _h0, s0, v0 = colorsys.rgb_to_hsv(r0 / 255, g0 / 255, b0 / 255)
    assert s0 < 0.08 or v0 < 0.15  # first entry is neutral
    r1, g1, b1 = _hex_to_rgb(palette[1])
    assert r1 > g1 and r1 > b1  # second entry is the red patch


def test_garbage_bytes_are_handled_without_raising() -> None:
    assert palette_from_image_bytes(b"not an image") is None


def test_a_hue_bucket_is_represented_by_its_most_saturated_swatch() -> None:
    # An accent bucket holding a common dull gray-brown and a rarer vivid
    # brown of the same hue is represented by the vivid one; the dominant
    # (surface) bucket keeps its most common shade.
    dull = (0x5A, 0x4E, 0x46)  # hue ~24°, saturation ~0.22
    vivid = (0x93, 0x5A, 0x3A)  # hue ~22°, saturation ~0.6
    beige = (0xDB, 0xCE, 0xB5)  # the dominant bucket, drives the surfaces
    image = Image.new("RGB", (64, 64), beige)
    for y in range(34, 64):
        for x in range(64):
            image.putpixel((x, y), vivid if y < 44 else dull)

    palette = palette_from_image_bytes(_png_bytes(image))

    assert palette == ["#dbceb5", "#935a3a"]
