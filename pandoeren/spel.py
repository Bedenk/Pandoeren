"""De spelmodule: bieden, troef en partner kiezen, slagen spelen, roem en
afrekenen in centen.

Dit bestand knoopt `cards.py`, `roem.py`, `spelregels.py` en `variant.py` aan
elkaar tot een speelbare ronde. Een "speler" hier is willekeurig wie of wat er
aan die stoel zit: een computerspeler, een mens die op een scherm klikt, of
straks iemand die via internet meespeelt. De engine vraagt alleen wat iemand
biedt, welke troef en partner hij kiest, welke kaart hij weglegt en welke hij
speelt — het maakt niet uit waar dat antwoord vandaan komt. Zie `Speler`.

Geïmplementeerd -- alle veertien spellen uit `variant.CONTRACTEN`:
- puntenspel en pandoer: partner is een geroepen aas.
- kereltje: partner is wie de troefboer heeft. De bieder mag zelf geen troef
  kiezen waarvan hij de boer al heeft (dat zou geen kereltje meer zijn, maar
  in feite een goedkope privé) — hij kiest dus altijd een kleur die iemand
  anders' boer als partner oplevert.
- zwabber: partner is wie de eerste slag wint (blijkt pas na die slag); wint
  de bieder zelf de eerste slag, dan speelt hij alleen. Geen troef.
- misère, misère ouvert, stil praatje, praatje, privé en solo-zwabber: alleen,
  geen partner. Allemaal met troef, behalve solo-zwabber.
- piccolo, piccolo ouvert, stil piccolo-praatje en piccolo-praatje: alleen;
  moeten precies één slag halen, en wel met de troefboer.

Wat deze module bewust NIET regelt (dat hoort bij de toekomstige client):
- bij misère ouvert, stil praatje, piccolo ouvert en stil piccolo-praatje
  liggen na de eerste slag alle kaarten van de bieder (en bij stil
  praatje/piccolo-praatje: van iedereen) open op tafel;
- bij stil praatje en stil piccolo-praatje mogen de tegenstanders niet meer
  overleggen, bij praatje en piccolo-praatje juist wel;
- bij een geroepen aas of praatje wordt er niet gecommuniceerd over de kaarten
  zelf, alleen over wie waar zit -- de chat-regels ("stil" legt de
  tegenstanders het zwijgen op) horen dus ook bij de client, niet bij de
  score die deze module berekent.

Vereenvoudiging: bij een geroepen aas kent de engine de partner vanaf het
begin (nodig om de punten toe te delen). Aan tafel maakt de partner zich pas
bekend door slagen op te nemen (Butselaar, regel 10) — dat is een kwestie van
presentatie aan het scherm, niet van de telling, en hoort dus bij de
toekomstige client, niet bij deze module.

Voor de grafische (Qt-)client, ontwerpnotitie over de kijkkaart-ruil: dit is
niet alleen een keuze van de bieder, het is ook informatie die alle spelers
aan tafel gewoon kunnen zien, en dus moet de client dat straks ook laten zien:
- De kijkkaart ligt vanaf het delen open op tafel, voor iedereen zichtbaar
  (ook al vóór het bieden) — welke kaart het is, is dus nooit een verrassing.
- Neemt de bieder de kijkkaart aan, dan legt hij de kaart die hij ervoor
  inruilt gesloten (dus onzichtbaar voor de anderen) weg. De tegenspelers zien
  dan wel dát er geruild is (de kijkkaart verdwijnt van tafel, hij zit nu in
  de hand van de bieder) maar niet welke kaart daarvoor is ingeleverd.
- Wijst de bieder de kijkkaart af, dan is de kijkkaart zelf de kaart die uit
  het spel gaat — en die kaart was al bekend, dus daar is niets nieuws te zien.
Kortom: "geruild of niet" is altijd publieke informatie, "welke kaart er bij
een ruil is ingeleverd" nooit. Dat onderscheid hoort de engine straks door te
geven aan élke speler (mens én AI), niet alleen aan de bieder zelf — nu geeft
`speel_ronde` de uitkomst van `leg_af` alleen aan de bieder, verder aan niemand.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional, Protocol, Sequence

from .cards import Card, Rank, Suit, deel, kaart_punten, slag_winnaar, LAATSTE_SLAG_PUNTEN
from .roem import (
    RoemClaim, hand_roem_claims, hoogste_enkele_roem, kan_ontkennen,
    stuk_claim, tafel_roem_claims,
)
from .spelregels import legale_kaarten
from .variant import CONTRACTEN, Bod, Variant

GEROEPEN_AAS_SOORTEN = {"punten", "pandoer"}
TROEFBOER_PARTNER_SOORTEN = {"kereltje"}       # partner is wie de troefboer heeft
EERSTE_SLAG_PARTNER_SOORTEN = {"zwabber"}      # partner is wie de eerste slag wint
ALLE_SLAGEN_MET_PARTNER_SOORTEN = {"pandoer"} | TROEFBOER_PARTNER_SOORTEN | EERSTE_SLAG_PARTNER_SOORTEN
NUL_SLAGEN_SOORTEN = {"misere", "misere_ouvert", "stil_praatje", "praatje"}
ALLE_SLAGEN_ALLEEN_SOORTEN = {"pandoer_prive", "solo_zwabber"}
SOLO_SOORTEN = NUL_SLAGEN_SOORTEN | ALLE_SLAGEN_ALLEEN_SOORTEN
PICCOLO_SOORTEN = {"piccolo", "piccolo_ouvert", "stil_piccolo_praatje", "piccolo_praatje"}
GEIMPLEMENTEERD = (
    GEROEPEN_AAS_SOORTEN | TROEFBOER_PARTNER_SOORTEN | EERSTE_SLAG_PARTNER_SOORTEN
    | SOLO_SOORTEN | PICCOLO_SOORTEN
)


@dataclass
class Zicht:
    """Wat één speler op dit moment mag zien, om een kaart te kiezen."""

    ik: int
    hand: list
    troef: Optional[Suit]
    contract: Bod
    bieder: int
    partner: Optional[int]
    huidige_slag: list = field(default_factory=list)      # [(speler, kaart), ...]
    gespeelde_slagen: list = field(default_factory=list)   # per slag: (winnaar, [(speler,kaart),...])
    gevraagde_kaart: Optional[Card] = None
    # Bij punten/pandoer (geroepen aas): de kaart die de bieder heeft
    # gevraagd. `partner` hierboven staat vanaf de eerste slag al vast (de
    # spelmodule weet het meteen), maar dat is spel-interne informatie -- wie
    # aan tafel eigenlijk maat is, blijkt pas als het spel het zelf verraadt:
    # zodra deze kaart gespeeld wordt, of zodra de bieder zelf zijn eerste
    # slag binnenhaalt (Butselaar: de maat haalt die slag dan van tafel). Een
    # client kan met `gevraagde_kaart` en `gespeelde_slagen`/`huidige_slag`
    # dus zelf bepalen wanneer dat moment daar is, in plaats van `partner`
    # vanaf slag 1 te verklappen.


def maat_indien_onthuld(zicht: "Zicht", mijn_index: int) -> Optional[int]:
    """Wie is mijn maat, voor zover dat al aan tafel bekend zou zijn?

    `zicht.partner` staat spel-intern al vanaf slag 1 vast, maar volgens
    Butselaar wordt het pas aan tafel duidelijk zodra de gevraagde kaart
    gespeeld is, of zodra de BIEDER zelf zijn eerste slag binnenhaalt (de
    maat haalt die slag dan van tafel). Wint de maat zelf een slag zonder
    dat daarbij de gevraagde kaart gespeeld is, dan verraadt dat aan tafel
    nog niets: niemand kan aan een willekeurige slagwinst zien dat die
    winnaar de maat is, dus dat telt hier niet als onthulling. Deze functie
    geeft de index van mijn maat pas zodra een van de twee echte
    onthulmomenten al gebeurd is in
    `zicht.gespeelde_slagen`/`zicht.huidige_slag`, en anders `None` -- ook
    als de spelmodule het antwoord intern al zou weten.

    Geeft ook `None` als ikzelf (`mijn_index`) geen bieder en geen maat
    ben (bijv. tegenstander, of een spel zonder maat): dan heb ik voor
    dit spel geen eigen maat om te onthullen."""
    if zicht.partner is None:
        return None
    if zicht.bieder == mijn_index:
        maat = zicht.partner
    elif zicht.partner == mijn_index:
        maat = zicht.bieder
    else:
        return None
    if zicht.gevraagde_kaart is not None:
        gespeeld = [k for _, slag in zicht.gespeelde_slagen for _, k in slag]
        gespeeld += [k for _, k in zicht.huidige_slag]
        if zicht.gevraagde_kaart in gespeeld:
            return maat
    if any(winnaar == zicht.bieder for winnaar, _ in zicht.gespeelde_slagen):
        return maat
    return None


class Speler(Protocol):
    def bieden(self, hand: Sequence[Card], huidig_hoogste: Optional[Bod],
               kijkkaart: Card, variant: Variant) -> Optional[Bod]:
        """Geef een hoger bod dan `huidig_hoogste`, of None om te passen.

        `kijkkaart` ligt vanaf het delen open op tafel (Butselaar) -- die is
        dus altijd bekend, ook al vóór je zelf iets biedt, en mag meewegen."""

    def kies_troef_en_aas(self, hand: Sequence[Card], variant: Variant) -> tuple:
        """(troefkleur, aas-of-heer-kaart-die-je-meevraagt) voor puntenspel/pandoer."""

    def kies_troef(self, hand: Sequence[Card], variant: Variant) -> Suit:
        """Troefkleur voor een spel waarbij jij zelf troef kiest zonder een aas
        te roepen: misère, misère ouvert, privé, piccolo, piccolo ouvert, stil
        praatje, stil piccolo-praatje, piccolo-praatje en praatje. Niet voor
        kereltje (zie `kies_troef_voor_kereltje`), en niet voor zwabber of
        solo-zwabber: die twee spelen zonder troef."""

    def kies_troef_voor_kereltje(self, hand: Sequence[Card], variant: Variant) -> Suit:
        """Troefkleur voor kereltje. Kies een kleur waarvan je zelf niet de
        boer hebt: bij kereltje ben je juist afhankelijk van wie de troefboer
        wél heeft (die wordt automatisch je partner) — heb je 'm zelf, dan
        kun je geen kereltje bieden."""

    def leg_af(self, hand_met_kijkkaart: Sequence[Card], variant: Variant) -> Card:
        """Welke van je 9 kaarten (inclusief kijkkaart) leg je gedekt weg?

        Ruilen is niet verplicht (Butselaar): leg je de kijkkaart zelf terug,
        dan speel je verder met je eigen 8 kaarten en gaat de kijkkaart
        ongebruikt uit het spel, net als bij een echte ruil."""

    def speel_kaart(self, zicht: Zicht, variant: Variant) -> Card:
        """Welke kaart speel je? Moet voorkomen in `legale_kaarten(...)`."""

    def meld_roem(self, aangeboden: Sequence[RoemClaim], variant: Variant) -> Sequence[RoemClaim]:
        """Welke van deze (nog niet gemelde, nog volledig in je hand aanwezige)
        roem-mogelijkheden meld je nu? Wordt vlak vóór elke `speel_kaart`
        gevraagd, zolang er nog iets te melden is. Meld je een combinatie
        niet vóórdat de laatste kaart ervan gespeeld is, dan ben je hem kwijt
        (Butselaar, blz. 12 -- zie `RoemClaim`). Geef gewoon de elementen uit
        `aangeboden` terug die je nu meldt (lege lijst/tuple mag ook)."""

    def meld_tafelroem(self, aangeboden: Sequence[RoemClaim], variant: Variant) -> Sequence[RoemClaim]:
        """Zelfde als `meld_roem`, maar dan voor roem die in de zojuist
        gewonnen slag is gevallen (AANNAME, zie `roem.tafel_roem_claims`).
        Wordt alleen gevraagd aan wie de slag net gewonnen heeft."""

    def toon_tafelroem(self, winnaar: int, gemeld: Sequence[RoemClaim], slag_nummer: int) -> None:
        """Puur informatief, geen antwoord nodig: wordt na elke slag aan
        ALLE spelers gemeld zodra `winnaar` daar roem op tafel in heeft
        gemeld (zie `meld_tafelroem`) -- zodat bijvoorbeeld een GUI dit ook
        kan laten zien als het een computerspeler was die meldde, niet
        alleen wanneer de mens zelf de vraag kreeg. Standaard niets doen
        (zie `EenvoudigeSpeler`); een mens-aangestuurde speler kan dit
        gebruiken om even een bannertje te tonen."""


class EenvoudigeSpeler:
    """Een simpele computerspeler: speelt volgens de regels, maar zonder
    slimme strategie. Bruikbaar als eerste tegenstander en voor tests."""

    def __init__(self, rng: Optional[random.Random] = None):
        self.rng = rng or random.Random()

    def bieden(self, hand, huidig_hoogste, kijkkaart, variant):
        return None  # past altijd; een biedende AI is een latere stap

    def kies_troef_en_aas(self, hand, variant):
        # Wanneer mag je een heer in plaats van een aas vragen? Butselaar
        # (blz. 16) geeft alleen het uiterste geval expliciet: heeft de
        # bieder zelf alle azen, dan mag hij een heer meevragen. Dat is één
        # voorbeeld, geen volledige regel -- de algemene regels zeggen er
        # verder niets over. Dit is de generalisatie die hier is gekozen
        # (AANNAME, niet letterlijk zo in het boek): je vraagt altijd eerst
        # de aas van een niet-troefkleur waarvan je zelf de aas niet hebt
        # (vrije keuze als er meerdere zijn); pas als zo'n kleur niet meer
        # bestaat -- dus als je zelf alle niet-troef-azen al hebt -- val je
        # terug op een heer. Of je verder nog kaarten van die kleur hebt
        # (of er juist kaal in zit) speelt geen rol: alleen bezit van de aas
        # zelf telt. Zie ook gesprek met de gebruiker, 2026-10-01.
        tellingen: dict = {}
        for kaart in hand:
            tellingen[kaart.suit] = tellingen.get(kaart.suit, 0) + 1
        troef = max(tellingen, key=lambda s: tellingen[s])
        # De troefkleur zelf komt niet in aanmerking -- OPEN VRAAG, nog niet
        # bevestigd (zie gesprek met gebruiker, 2026-10-01):
        # Butselaar blz. 31-32 zegt, specifiek bij het contract Pandoer:
        # "De speler van Pandoer mag het aas meevragen dat hem het meest
        # lijkt" en wijst de "pas na de andere 3 azen"-school expliciet af
        # ("onze regel lijkt ons het meest eenvoudig") -- bij Pandoer mag
        # troefaas dus blijkbaar gewoon gevraagd worden, zonder voorwaarde.
        # Of dezelfde vrijheid ook geldt bij het puntenspel (dat nu dezelfde
        # functie deelt met pandoer, via GEROEPEN_AAS_SOORTEN) staat nergens
        # letterlijk in het boek. Totdat dat zeker is, sluiten we troef hier
        # voor beide contracten uit -- dat is de voorzichtige/mogelijk te
        # strenge keuze, niet per se de juiste. De gebruiker laat dit
        # uitzoeken via betatesters die het spel kennen; zodra daar
        # duidelijkheid over is (mogelijk met een verschil tussen punten en
        # pandoer), moet dit hier en in `_kies_troef_en_partner` aangepast
        # worden -- let op dat `kies_troef_en_aas` dan ook moet weten welk
        # contract het is (nu krijgt deze methode alleen `hand` en `variant`,
        # geen `bod`).
        eigen_azen = {k.suit for k in hand if k.rank is Rank.AAS}
        kandidaten = [s for s in Suit if s not in eigen_azen and s != troef]
        if kandidaten:
            return troef, Card(self.rng.choice(kandidaten), Rank.AAS)
        # geen kale niet-troef-kleur meer over (bijv. alle 3 andere azen al
        # in eigen hand): vraag dan een heer, ook weer niet van troef.
        kandidaten = [s for s in Suit if Card(s, Rank.HEER) not in hand and s != troef]
        if not kandidaten:
            kandidaten = [s for s in Suit if s != troef]
        kleur = self.rng.choice(kandidaten)
        return troef, Card(kleur, Rank.HEER)

    def kies_troef(self, hand, variant):
        tellingen: dict = {}
        for kaart in hand:
            tellingen[kaart.suit] = tellingen.get(kaart.suit, 0) + 1
        return max(tellingen, key=lambda s: tellingen[s])

    def kies_troef_voor_kereltje(self, hand, variant):
        # Troef kiezen mag altijd een kleur zijn waar je zelf geen kaart van
        # hebt (dus niet beperkt tot de kleuren die in `hand` voorkomen).
        tellingen: dict = {}
        for kaart in hand:
            tellingen[kaart.suit] = tellingen.get(kaart.suit, 0) + 1
        eigen_boeren = {k.suit for k in hand if k.rank is Rank.BOER}
        kandidaten = [s for s in Suit if s not in eigen_boeren]
        if not kandidaten:
            # zeldzaam randgeval: je hebt alle vier de boeren zelf, dan is er
            # geen geldige troefkleur voor kereltje.
            kandidaten = list(Suit)
        return max(kandidaten, key=lambda s: tellingen.get(s, 0))

    def leg_af(self, hand_met_kijkkaart, variant):
        return min(hand_met_kijkkaart, key=lambda k: int(k.rank))

    def speel_kaart(self, zicht, variant):
        mogelijk = legale_kaarten(zicht.hand, zicht.huidige_slag, zicht.troef, variant)
        return mogelijk[0]

    def meld_roem(self, aangeboden, variant):
        # Eenvoudig: meld gewoon alles meteen zodra het kan, zodat deze
        # computerspeler nooit per ongeluk roem kwijtraakt (dat zou geen
        # eerlijke tegenstander zijn -- "vergeten" is een menselijk
        # foutje, geen strategie). Zie ook de TODO's elders over een
        # slimmere AI, nu nog niet aan de orde.
        return list(aangeboden)

    def meld_tafelroem(self, aangeboden, variant):
        return list(aangeboden)

    def toon_tafelroem(self, winnaar, gemeld, slag_nummer):
        pass  # geen GUI/terminal om iets te laten zien


def bied_ronde(spelers: Sequence[Speler], handen: Sequence[Sequence[Card]],
               kijkkaart: Card, variant: Variant, voorhand: int = 0):
    """Wie mag spelen?

    Geeft (bieder, bod, deelgenomen) terug, waarbij `deelgenomen` de spelers
    zijn die minstens één keer echt geboden hebben (nodig om te weten wie
    straks roem mag ontkennen). Geeft None als iedereen meteen past
    ("rondpassen") — de aanroeper regelt dan een nieuwe deling.
    """
    n = len(spelers)
    actief = set(range(n))
    deelgenomen: set = set()
    hoogste: Optional[Bod] = None
    hoogste_speler: Optional[int] = None
    i = voorhand
    while len(actief) > 1 or hoogste_speler is None:
        if i not in actief or i == hoogste_speler:
            i = (i + 1) % n
            continue
        bod = spelers[i].bieden(handen[i], hoogste, kijkkaart, variant)
        if bod is not None and variant.is_hoger(bod, hoogste):
            hoogste, hoogste_speler = bod, i
            deelgenomen.add(i)
        else:
            actief.discard(i)
        if not actief:
            break
        i = (i + 1) % n
    if hoogste_speler is None:
        return None
    return hoogste_speler, hoogste, deelgenomen


@dataclass
class _OpenRoem:
    """Interne boekhouding tijdens het spelen van een ronde: één
    roem-mogelijkheid (zie `RoemClaim`) die een speler nog kan melden, al
    gemeld heeft, of door stilzwijgen kwijt is."""
    claim: RoemClaim
    gemeld: bool = False
    vervallen: bool = False


@dataclass(frozen=True)
class RoemMelding:
    """Eén melding die tijdens het spel daadwerkelijk gemaakt is (en dus
    meetelt) -- voor een client om aan de speler te laten zien wát er precies
    aan roem is toegekend, in plaats van alleen het totaal (zie
    `RondeResultaat.roem_meldingen`)."""
    speler: int               # wie de melding deed (bij tafel-roem: wie de slag won)
    plaats: str               # "hand" of "tafel"
    omschrijving: str         # bijv. "vier azen", "stuk", "3-reeks, hoogste negen ♠"
    punten: int
    slag_nummer: Optional[int] = None  # alleen gezet bij plaats == "tafel" (1-based)


@dataclass
class RondeResultaat:
    contract: Bod
    bieder: int
    partner: Optional[int]
    geslaagd: bool
    centen: dict            # {speler: +bedrag of -bedrag}
    troef: Optional[Suit] = None        # None als het spel zonder troef gaat
    punten_team: Optional[int] = None   # alleen bij 'punten'
    roem_team: Optional[int] = None     # alleen bij 'punten': roem + stuk, al in punten_team
                                         # meegeteld -- apart hier zodat een client kan laten
                                         # zien hoevéél er aan roem is toegekend. Voor wát
                                         # er precies toegekend is (en door wie gemeld), zie
                                         # `roem_meldingen` hieronder -- roem telt pas mee als
                                         # hij tijdens het spel gemeld wordt (Butselaar, blz. 12),
                                         # anders vervalt hij.
    roem_meldingen: list = field(default_factory=list)  # [RoemMelding, ...], alleen de gemelde
    slagen: list = field(default_factory=list)  # (winnaar, [(speler,kaart),...])


def _kies_troef_en_partner(bod: Bod, declarant: int, hand: Sequence[Card],
                            handen: Sequence[Sequence[Card]], spelers, variant):
    """Geeft (troef, partner, gevraagde_kaart). `gevraagde_kaart` is alleen
    gezet bij punten/pandoer (geroepen aas) -- de kaart waarvan het spelen
    verraadt wie de maat is; zie de toelichting bij `Zicht.gevraagde_kaart`."""
    contract = CONTRACTEN[bod.soort]
    if bod.soort in GEROEPEN_AAS_SOORTEN:
        troef, gevraagd = spelers[declarant].kies_troef_en_aas(hand, variant)
        if gevraagd is None or gevraagd in hand:
            raise ValueError(
                "Ongeldig gevraagd aas/heer: moet een kaart zijn die de bieder "
                "niet zelf in handen heeft."
            )
        if gevraagd.suit == troef:
            raise ValueError(
                "Ongeldig gevraagd aas/heer: mag niet uit de troefkleur zijn "
                "(daar geldt de troefvolgorde, niet de gewone)."
            )
        partner = next(
            (i for i in range(len(handen)) if i != declarant and gevraagd in handen[i]),
            None,
        )
        if partner is None:
            raise ValueError(f"Niemand anders heeft de gevraagde kaart {gevraagd}.")
        return troef, partner, gevraagd
    if bod.soort in TROEFBOER_PARTNER_SOORTEN:
        troef = spelers[declarant].kies_troef_voor_kereltje(hand, variant)
        if Card(troef, Rank.BOER) in hand:
            raise ValueError(
                "Bij kereltje mag je geen troefkleur kiezen waarvan je zelf "
                "de boer hebt — dan kun je geen kereltje bieden."
            )
        houder = next(
            (i for i in range(len(handen)) if i != declarant and Card(troef, Rank.BOER) in handen[i]),
            None,
        )
        return troef, houder, None
    if contract.troef:
        return spelers[declarant].kies_troef(hand, variant), None, None
    # zwabber: partner blijkt pas na de eerste slag (in speel_ronde); hier nog
    # niemand. solo-zwabber: nooit een partner. (De enige twee spellen zonder
    # troef.)
    return None, None, None


def speel_ronde(spelers: Sequence[Speler], variant: Variant,
                rng: Optional[random.Random] = None, voorhand: int = 0):
    """Speel één volledige ronde: delen, bieden, spelen, afrekenen.

    Geeft een `RondeResultaat`, of None als iedereen paste (rondpassen; de
    aanroeper deelt dan opnieuw, met de volgende speler als deler).
    """
    rng = rng or random.Random()
    handen, kijkkaart = deel(rng)
    handen = [list(h) for h in handen]

    bod_resultaat = bied_ronde(spelers, handen, kijkkaart, variant, voorhand)
    if bod_resultaat is None:
        return None
    declarant, bod, deelgenomen = bod_resultaat

    if bod.soort not in GEIMPLEMENTEERD:
        # Kan nu niet meer voorkomen -- alle veertien spellen uit
        # `variant.CONTRACTEN` staan in GEIMPLEMENTEERD. Blijft als vangnet
        # voor een eventueel nieuw contract dat daar nog niet in staat.
        raise NotImplementedError(
            f"Het spel '{bod.soort}' heeft nog geen speelverloop in spel.py."
        )

    # Kijkkaart ruilen (Butselaar, regel 11) -- niet verplicht: `leg_af` mag
    # de kijkkaart zelf teruggeven, dan blijft de eigen hand ongewijzigd en
    # gaat de kijkkaart net als een echt afgelegde kaart uit het spel.
    hand_met_kijkkaart = handen[declarant] + [kijkkaart]
    afgelegd = spelers[declarant].leg_af(hand_met_kijkkaart, variant)
    if afgelegd not in hand_met_kijkkaart:
        raise ValueError("De weggelegde kaart zit niet in de hand.")
    handen[declarant] = [k for k in hand_met_kijkkaart if k != afgelegd]

    troef, partner, gevraagde_kaart = _kies_troef_en_partner(
        bod, declarant, handen[declarant], handen, spelers, variant
    )

    # Roem-basis: de hand vóór er gespeeld wordt (dus na het ruilen).
    hand_declarant_start = list(handen[declarant])
    hand_partner_start = list(handen[partner]) if partner is not None else None

    team = {declarant} | ({partner} if partner is not None else set())
    tegenstanders = set(range(len(handen))) - team

    # Roem moet tijdens het spel gemeld worden, anders vervalt hij
    # (Butselaar, blz. 12 -- zie `roem.RoemClaim`). Dit speelt alleen een rol
    # bij puntenspel (net als voorheen: roem telt alleen mee voor dat
    # contract, zie de scoring hieronder), dus alleen dan houden we het bij.
    roem_speelt_mee = bod.soort == "punten"
    open_reeksen: dict = {}  # speler -> [_OpenRoem, ...] (reeksen/vier-gelijke, kunnen ontkend worden)
    open_stuk: dict = {}     # speler -> _OpenRoem (stuk, kan NIET ontkend worden)
    tafel_roem_gemeld: list = []  # (winnaar, slag_nummer, RoemClaim) die op tafel gemeld zijn

    if roem_speelt_mee:
        for speler_idx, hand_start in ((declarant, hand_declarant_start),) + (
            ((partner, hand_partner_start),) if partner is not None else ()
        ):
            open_reeksen[speler_idx] = [
                _OpenRoem(c) for c in hand_roem_claims(hand_start, variant.kaarten_dubbel_in_roem)
            ]
            s = stuk_claim(hand_start, troef)
            if s is not None:
                open_stuk[speler_idx] = _OpenRoem(s)

    def _openstaand_voor(speler_idx):
        lijst = list(open_reeksen.get(speler_idx, []))
        if speler_idx in open_stuk:
            lijst.append(open_stuk[speler_idx])
        return [o for o in lijst if not o.gemeld and not o.vervallen]

    def _vraag_meld_roem(speler_idx):
        openstaand = _openstaand_voor(speler_idx)
        if not openstaand:
            return
        gekozen = set(spelers[speler_idx].meld_roem([o.claim for o in openstaand], variant))
        for o in openstaand:
            if o.claim in gekozen:
                o.gemeld = True

    def _verwerk_gespeelde_kaart(speler_idx, kaart, hand_na_zet):
        """Vlak nadat `kaart` gespeeld is: is dit de laatste nog ongespeelde
        kaart van een nog niet gemelde combinatie? Dan is die nu vervallen."""
        for o in _openstaand_voor(speler_idx):
            if kaart not in o.claim.kaarten:
                continue
            resterend = o.claim.kaarten - {kaart}
            if not (resterend & set(hand_na_zet)):
                o.vervallen = True

    # Slagen spelen, op een kopie van de handen (die tijdens het spel slinkt).
    speelhanden = [list(h) for h in handen]
    contract = CONTRACTEN[bod.soort]
    leider = declarant
    slagen: list = []
    for slag_nummer in range(1, 9):
        slag: list = []
        for j in range(len(speelhanden)):
            speler_idx = (leider + j) % len(speelhanden)
            if roem_speelt_mee and speler_idx in team:
                _vraag_meld_roem(speler_idx)
            zicht = Zicht(
                ik=speler_idx, hand=list(speelhanden[speler_idx]), troef=troef,
                contract=bod, bieder=declarant, partner=partner,
                huidige_slag=list(slag), gespeelde_slagen=list(slagen),
                gevraagde_kaart=gevraagde_kaart,
            )
            kaart = spelers[speler_idx].speel_kaart(zicht, variant)
            toegestaan = legale_kaarten(speelhanden[speler_idx], slag, troef, variant)
            if kaart not in toegestaan:
                raise ValueError(f"Speler {speler_idx} speelde een ongeldige kaart: {kaart}")
            speelhanden[speler_idx].remove(kaart)
            if roem_speelt_mee and speler_idx in team:
                _verwerk_gespeelde_kaart(speler_idx, kaart, speelhanden[speler_idx])
            slag.append((speler_idx, kaart))
        winnaar = slag_winnaar(slag, troef)
        slagen.append((winnaar, slag))
        leider = winnaar
        # Roem op tafel (AANNAME, zie roem.tafel_roem_claims): alleen van
        # belang als het team de slag binnenhaalt, en moet net als
        # hand-roem gemeld worden door wie de slag wint.
        if roem_speelt_mee and winnaar in team:
            tafel_kandidaten = tafel_roem_claims(slag, troef)
            if tafel_kandidaten:
                gekozen_claims = [
                    c for c in tafel_kandidaten
                    if c in set(spelers[winnaar].meld_tafelroem(tafel_kandidaten, variant))
                ]
                tafel_roem_gemeld.extend((winnaar, slag_nummer, c) for c in gekozen_claims)
                if gekozen_claims:
                    # Aan iedereen laten weten (ook wie er zelf niets mee te
                    # maken heeft) -- puur informatief, voor bijv. een GUI
                    # die dit wil tonen ook als een computerspeler meldde.
                    for s in spelers:
                        s.toon_tafelroem(winnaar, gekozen_claims, slag_nummer)

    laatste_slag_winnaar = slagen[-1][0]

    if bod.soort in EERSTE_SLAG_PARTNER_SOORTEN:
        # zwabber: de partner is wie de eerste slag wint, blijkt dus nu pas.
        eerste_winnaar = slagen[0][0]
        partner = eerste_winnaar if eerste_winnaar != declarant else None
        team = {declarant} | ({partner} if partner is not None else set())

    roem_team_resultaat = None
    roem_meldingen_resultaat: list = []
    if bod.soort == "punten":
        team_kaartpunten = sum(
            kaart_punten(kaart, troef)
            for winnaar, slag in slagen if winnaar in team
            for _, kaart in slag
        )
        if laatste_slag_winnaar in team:
            team_kaartpunten += LAATSTE_SLAG_PUNTEN

        def gemelde_reeks_claims(speler_idx, hand_start):
            """Gemelde reeksen/vier-gelijke van deze speler, of [] als een
            tegenstander ze kan ontkennen (Butselaar) -- ontkennen is alles-
            of-niets per hand, dus bij ontkenning vervalt de hele set."""
            gemeld = [o.claim for o in open_reeksen.get(speler_idx, []) if o.gemeld]
            if not gemeld:
                return []
            hoogste = hoogste_enkele_roem(hand_start)
            if variant.roem_ontkennen and any(
                kan_ontkennen(hoogste, handen[t]) for t in tegenstanders if t in deelgenomen
            ):
                return []
            return gemeld

        roem_claims_declarant = gemelde_reeks_claims(declarant, hand_declarant_start)
        roem_claims_partner = (
            gemelde_reeks_claims(partner, hand_partner_start) if partner is not None else []
        )
        roem_team = sum(c.punten for c in roem_claims_declarant + roem_claims_partner)
        roem_meldingen = [
            RoemMelding(speler=declarant, plaats="hand", omschrijving=c.omschrijving, punten=c.punten)
            for c in roem_claims_declarant
        ] + [
            RoemMelding(speler=partner, plaats="hand", omschrijving=c.omschrijving, punten=c.punten)
            for c in roem_claims_partner
        ]
        # Stuk kan niet ontkend worden (zie STUK_PUNTEN), maar moet wel
        # gemeld zijn.
        if declarant in open_stuk and open_stuk[declarant].gemeld:
            roem_team += open_stuk[declarant].claim.punten
            roem_meldingen.append(RoemMelding(
                speler=declarant, plaats="hand",
                omschrijving=open_stuk[declarant].claim.omschrijving,
                punten=open_stuk[declarant].claim.punten,
            ))
        if partner is not None and partner in open_stuk and open_stuk[partner].gemeld:
            roem_team += open_stuk[partner].claim.punten
            roem_meldingen.append(RoemMelding(
                speler=partner, plaats="hand",
                omschrijving=open_stuk[partner].claim.omschrijving,
                punten=open_stuk[partner].claim.punten,
            ))
        # Roem op tafel (AANNAME): alles wat tijdens het spel gemeld is.
        roem_team += sum(c.punten for _, _, c in tafel_roem_gemeld)
        roem_meldingen += [
            RoemMelding(
                speler=winnaar, plaats="tafel", omschrijving=c.omschrijving,
                punten=c.punten, slag_nummer=slag_nr,
            )
            for winnaar, slag_nr, c in tafel_roem_gemeld
        ]

        punten_team = team_kaartpunten + roem_team
        roem_team_resultaat = roem_team
        roem_meldingen_resultaat = roem_meldingen
        geslaagd = punten_team >= bod.doel
    elif bod.soort in ALLE_SLAGEN_MET_PARTNER_SOORTEN:  # pandoer, kereltje, zwabber
        geslaagd = all(winnaar in team for winnaar, _ in slagen)
        punten_team = None
    elif bod.soort in PICCOLO_SOORTEN:
        # precies één slag, en die moet gewonnen zijn met de troefboer.
        eigen_slagen = [slag for winnaar, slag in slagen if winnaar == declarant]
        if len(eigen_slagen) == 1:
            eigen_kaart = next(k for spl, k in eigen_slagen[0] if spl == declarant)
            geslaagd = eigen_kaart == Card(troef, Rank.BOER)
        else:
            geslaagd = False
        punten_team = None
    elif bod.soort in ALLE_SLAGEN_ALLEEN_SOORTEN:  # privé, solo-zwabber
        geslaagd = all(winnaar == declarant for winnaar, _ in slagen)
        punten_team = None
    elif bod.soort in NUL_SLAGEN_SOORTEN:  # misère, misère ouvert, praatje-familie
        geslaagd = not any(winnaar == declarant for winnaar, _ in slagen)
        punten_team = None
    else:
        raise AssertionError(f"Onbekend hoe '{bod.soort}' afgerekend moet worden.")

    bedrag = variant.uitbetaling(bod)
    teken = 1 if geslaagd else -1
    centen = {declarant: teken * bedrag}
    if partner is not None:
        centen[partner] = teken * bedrag

    return RondeResultaat(
        contract=bod, bieder=declarant, partner=partner, geslaagd=geslaagd,
        centen=centen, troef=troef, punten_team=punten_team,
        roem_team=roem_team_resultaat, roem_meldingen=roem_meldingen_resultaat,
        slagen=slagen,
    )
