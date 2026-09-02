"""The Archive theme family: one palette per theme, and nothing else per theme.

Every member shares one design language — a dark archive, bone text, an accent for
what is important and a hot colour held back for what matters — so a theme here is
sixteen colours. The shared rules live in `assets/theme-archive.css`; the tokens
those rules consume are generated from these palettes.
"""

from dataclasses import dataclass


def _channels(color: str) -> tuple[int, int, int]:
    value = color.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def mix(base: str, other: str, amount: float) -> str:
    """Returns `base` moved `amount` of the way towards `other`, in sRGB."""
    left, right = _channels(base), _channels(other)
    blended = (round(a + (b - a) * amount) for a, b in zip(left, right, strict=True))
    return "#" + "".join(f"{channel:02x}" for channel in blended)


def relative_luminance(color: str) -> float:
    """WCAG relative luminance, the input to every contrast ratio below."""
    parts = []
    for channel in _channels(color):
        srgb = channel / 255
        parts.append(srgb / 12.92 if srgb <= 0.04045 else ((srgb + 0.055) / 1.055) ** 2.4)
    red, green, blue = parts
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(one: str, two: str) -> float:
    """WCAG contrast between two opaque colours; 4.5 is the floor for body text."""
    first, second = relative_luminance(one), relative_luminance(two)
    lighter, darker = max(first, second), min(first, second)
    return (lighter + 0.05) / (darker + 0.05)


def readable(color: str, ground: str, ratio: float, toward: str) -> str:
    """Lifts `color` towards `toward` in 5% steps until it clears `ratio` on `ground`.

    Solved rather than nudged: a theme states the colour it wants, and a colour that
    cannot carry text at that size on that ground is raised until it can.
    """
    candidate = color
    for step in range(21):
        candidate = mix(color, toward, step * 0.05)
        if contrast_ratio(candidate, ground) >= ratio:
            break
    return candidate


@dataclass(frozen=True)
class Palette:
    """One theme in the family. Every colour it needs; every rule it shares."""

    key: str
    label: str
    vibe: str

    void: str
    """The deepest surface: the rail, and the ground code sits on."""

    bg: str
    """The reading surface and the window behind it."""

    surface: str
    """Panels that sit on the reading surface: callouts, cards, embeds."""

    line: str
    line_strong: str

    link: str
    """Interaction at rest. Must clear 4.5:1 against `bg`."""

    accent: str
    """The theme's solid colour: selection, the seal, the rule under a title."""

    hot: str
    """The 1%. Hover, an active state, the document under your hand."""

    ornament: str
    """Rules, blockquote edges, section breaks — the theme's quieter metal."""

    text: str
    muted: str

    danger: str
    warning: str
    success: str
    info: str

    # -- derived ----------------------------------------------------------

    def legible(self, color: str, ground: str = "", ratio: float = 4.5) -> str:
        """The same colour, raised until it can carry text on the ground it sits on."""
        return readable(color, ground or self.bg, ratio, self.text)

    @property
    def deep(self) -> str:
        """The accent sunk towards the void: structure tints and selected rows."""
        return mix(self.accent, self.void, 0.30)

    @property
    def second(self) -> str:
        """The lighter partner of the link: tags, third-level headings."""
        return mix(self.link, self.text, 0.30)

    @property
    def bright(self) -> str:
        """Brighter than body text: a title, a selected row's label."""
        return mix(self.text, "#ffffff", 0.35)

    @property
    def code_bg(self) -> str:
        return mix(self.void, "#000000", 0.25)

    @property
    def code_fg(self) -> str:
        return mix(self.link, self.text, 0.22)

    @property
    def rail_label(self) -> str:
        """The rail's small-caps section labels, on the void rather than the page."""
        return self.legible(mix(self.accent, self.text, 0.25), self.void)


