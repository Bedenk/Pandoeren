"""Roem (combinaties in je hand) en stuk.

Reeksen tellen altijd in de volgorde aas-heer-vrouw-boer-10-9-8-7-6, ook in de
troefkleur. Roem is 'beter' naarmate de soort verderop in `_SOORT_VOLGORDE`
staat; bij gelijke soort wint de hoogste kaart, en daarna de hoogste kleur
(schoppen, harten, ruiten, klaveren).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from .cards import Card, Rank, Suit

REEKS_PUNTEN = {3: 20, 4: 50, 5: 100, 6: 120, 7: 140, 8: 160}
MAX_REEKS = 8  # een hand heeft 8 kaarten; bij 9 (met kijkkaart) tellen we als 8
VIER_GELIJKE = {
    Rank.VROUW: ("vier_vrouwen", 100, "vrouwen"),
    Rank.HEER: ("vier_heren", 100, "heren"),
    Rank.AAS: ("vier_azen", 100, "azen"),
    Rank.BOER: ("vier_boeren", 200, "boeren"),
}
STUK_PUNTEN = 20  # heer + vrouw van troef; kan niet worden ontkend

# Laag -> hoog. Vier gelijke staan boven een 5-reeks, ondanks gelijke punten.
_SOORT_VOLGORDE = [
    "reeks3", "reeks4", "reeks5",
    "vier_vrouwen", "vier_heren", "vier_azen",
    "reeks6", "reeks7", "reeks8",
    "vier_boeren",
]


@dataclass(frozen=True)
class Roem:
    soort: str
    kaarten: frozenset
    punten: int
    hoogste: Rank
    kleur: Optional[Suit]  # None bij vier gelijke

    @property
    def sleutel(self) -> tuple:
        """Sorteersleutel: groter = betere roem. Gebruikt om roem te ontkennen."""
        return (
            _SOORT_VOLGORDE.index(self.soort),
            int(self.hoogste),
            self.kleur.sterkte if self.kleur else 0,
        )

    def __str__(self) -> str:
        if self.kleur is None:
            return f"vier {VIER_GELIJKE[self.hoogste][2]}"
        return f"{len(self.kaarten)}-reeks, hoogste {self.hoogste.naam} {self.kleur.value}"


def _kandidaten(hand: Iterable[Card]) -> list:
    """Alle losse roem-mogelijkheden in een hand, ook delen van langere reeksen."""
    kaarten = set(hand)
    kandidaten = []

    for kleur in Suit:
        rangen = sorted(int(k.rank) for k in kaarten if k.suit is kleur)
        reeksen, huidig = [], []
        for r in rangen:
            if huidig and r == huidig[-1] + 1:
                huidig.append(r)
            else:
                if huidig:
                    reeksen.append(huidig)
                huidig = [r]
        if huidig:
            reeksen.append(huidig)

        for reeks in reeksen:
            for lengte in range(3, len(reeks) + 1):
                for start in range(len(reeks) - lengte + 1):
                    deel = reeks[start:start + lengte]
                    l = min(lengte, MAX_REEKS)
                    kandidaten.append(Roem(
                        soort=f"reeks{l}",
                        kaarten=frozenset(Card(kleur, Rank(r)) for r in deel),
                        punten=REEKS_PUNTEN[l],
                        hoogste=Rank(deel[-1]),
                        kleur=kleur,
                    ))

    for rang, (soort, punten, _) in VIER_GELIJKE.items():
        vier = frozenset(Card(k, rang) for k in Suit)
        if vier <= kaarten:
            kandidaten.append(Roem(soort, vier, punten, rang, None))
    return kandidaten


def _beste_los(kandidaten: list) -> tuple:
    """Beste verzameling roem waarin geen kaart twee keer meetelt."""
    beste = (0, ())

    def zoek(i: int, gebruikt: frozenset, punten: int, gekozen: list) -> None:
        nonlocal beste
        if punten > beste[0]:
            beste = (punten, tuple(gekozen))
        for j in range(i, len(kandidaten)):
            k = kandidaten[j]
            if gebruikt.isdisjoint(k.kaarten):
                gekozen.append(k)
                zoek(j + 1, gebruikt | k.kaarten, punten + k.punten, gekozen)
                gekozen.pop()

    zoek(0, frozenset(), 0, [])
    return beste


def beste_roem(hand: Iterable[Card], kaarten_dubbel_gebruiken: bool = False) -> tuple:
    """Totale roem van een hand: (punten, combinaties).

    Standaard mag een kaart maar in één combinatie meetellen (bijv. bij vier
    vrouwen plus vrouw-boer-10-9 telt óf de reeks, óf de vier vrouwen met de
    overgebleven boer-10-9). Of dat in jullie variant zo is, is nog niet zeker;
    met `kaarten_dubbel_gebruiken=True` mogen reeksen en vier-gelijke elkaar
    overlappen.
    """
    kandidaten = _kandidaten(hand)
    if not kaarten_dubbel_gebruiken:
        return _beste_los(kandidaten)

    reeksen = [k for k in kandidaten if k.kleur is not None]
    vieren = [k for k in kandidaten if k.kleur is None]
    punten, gekozen = _beste_los(reeksen)
    gekozen = list(gekozen) + vieren
    return punten + sum(v.punten for v in vieren), tuple(gekozen)


def hoogste_enkele_roem(hand: Iterable[Card]) -> Optional[Roem]:
    """De 'beste' losse roem in de hand; hiermee wordt roem ontkend."""
    kandidaten = _kandidaten(hand)
    return max(kandidaten, key=lambda k: k.sleutel) if kandidaten else None


def kan_ontkennen(bewering: Optional[Roem], hand_tegenstander: Iterable[Card]) -> bool:
    """Kan een tegenstander de geclaimde hoogste roem ontkennen?

    Dat kan als zijn eigen hoogste enkele roem strikt beter is."""
    if bewering is None:
        return False
    eigen = hoogste_enkele_roem(hand_tegenstander)
    return eigen is not None and eigen.sleutel > bewering.sleutel


def heeft_stuk(hand: Iterable[Card], troef: Optional[Suit]) -> bool:
    """Heer én vrouw van troef in dezelfde hand."""
    if troef is None:
        return False
    kaarten = set(hand)
    return Card(troef, Rank.HEER) in kaarten and Card(troef, Rank.VROUW) in kaarten


def roem_totaal(hand: Iterable[Card], troef: Optional[Suit],
                kaarten_dubbel_gebruiken: bool = False) -> int:
    """Roem plus stuk. Stuk (heer + vrouw van troef) telt altijd extra mee, ook
    als die kaarten al in een andere combinatie zitten."""
    hand = list(hand)
    punten, _ = beste_roem(hand, kaarten_dubbel_gebruiken)
    return punten + (STUK_PUNTEN if heeft_stuk(hand, troef) else 0)


@dataclass(frozen=True)
class RoemClaim:
    """Eén roem-mogelijkheid die een speler moet MELDEN voordat alle kaarten
    die erbij horen gespeeld zijn -- vergeet hij dat, dan is hij de punten
    kwijt (Butselaar, blz. 12, letterlijk zo beschreven voor 'stuk': "Vergeet
    men 'stuk' te roemen, dan is men dus 20 punten kwijt ... hetgeen soms
    verlies van het spel ten gevolge kan hebben." Melden mag nog tot vlak
    vóór de laatste nog ongespeelde kaart van de combinatie valt -- ook als
    een eerdere kaart ervan al wel gespeeld is (Butselaar geeft dit expliciet
    als voorbeeld bij stuk: vergeet je het bij de vrouw, dan mag het alsnog
    bij de heer). Dezelfde melding-of-vervallen-regel wordt hier ook
    toegepast op reeksen en vier-gelijke in de hand, en (zie
    `tafel_roem_claims`) op roem die op tafel ontstaat -- dat laatste staat
    niet letterlijk zo in het boekje, zie de toelichting daar."""
    omschrijving: str
    kaarten: frozenset
    punten: int


def hand_roem_claims(hand: Iterable[Card], kaarten_dubbel_gebruiken: bool = False) -> list:
    """Reeksen en vier-gelijke in deze hand, als losse, te melden
    `RoemClaim`s -- dus zonder de niet-overlappende 'beste combinatie'-keuze
    van `beste_roem` (die blijft nodig voor het ontken-mechanisme, dat werkt
    nog steeds op de hele hand). Stuk zit hier bewust niet bij: dat kan niet
    ontkend worden en wordt apart gevolgd, zie `stuk_claim`."""
    _, combinaties = beste_roem(hand, kaarten_dubbel_gebruiken)
    return [
        RoemClaim(omschrijving=str(r), kaarten=r.kaarten, punten=r.punten)
        for r in combinaties
    ]


def stuk_claim(hand: Iterable[Card], troef: Optional[Suit]) -> Optional[RoemClaim]:
    """Stuk (heer + vrouw van troef) in deze hand, als te melden `RoemClaim`,
    of None als de hand geen stuk heeft."""
    if not heeft_stuk(hand, troef):
        return None
    return RoemClaim(
        omschrijving="stuk",
        kaarten=frozenset({Card(troef, Rank.HEER), Card(troef, Rank.VROUW)}),
        punten=STUK_PUNTEN,
    )


def tafel_roem_claims(slag: Iterable, troef: Optional[Suit]) -> list:
    """Roem die kan ontstaan uit de kaarten die in één (afgeronde) slag
    vielen, ongeacht wie welke kaart speelde: een reeks van 3 of 4
    opeenvolgende kaarten van dezelfde kleur, of stuk (heer + vrouw van
    troef) -- gevormd door de vier kaarten van déze slag.

    AANNAME, NIET BEVESTIGD DOOR HET BOEKJE (zie gesprek met de gebruiker,
    2026-10-02): Butselaar beschrijft roem alleen als iets in de eigen hand.
    De gebruiker is desondanks zeker dat roem ook zo op tafel kan vallen
    (bijv.: bieder speelt troefboer uit, zijn maat gooit troefheer bij, een
    tegenstander moet gedwongen troefvrouw bijleggen -- dat is dan stuk, met
    heer en vrouw uit twee verschillende handen) en heeft gevraagd dit zo te
    bouwen, met deze aantekening. Net als in de hand moet dit gemeld worden
    (zie `RoemClaim`) en mag niet over kleuren heen gemengd worden -- 'vier
    gelijke' (vier kaarten van dezelfde rang maar verschillende kleur) telt
    hier daarom nooit mee, die vereist per definitie vier verschillende
    kleuren. Een slag heeft hoogstens 4 kaarten, dus een reeks van 5 of meer
    kan hier sowieso niet voorkomen."""
    kaarten = [kaart for _, kaart in slag]
    reeks_kandidaten = [r for r in _kandidaten(kaarten) if r.kleur is not None]
    # Net als in de hand: alleen de beste, niet-overlappende keuze (dus bij
    # 4 opeenvolgende kaarten de reeks4, niet ook nog de overlappende
    # reeks3'en die daar deel van uitmaken).
    _, beste = _beste_los(reeks_kandidaten)
    claims = [RoemClaim(omschrijving=str(r), kaarten=r.kaarten, punten=r.punten) for r in beste]
    if troef is not None and heeft_stuk(kaarten, troef):
        claims.append(RoemClaim(
            omschrijving="stuk (op tafel)",
            kaarten=frozenset({Card(troef, Rank.HEER), Card(troef, Rank.VROUW)}),
            punten=STUK_PUNTEN,
        ))
    return claims
