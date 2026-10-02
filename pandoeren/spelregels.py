"""Welke kaart mag je bijspelen?

De regels komen uit Butselaar (1958), Algemene Bepalingen 7-9, en staan als
instellingen in `Variant` waar het boekje zelf ruimte laat:

- Zonder troef: bekennen als je kunt, anders alles.
- Met troef en de gevraagde kleur is troef: je moet troef bijspelen als je
  troeven hebt. Overtroeven (hoger dan wat al ligt) is bij Butselaar nooit
  verplicht (`overtroeven_verplicht`, standaard False): elke troef mag.
- Met troef en een andere kleur is gevraagd:
  - Kun je bekennen: bekennen, of (optioneel, `troeven_bij_bekennen`) troeven
    met een willekeurige troef. "Troeven mag men altijd, maar verplicht is
    het niet" (Butselaar, regel 7).
  - Kun je niet bekennen: alles mag, troef of een andere kleur ("Pas als men
    geen kaarten van de gevraagde kleur heeft, mag men bijspelen wat men
    wil.").
- De troefboer (de 'jas') hoeft nooit gespeeld te worden, behalve als het de
  enige troef is die je nog hebt in de laatste slag (Butselaar, regel 9:
  "Als hij meer troefkaarten heeft moet hij deze wel bijspelen!").
"""
from __future__ import annotations

from typing import Optional, Sequence

from .cards import Card, Rank, Suit, is_hogere_troef
from .variant import Variant


def _mogelijk(hand: Sequence[Card], gespeeld: Sequence, troef: Optional[Suit],
              variant: Variant) -> list:
    """Toegestane kaarten, zonder rekening te houden met de jas-uitzondering."""
    if not gespeeld:
        return list(hand)

    gevraagd = gespeeld[0][1].suit

    # Zonder troef: bekennen als je kunt, anders alles.
    if troef is None:
        volg = [k for k in hand if k.suit is gevraagd]
        return volg or list(hand)

    troeven = [k for k in hand if k.suit is troef]

    if gevraagd is troef:
        if not troeven:
            return list(hand)
        if not variant.overtroeven_verplicht:
            return troeven
        op_tafel = [k for _, k in gespeeld if k.suit is troef]
        hoogste = None
        for k in op_tafel:
            if hoogste is None or is_hogere_troef(k, hoogste):
                hoogste = k
        hogere = [k for k in troeven if hoogste is None or is_hogere_troef(k, hoogste)]
        return hogere or troeven

    volg = [k for k in hand if k.suit is gevraagd]
    if volg:
        return volg + (troeven if variant.troeven_bij_bekennen else [])

    # Kan niet bekennen: alles mag.
    return list(hand)


def legale_kaarten(hand: Sequence[Card], gespeeld: Sequence, troef: Optional[Suit],
                   variant: Variant) -> list:
    """Kaarten die de speler nu mag spelen.

    `gespeeld` is de lijst (speler, kaart) van de huidige slag, in volgorde;
    leeg als de speler uitkomt.
    """
    mogelijk = _mogelijk(hand, gespeeld, troef, variant)

    if variant.jas_nooit_verplicht and troef is not None:
        jas = Card(troef, Rank.BOER)
        rest = [k for k in hand if k != jas]
        if jas in hand and rest:  # in de laatste slag heb je alleen de jas nog
            for k in _mogelijk(rest, gespeeld, troef, variant):
                if k not in mogelijk:
                    mogelijk.append(k)
    return mogelijk
