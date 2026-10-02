#!/usr/bin/env python3
"""Speel pandoeren in de terminal: jij tegen drie eenvoudige computerspelers.

Dit is nog geen client, alleen een manier om de spelmodule (`pandoeren/spel.py`)
uit te proberen zonder een test te schrijven. Draai het vanuit de projectmap:

    python3 speeltest.py

De computerspelers bieden nog niet (ze passen altijd), dus jij bent altijd de
bieder. Kies een spel dat al gebouwd is: punten (met een getal), misère,
misère ouvert, pandoer of privé. Als iedereen past, wordt er opnieuw gedeeld.
"""
from __future__ import annotations

import random

from pandoeren.cards import Card, Rank, Suit, sorteer
from pandoeren.spel import (
    EenvoudigeSpeler, GEIMPLEMENTEERD, maat_indien_onthuld, speel_ronde,
)
from pandoeren.spelregels import legale_kaarten
from pandoeren.variant import MIDDEN_NEDERLAND, Bod

KLEUR_LETTER = {"S": Suit.SCHOPPEN, "H": Suit.HARTEN, "R": Suit.RUITEN, "K": Suit.KLAVEREN}
RANG_LETTER = {"6": Rank.ZES, "7": Rank.ZEVEN, "8": Rank.ACHT, "9": Rank.NEGEN,
               "10": Rank.TIEN, "B": Rank.BOER, "V": Rank.VROUW,
               "H": Rank.HEER, "A": Rank.AAS}
NAAM = {0: "jij", 1: "Piet", 2: "Klaas", 3: "Jan"}  # tijdelijke namen voor de bots


def toon_hand(hand) -> str:
    return " ".join(f"{i}:{k}" for i, k in enumerate(sorteer(hand)))


def kies_kleur(vraag: str) -> Suit:
    while True:
        antwoord = input(f"{vraag} (S/H/R/K): ").strip().upper()
        if antwoord in KLEUR_LETTER:
            return KLEUR_LETTER[antwoord]
        print("  Onbekende kleur, probeer S(choppen)/H(arten)/R(uiten)/K(laveren).")


