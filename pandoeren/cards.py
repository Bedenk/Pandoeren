"""Kaarten, rangorde en punten voor pandoeren.

Dit bestand bevat alleen wat een kaart is, wat hij waard is en wie een slag
wint. Bieden, roem en het verloop van een spel staan in andere modules.

Er wordt gespeeld met 33 kaarten: 7 t/m aas in vier kleuren plus de harten zes.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import Optional, Sequence


class Suit(Enum):
    KLAVEREN = "♣"
    RUITEN = "♦"
    HARTEN = "♥"
    SCHOPPEN = "♠"

    @property
    def naam(self) -> str:
        return self.name.lower()

    @property
    def sterkte(self) -> int:
        """Onderlinge rang van kleuren; alleen nodig om roem te vergelijken."""
        return _KLEUR_STERKTE[self]


_KLEUR_STERKTE = {
    Suit.SCHOPPEN: 4,
    Suit.HARTEN: 3,
    Suit.RUITEN: 2,
    Suit.KLAVEREN: 1,
}


class Rank(IntEnum):
    """Waarden staan in de 'gewone' volgorde, zodat reeksen (roem) opeenvolgende
    getallen zijn: zes=6 ... aas=14."""

    ZES = 6
    ZEVEN = 7
    ACHT = 8
    NEGEN = 9
    TIEN = 10
    BOER = 11
    VROUW = 12
    HEER = 13
    AAS = 14

    @property
    def naam(self) -> str:
        return self.name.lower()

    @property
    def label(self) -> str:
        return _RANG_LABEL[self]


_RANG_LABEL = {
    Rank.ZES: "6",
    Rank.ZEVEN: "7",
    Rank.ACHT: "8",
    Rank.NEGEN: "9",
    Rank.TIEN: "10",
    Rank.BOER: "B",
    Rank.VROUW: "V",
    Rank.HEER: "H",
    Rank.AAS: "A",
}


@dataclass(frozen=True)
class Card:
    suit: Suit
    rank: Rank

    def __str__(self) -> str:
        return f"{self.suit.value}{self.rank.label}"


# Rangorde binnen een slag, van hoog naar laag.
GEWONE_VOLGORDE = (
    Rank.AAS, Rank.HEER, Rank.VROUW, Rank.BOER, Rank.TIEN,
    Rank.NEGEN, Rank.ACHT, Rank.ZEVEN, Rank.ZES,
)
# In de troefkleur zijn de boer (de 'jas') en de negen de hoogste kaarten.
TROEF_VOLGORDE = (
    Rank.BOER, Rank.NEGEN, Rank.AAS, Rank.HEER, Rank.VROUW,
    Rank.TIEN, Rank.ACHT, Rank.ZEVEN, Rank.ZES,
)

GEWONE_PUNTEN = {Rank.AAS: 11, Rank.TIEN: 10, Rank.HEER: 3, Rank.VROUW: 2, Rank.BOER: 1}
TROEF_PUNTEN = {
    Rank.BOER: 20, Rank.NEGEN: 14, Rank.AAS: 11,
    Rank.TIEN: 10, Rank.HEER: 3, Rank.VROUW: 2,
}
LAATSTE_SLAG_PUNTEN = 5
# 3 gewone kleuren x 27 + troefkleur 60 + laatste slag 5.
TOTAAL_PUNTEN = 146


def _sterkte_tabel(volgorde: Sequence[Rank]) -> dict:
    return {rang: len(volgorde) - i for i, rang in enumerate(volgorde)}


_GEWONE_STERKTE = _sterkte_tabel(GEWONE_VOLGORDE)
_TROEF_STERKTE = _sterkte_tabel(TROEF_VOLGORDE)


def kaart_punten(kaart: Card, troef: Optional[Suit]) -> int:
    """Punten van één kaart. Zonder troef (troef=None) gelden de gewone waarden."""
    if troef is not None and kaart.suit is troef:
        return TROEF_PUNTEN.get(kaart.rank, 0)
    return GEWONE_PUNTEN.get(kaart.rank, 0)


def maak_spel() -> list:
    """De 33 kaarten van pandoeren."""
    spel = [Card(k, r) for k in Suit for r in Rank if r >= Rank.ZEVEN]
    spel.append(Card(Suit.HARTEN, Rank.ZES))
    return spel


def deel(rng: Optional[random.Random] = None):
    """Schud en deel: vier kaarten per speler, één open kaart in het midden
    (de 'kijkkaart'), dan nog vier per speler.

    Geeft (handen, kijkkaart). Speler 0 is degene die het eerst aan de beurt is;
    wie de deler is, regelt de spelmodule.
    """
    rng = rng or random.Random()
    spel = maak_spel()
    rng.shuffle(spel)
    it = iter(spel)

    def vier() -> list:
        return [next(it) for _ in range(4)]

    handen = [vier() for _ in range(4)]
    kijkkaart = next(it)
    for hand in handen:
        hand.extend(vier())
    return handen, kijkkaart


def sorteer(hand: Sequence[Card]) -> list:
    """Handige weergavevolgorde: per kleur, hoog naar laag."""
    return sorted(hand, key=lambda k: (k.suit.value, -int(k.rank)))


def slag_winnaar(gespeeld: Sequence, troef: Optional[Suit]) -> int:
    """Wie wint de slag?

    `gespeeld` is een lijst van (speler, kaart) in de volgorde van spelen; de
    eerste kaart bepaalt de gevraagde kleur. Hoogste troef wint, anders de
    hoogste kaart van de gevraagde kleur.
    """
    gevraagd = gespeeld[0][1].suit

    def sterkte(item):
        _, kaart = item
        if troef is not None and kaart.suit is troef:
            return (2, _TROEF_STERKTE[kaart.rank])
        if kaart.suit is gevraagd:
            return (1, _GEWONE_STERKTE[kaart.rank])
        return (0, 0)

    return max(gespeeld, key=sterkte)[0]


def is_hogere_troef(kaart: Card, ander: Card) -> bool:
    """Is `kaart` een sterkere troef dan `ander`? (Beide worden als troef gezien.)"""
    return _TROEF_STERKTE[kaart.rank] > _TROEF_STERKTE[ander.rank]
