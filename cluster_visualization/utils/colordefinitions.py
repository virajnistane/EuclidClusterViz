# !/bin/python3
# -*- coding: utf-8 -*-
# colordefinitions.py
# This file contains color definitions for visualization purposes.
# It includes a list of colors, a dictionary mapping indices to colors,
# and functions for color conversion.


import colorsys

colors_list = [
    "#1f77b4",  # blue
    "#ff7f0e",  # orange
    "#2ca02c",  # green
    "#d62728",  # red
    "#9467bd",  # purple
    "#8c564b",  # brown
    "#e377c2",  # pink
    "#7f7f7f",  # gray
    "#bcbd22",  # olive
    "#17becf",  # cyan
    "#aec7e8",  # light blue
    "#ffbb78",  # light orange
    "#98df8a",  # light green
    "#ff9896",  # light red
    "#c5b0d5",  # light purple
    "#f7b6d2",  # light pink
    "#c7c7c7",  # light gray
    "#dbdb8d",  # light olive
    "#9edae5",  # light cyan
]

colors_dict = {
    0: "#1f77b4",  # blue
    1: "#ff7f0e",  # orange
    2: "#2ca02c",  # green
    3: "#d62728",  # red
    4: "#9467bd",  # purple
    5: "#8c564b",  # brown
    6: "#e377c2",  # pink
    7: "#7f7f7f",  # gray
    8: "#bcbd22",  # olive
    9: "#17becf",  # cyan
    10: "#aec7e8",  # light blue
    11: "#ffbb78",  # light orange
    12: "#98df8a",  # light green
    13: "#ff9896",  # light red
    14: "#c5b0d5",  # light purple
    15: "#f7b6d2",  # light pink
    16: "#c7c7c7",  # light gray
    17: "#dbdb8d",  # light olive
    18: "#9edae5",  # light cyan
}


def hex_to_hsl(hex_color, alpha=1.0):
    hex_color = hex_color.lstrip("#")
    lv = len(hex_color)
    rgb = tuple(int(hex_color[i : i + lv // 3], 16) / 255.0 for i in range(0, lv, lv // 3))
    h, l, s = colorsys.rgb_to_hls(*rgb)
    h = int(round(h * 360))
    s = int(round(s * 100))
    l = int(round(l * 100))
    if alpha < 1.0:
        return f"hsla({h}, {s}%, {l}%, {alpha:.2f})"
    else:
        return f"hsl({h}, {s}%, {l}%)"


colors_list_hsl = [hex_to_hsl(c) for c in colors_list]
colors_list_transparent = [hex_to_hsl(c, 0.2) for c in colors_list]


# colors_list_transparent = [color + 'cc' for color in colors_list]