PALETTES: tuple[Palette, ...] = (
    Palette(
        key="blood-record",
        label="Blood Record",
        vibe="forensic archive",
        void="#0b0909",
        bg="#100d0d",
        surface="#1d1818",
        line="#352929",
        line_strong="#4b2020",
        link="#c15a48",
        accent="#a51f1f",
        hot="#d52b2b",
        ornament="#92503a",
        text="#e6ded0",
        muted="#938a7e",
        danger="#d52b2b",
        warning="#c1843d",
        success="#78966a",
        info="#7b9298",
    ),
    Palette(
        key="ember-archive",
        label="Ember Archive",
        vibe="dark academia, candlelit",
        void="#100d0b",
        bg="#1c1714",
        surface="#30261f",
        line="#3a2b22",
        line_strong="#5a3a26",
        link="#d0764a",
        accent="#9b3424",
        hot="#e08243",
        ornament="#a16b43",
        text="#e8dfd0",
        muted="#a1968a",
        danger="#d4553d",
        warning="#c9903f",
        success="#87a06b",
        info="#8f9ca4",
    ),
    Palette(
        key="blackout",
        label="Blackout",
        vibe="classified terminal",
        void="#050505",
        bg="#0d0d0d",
        surface="#1b1b1b",
        line="#252525",
        line_strong="#3a1c1c",
        link="#e05353",
        accent="#9e1515",
        hot="#ff2929",
        ornament="#8f8f8f",
        text="#ededed",
        muted="#8f8f8f",
        danger="#ff2929",
        warning="#d8a13f",
        success="#84a56d",
        info="#93a7af",
    ),
    Palette(
        key="corrosion",
        label="Corrosion",
        vibe="industrial decay",
        void="#090b0a",
        bg="#111513",
        surface="#202722",
        line="#273029",
        line_strong="#3c4a33",
        link="#a9c43b",
        accent="#819b32",
        hot="#d2e44b",
        ornament="#a45c3f",
        text="#d8ddd4",
        muted="#8d968e",
        danger="#cf6740",
        warning="#d2b23f",
        success="#84b65c",
        info="#8b9ba1",
    ),
    Palette(
        key="bruise",
        label="Bruise",
        vibe="occult, nocturnal",
        void="#0a080c",
        bg="#120e15",
        surface="#241a2a",
        line="#302238",
        line_strong="#4a2b57",
        link="#b378c6",
        accent="#6d3b80",
        hot="#cf82e0",
        ornament="#9a5273",
        text="#e1d9e4",
        muted="#968b9a",
        danger="#d2617e",
        warning="#c79a4a",
        success="#83ab7c",
        info="#8d9bb5",
    ),
    Palette(
        key="drowned",
        label="Drowned",
        vibe="abyssal archive",
        void="#060a0c",
        bg="#0b1215",
        surface="#152328",
        line="#1c3035",
        line_strong="#2a4a52",
        link="#48b0c0",
        accent="#236a78",
        hot="#5fd3dd",
        ornament="#9c6a52",
        text="#d5dddd",
        muted="#8a999c",
        danger="#cc6d51",
        warning="#c9a04f",
        success="#74ae8e",
        info="#88a0a9",
    ),
    Palette(
        key="sepulcher",
        label="Sepulcher",
        vibe="stone, and red is earned",
        void="#0a0a0a",
        bg="#111111",
        surface="#202020",
        line="#292929",
        line_strong="#3a3a38",
        link="#aaa69c",
        accent="#85827b",
        hot="#d2cec2",
        ornament="#85827b",
        text="#d6d3ca",
        muted="#918e89",
        danger="#cc3b3b",
        warning="#bf9f56",
        success="#8b9c81",
        info="#90979e",
    ),
    Palette(
        key="cold-iron",
        label="Cold Iron",
        vibe="engineering, incident response",
        void="#080b0d",
        bg="#101417",
        surface="#1d252a",
        line="#283238",
        line_strong="#3a4b54",
        link="#7fa6b6",
        accent="#597987",
        hot="#a8d0df",
        ornament="#b18a42",
        text="#d2d9dc",
        muted="#8b959a",
        danger="#c8504a",
        warning="#c39a4e",
        success="#85a885",
        info="#87a0ac",
    ),
    Palette(
        key="hazard",
        label="Hazard",
        vibe="containment facility",
        void="#080807",
        bg="#11110f",
        surface="#222219",
        line="#353321",
        line_strong="#4d4726",
        link="#d1b62c",
        accent="#b59b22",
        hot="#f0d84a",
        ornament="#b59b22",
        text="#e4e1d5",
        muted="#9a968a",
        danger="#e0503c",
        warning="#d1b62c",
        success="#8ca664",
        info="#909b95",
    ),
    Palette(
        key="velvet-knife",
        label="Velvet Knife",
        vibe="gothic luxury",
        void="#0d080a",
        bg="#160d10",
        surface="#29171d",
        line="#382027",
        line_strong="#552b39",
        link="#c47088",
        accent="#70253b",
        hot="#e07b95",
        ornament="#a88952",
        text="#e8ddd2",
        muted="#9c8f8b",
        danger="#d55a5a",
        warning="#c79a52",
        success="#8aa57d",
        info="#949cab",
    ),
    Palette(
        key="ash",
        label="Ash",
        vibe="a burned archive",
        void="#0c0b0a",
        bg="#151311",
        surface="#27211c",
        line="#332b25",
        line_strong="#4a3a2c",
        link="#c08962",
        accent="#8d6247",
        hot="#dba579",
        ornament="#a0644a",
        text="#ddd4c8",
        muted="#968a7d",
        danger="#c85a41",
        warning="#c79b4e",
        success="#90a672",
        info="#909aa0",
    ),
    Palette(
        key="null",
        label="Null",
        vibe="black box, not neon",
        void="#050609",
        bg="#0a0d12",
        surface="#161d27",
        line="#202a38",
        line_strong="#2f4460",
        link="#6a9ee0",
        accent="#315c9c",
        hot="#79b2ff",
        ornament="#8593a8",
        text="#dce3ed",
        muted="#8b96a6",
        danger="#e05264",
        warning="#c9953f",
        success="#74ae86",
        info="#87a2bc",
    ),
    Palette(
        key="black-blood",
        label="Black Blood",
        vibe="almost nothing, until something matters",
        void="#050505",
        bg="#0a0a0a",
        surface="#151515",
        line="#1b1010",
        line_strong="#2e1414",
        link="#bdbdbd",
        accent="#820c0c",
        hot="#e01919",
        ornament="#6e6e6e",
        text="#d5d5d5",
        muted="#8c8c8c",
        danger="#e01919",
        warning="#bf9f56",
        success="#8b9c81",
        info="#90979e",
    ),
)
