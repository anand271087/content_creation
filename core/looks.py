"""Avatar look registry — every trained HeyGen look, its setting, and which
formats it suits. Pulled from the HeyGen API 2026-07-12 (5 groups, 17 looks).

crop=None → framing not yet verified: do ONE test render, check a frame,
add the preset to core/framing.py, then fill it in here. Side-angle looks
have off-center faces — board/pill layouts should MIRROR (face right → UI left).
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class Look:
    key: str
    avatar_id: str
    group: str
    angle: str            # front | side
    setting: str
    crop: str | None      # core/framing.py preset name once verified
    formats: list[str]    # recommended formats from the registry
    mirror_ui: bool = False


LOOKS: dict[str, Look] = {l.key: l for l in [
    # ── Blue: black polo w/ red trim ──────────────────────────────────────
    Look("blue_chair_front", "87db904b81ec4e989ac34f5eb6d0dcb4", "blue", "front",
         "green wingback armchair, dark wall (seated)", None,
         ["question_bubble", "longform"]),
    Look("blue_chair_side", "375926c5b6b2406dbc704493af5ea571", "blue", "side",
         "green wingback armchair (seated, closer)", None,
         ["question_bubble"], mirror_ui=True),
    Look("blue_bright_front", "1a5f8b2171664300a4196740627ef478", "blue", "front",
         "bright stone wall + plant + sofa (standing)", None,
         ["viral_15s", "sort_board"]),
    Look("blue_stairs_side", "87554c967326419dad39de107f63c57e", "blue", "side",
         "wooden staircase, bright (standing)", None,
         ["b-angle for blue_bright_front"], mirror_ui=True),

    # ── White: white polo ─────────────────────────────────────────────────
    Look("white_darkwall_front", "8cd70deba2f04b358f2cd6a9ab7ef602", "white", "front",
         "dark navy wall, warm sconces, red accent (standing)", None,
         ["viral_15s", "timer", "hero hooks"]),
    Look("white_darkwall_side", "d02436198c484c41be0f20c4c07b01df", "white", "side",
         "dark wall + red accent", None,
         ["b-angle for white_darkwall_front"], mirror_ui=True),
    Look("white_chair_front", "7b21878db3cf418aacdd2121d212b4b8", "white", "front",
         "green wingback chair, navy panels (seated)", None,
         ["question_bubble", "longform"]),
    Look("white_chair_side", "6f76c08420034e48ae1953e4e79bce34", "white", "side",
         "green wingback chair (seated)", None,
         ["b-angle for white_chair_front"], mirror_ui=True),

    # ── Blueshrt: navy button-down ────────────────────────────────────────
    Look("blueshrt_window_front", "282cde77828a4694a24426dd47c1b059", "blueshrt", "front",
         "bright window/glass (standing) — nick_saraev editorial aesthetic; "
         "SOURCE LETTERBOXED, use blueshrt_full/blueshrt_tight presets", "blueshrt_full",
         ["process_walkthrough (format #8)", "countdown"]),
    Look("blueshrt_stone_34", "b0375ab1cb90429881b9861f94d644c9", "blueshrt", "side",
         "grey stone wall + hanging plant (three-quarter)", None,
         ["b-angle for blueshrt_window_front"], mirror_ui=True),

    # ── Green group: green shirt @ bookshelf + black crew looks ───────────
    Look("green_bookshelf_front", "b3c1f3b2e3e240e38954957fd9e9caed", "green", "front",
         "warm bookshelf set, orange glow (Dan Martell aesthetic) — NO bg replacement needed", None,
         ["tier_board", "tier_timeline", "sort_board", "tier_stack"]),
    Look("green_bookshelf_side", "d6e85cde152741cb9b09ee50832fa5a3", "green", "side",
         "warm bookshelf set", None,
         ["b-angle for green_bookshelf_front"], mirror_ui=True),
    Look("black_blinds_front", "4a269a2d0e164da6927b5ef08718671e", "green", "front",
         "black crew, bright blinds + plant (standing)", None,
         ["countdown", "checklist"]),
    Look("black_couch_front", "80ec06078fde434f9255da5d6251abc0", "green", "front",
         "black crew, couch + brick (seated) — LETTERBOXED (band 1000x608 @ "
         "x50 y656); use dark_brick palette + blur-fill base", "black_couch_full",
         ["countdown", "moody virals", "process_walkthrough (dark)"]),
    Look("black_brick_side", "c1e30d196e9042a2b5e52071c15596bc", "green", "side",
         "black crew, brick wall (profile)", None,
         ["b-angle for black looks"], mirror_ui=True),

    # ── Grey: grey Nike long-sleeve ───────────────────────────────────────
    Look("grey_bookshelf_front", "f0ce1c8a15c6478682925d49c10e06bd", "grey", "front",
         "bookshelf set, rust chair (seated)", None,
         ["checklist", "authority how-to"]),
    Look("grey_bookshelf_side", "faa7bced85fa43f1b472d5ba1e3e5774", "grey", "side",
         "bookshelf set (seated)", None,
         ["b-angle for grey_bookshelf_front"], mirror_ui=True),
]}


def get(key: str) -> Look:
    if key not in LOOKS:
        raise KeyError(f"unknown look {key!r} — see core/looks.py ({', '.join(LOOKS)})")
    return LOOKS[key]


def pairs() -> dict[str, tuple[str, str]]:
    """front/side pairs usable for two-camera jump cuts (render script on both,
    alternate at sentence boundaries)."""
    return {
        "blue_chair": ("blue_chair_front", "blue_chair_side"),
        "white_darkwall": ("white_darkwall_front", "white_darkwall_side"),
        "white_chair": ("white_chair_front", "white_chair_side"),
        "blueshrt": ("blueshrt_window_front", "blueshrt_stone_34"),
        "green_bookshelf": ("green_bookshelf_front", "green_bookshelf_side"),
        "grey_bookshelf": ("grey_bookshelf_front", "grey_bookshelf_side"),
    }
