from __future__ import annotations

import colorsys


def calculate_brightness(rgb: tuple[int, int, int], level: int) -> tuple[int, int, int]:
    """Apply a brightness level to an RGB color."""
    hsv = colorsys.rgb_to_hsv(*rgb)
    red, green, blue = colorsys.hsv_to_rgb(hsv[0], hsv[1], level)
    return int(red), int(green), int(blue)


def rgb_unscaled(rgb: tuple[int, int, int]) -> tuple[int, int, int]:
    """Scale RGB up to its full value while preserving hue and saturation."""
    red_value, green_value, blue_value = rgb
    hsv = colorsys.rgb_to_hsv(
        red_value / 255.0, green_value / 255.0, blue_value / 255.0
    )
    red, green, blue = colorsys.hsv_to_rgb(hsv[0], hsv[1], 1)
    return round(red * 255), round(green * 255), round(blue * 255)
