from __future__ import annotations

import colorsys


def rgbw_brightness(
    rgbw_data: tuple[int, int, int, int],
    brightness: int | None = None,
) -> tuple[int, int, int, int]:
    """Convert rgbw to brightness."""
    original_r, original_g, original_b = rgbw_data[0:3]
    h, s, v = colorsys.rgb_to_hsv(original_r / 255, original_g / 255, original_b / 255)
    color_brightness = round(v * 255)
    ww_brightness = rgbw_data[3]
    current_brightness = round((color_brightness + ww_brightness) / 2)

    if not brightness or brightness == current_brightness:
        return rgbw_data

    if brightness < current_brightness:
        change_brightness_pct = (current_brightness - brightness) / current_brightness
        ww_brightness = round(ww_brightness * (1 - change_brightness_pct))
        color_brightness = round(color_brightness * (1 - change_brightness_pct))

    else:
        change_brightness_pct = (brightness - current_brightness) / (
            255 - current_brightness
        )
        ww_brightness = round(
            (255 - ww_brightness) * change_brightness_pct + ww_brightness
        )
        color_brightness = round(
            (255 - color_brightness) * change_brightness_pct + color_brightness
        )

    r, g, b = colorsys.hsv_to_rgb(h, s, color_brightness / 255)
    return (round(r * 255), round(g * 255), round(b * 255), ww_brightness)