class MenselijkeSpeler:
    """Speler die alles via de terminal aan jou vraagt."""

    def __init__(self):
        self._maat_onthuld = False

    def nieuwe_ronde(self) -> None:
        """Aanroepen aan het begin van elke ronde: de maat is dan nog niet
        onthuld, ongeacht wat er in de vorige ronde gebeurde."""
        self._maat_onthuld = False

    def bieden(self, hand, huidig_hoogste, kijkkaart, variant):
        gesorteerd = sorteer(hand)
        print(f"\nJouw hand: {toon_hand(gesorteerd)}")
        print(f"Kijkkaart op tafel: {kijkkaart}")
        if huidig_hoogste is None:
            print("Hoogste bod tot nu toe: nog niemand.")
        else:
            print(f"Hoogste bod tot nu toe: {huidig_hoogste}")
        print("Bekende spellen: " + ", ".join(sorted(GEIMPLEMENTEERD)))
        while True:
            antwoord = input(
                "Jouw bod (bijv. 'punten 150', 'misere', 'pandoer', of 'pas'): "
            ).strip().lower()
            if antwoord in ("pas", "p", ""):
                return None
            delen = antwoord.split()
            soort = delen[0]
            if soort not in GEIMPLEMENTEERD:
                print(f"  '{soort}' is nog niet gebouwd. Kies uit: {', '.join(sorted(GEIMPLEMENTEERD))}, of 'pas'.")
                continue
            doel = None
            if soort == "punten":
                if len(delen) != 2 or not delen[1].isdigit():
                    print("  Geef bij 'punten' ook een aantal, bijv. 'punten 150'.")
                    continue
                doel = int(delen[1])
            bod = Bod(soort, doel)
            try:
                if variant.is_hoger(bod, huidig_hoogste):
                    return bod
                print(f"  '{bod}' is niet hoger dan '{huidig_hoogste}'.")
            except ValueError as e:
                print(f"  {e}")

    def kies_troef_en_aas(self, hand, variant):
        print(f"\nJouw hand (na de kijkkaart-ruil): {toon_hand(sorteer(hand))}")
        troef = kies_kleur("Welke kleur wordt troef?")
        # De troefkleur zelf mag je niet vragen: daar geldt de troefvolgorde
        # (boer, negen, aas, ...) en niet de gewone -- een "gevraagd aas" in
        # troef is geen zinnig verzoek.
        eigen_azen = {k.suit for k in hand if k.rank is Rank.AAS}
        vrije_kleuren = [s for s in Suit if s not in eigen_azen and s != troef]
        if vrije_kleuren:
            print("Je vraagt de aas van een kleur die je zelf niet hebt (niet de troefkleur).")
            kleur = kies_kleur("Van welke kleur vraag je de aas?")
            while kleur in eigen_azen or kleur == troef:
                print("  Die aas heb je zelf al, of het is de troefkleur -- kies een andere kleur.")
                kleur = kies_kleur("Van welke kleur vraag je de aas?")
            return troef, Card(kleur, Rank.AAS)
        print("Je hebt alle andere azen al zelf: je vraagt dus een heer (niet van troef).")
        kleur = kies_kleur("Van welke kleur vraag je de heer?")
        while kleur == troef:
            print("  Dat is de troefkleur, kies een andere kleur.")
            kleur = kies_kleur("Van welke kleur vraag je de heer?")
        return troef, Card(kleur, Rank.HEER)

    def kies_troef(self, hand, variant):
        print(f"\nJouw hand (na de kijkkaart-ruil): {toon_hand(sorteer(hand))}")
        return kies_kleur("Welke kleur wordt troef?")

    def kies_troef_voor_kereltje(self, hand, variant):
        print(f"\nJouw hand (na de kijkkaart-ruil): {toon_hand(sorteer(hand))}")
        eigen_boeren = {k.suit for k in hand if k.rank is Rank.BOER}
        print("Bij kereltje mag je geen kleur kiezen waarvan je zelf de boer hebt "
              "(wie de troefboer heeft wordt automatisch je partner).")
        kleur = kies_kleur("Welke kleur wordt troef?")
        while kleur in eigen_boeren:
            print("  Die boer heb je zelf, kies een andere kleur.")
            kleur = kies_kleur("Welke kleur wordt troef?")
        return kleur

    def leg_af(self, hand_met_kijkkaart, variant):
        kijkkaart = hand_met_kijkkaart[-1]
        gesorteerd = sorteer(hand_met_kijkkaart)
        weergave = " ".join(
            f"{i}:{k}" + (" (kijkkaart)" if k == kijkkaart else "")
            for i, k in enumerate(gesorteerd)
        )
        print(f"\nJe hebt het bod gewonnen! Je 9 kaarten (met de kijkkaart erbij): {weergave}")
        print("Ruilen is niet verplicht: leg je de kijkkaart terug, dan speel "
              "je verder met je eigen 8 kaarten.")
        while True:
            antwoord = input("Welke kaart leg je gedekt weg (nummer)? ").strip()
            if antwoord.isdigit() and int(antwoord) < len(gesorteerd):
                return gesorteerd[int(antwoord)]
            print("  Ongeldig nummer.")

    def speel_kaart(self, zicht, variant):
        if not self._maat_onthuld:
            maat = maat_indien_onthuld(zicht, mijn_index=0)
            if maat is not None:
                self._maat_onthuld = True
                print(f"\n>> Maat: {NAAM[maat]}")
        if zicht.huidige_slag:
            gespeeld = ", ".join(f"{NAAM[s]}: {k}" for s, k in zicht.huidige_slag)
            print(f"\nDeze slag tot nu toe -- {gespeeld}")
        else:
            print("\nJij speelt uit voor deze slag.")
        mogelijk = legale_kaarten(zicht.hand, zicht.huidige_slag, zicht.troef, variant)
        gesorteerd = sorteer(mogelijk)
        print(f"Jouw hand: {toon_hand(sorteer(zicht.hand))}")
        print(f"Kaarten die je mag spelen: {toon_hand(gesorteerd)}")
        while True:
            antwoord = input("Welke kaart speel je (nummer)? ").strip()
            if antwoord.isdigit() and int(antwoord) < len(gesorteerd):
                return gesorteerd[int(antwoord)]
            print("  Ongeldig nummer.")

    def _meld(self, aangeboden, waar: str):
        """Gedeelde implementatie voor meld_roem/meld_tafelroem: toont de nog
        te melden roem en laat je kiezen welke je nu meldt. Vergeet je er
        een, dan is hij straks kwijt -- zie `roem.RoemClaim`."""
        if not aangeboden:
            return []
        print(f"\nJe hebt roem {waar} die je nu kunt melden (anders ben je hem straks kwijt!):")
        for i, claim in enumerate(aangeboden):
            print(f"  {i}: {claim.omschrijving} ({claim.punten} punten)")
        antwoord = input(
            "Welke meld je nu? (nummers gescheiden door spaties, 'alles', of leeg voor geen): "
        ).strip().lower()
        if antwoord == "alles":
            return list(aangeboden)
        if not antwoord:
            return []
        gekozen = []
        for stuk in antwoord.split():
            if stuk.isdigit() and int(stuk) < len(aangeboden):
                gekozen.append(aangeboden[int(stuk)])
        return gekozen

    def meld_roem(self, aangeboden, variant):
        return self._meld(aangeboden, "in je hand")

    def meld_tafelroem(self, aangeboden, variant):
        return self._meld(aangeboden, "op tafel (deze slag)")

    def toon_tafelroem(self, winnaar, gemeld, slag_nummer):
        for claim in gemeld:
            print(f">> {NAAM[winnaar]} meldt {claim.omschrijving}, {claim.punten} roem "
                  f"(slag {slag_nummer})")


def toon_resultaat(resultaat) -> None:
    if resultaat is None:
        print("\nIedereen paste (rondpassen) -- opnieuw delen.")
        return
    print(f"\n== Uitslag ==")
    print(f"Contract: {resultaat.contract} -- bieder: {NAAM[resultaat.bieder]}"
          + (f", partner: {NAAM[resultaat.partner]}" if resultaat.partner is not None else ""))
    if resultaat.punten_team is not None:
        roem_tekst = f" (waarvan {resultaat.roem_team} roem)" if resultaat.roem_team else ""
        print(f"Team van de bieder haalde {resultaat.punten_team} punten{roem_tekst}.")
        for m in resultaat.roem_meldingen:
            plek = f"in de hand van {NAAM[m.speler]}" if m.plaats == "hand" else (
                f"op tafel (slag {m.slag_nummer}, gewonnen door {NAAM[m.speler]})"
            )
            print(f"    {m.omschrijving}: {m.punten} punten, {plek}")
    print("Gehaald!" if resultaat.geslaagd else "Niet gehaald.")
    for speler, bedrag in sorted(resultaat.centen.items()):
        print(f"  {NAAM[speler]}: {bedrag:+d} cent")


def main() -> None:
    print(__doc__)
    spelers = [MenselijkeSpeler(), EenvoudigeSpeler(), EenvoudigeSpeler(), EenvoudigeSpeler()]
    totalen = {i: 0 for i in range(4)}
    pot = 4 * MIDDEN_NEDERLAND.lappen  # eenmalig ingelegd bij het begin van het spel
    print(f"\nIedereen legt eenmalig {MIDDEN_NEDERLAND.lappen} cent in: de pot begint op {pot} cent.")
    rng = random.Random()
    ronde = 0
    while True:
        voorhand = ronde % 4
        print(f"\n{'=' * 60}\nRonde {ronde + 1} -- deler/voorhand: {NAAM[voorhand]}")
        spelers[0].nieuwe_ronde()
        try:
            resultaat = speel_ronde(spelers, MIDDEN_NEDERLAND, rng, voorhand)
        except NotImplementedError as e:
            print(f"\n{e}")
            ronde += 1
            continue
        toon_resultaat(resultaat)
        if resultaat is not None:
            for speler, bedrag in resultaat.centen.items():
                totalen[speler] += bedrag
                pot -= bedrag  # winst wordt uit de pot gehaald, verlies erin terugbetaald
        print("\nStand: " + ", ".join(f"{NAAM[i]} {totalen[i]:+d}" for i in range(4))
              + f"  --  Pot: {pot} cent")
        ronde += 1
        if input("\nNog een ronde? (j/n): ").strip().lower().startswith("n"):
            break
    print("\nTot de volgende keer!")


if __name__ == "__main__":
    main()
