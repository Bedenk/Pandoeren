"""Regelvarianten van pandoeren.

Pandoeren verschilt per streek en per familie. Alles wat kan verschillen staat
daarom in een `Variant`, en bij elke instelling staat hoe zeker we zijn dat het
in de betreffende variant zo ging (`Zekerheid`). Zo blijft zichtbaar wat echt
bevestigd is en wat nog uit bronnen komt.

De variant `MIDDEN_NEDERLAND` ("Midden-Nederland", want de Bollenstreek is er maar een klein onderdeel van) volgt sinds de tweede versie het boekje "Pandoeren"
van A.C. Butselaar (1958): de biedvolgorde en de bedragen komen letterlijk uit
zijn eigen lijst (hoofdstuk 1, "De volgorde der spelen"), aangevuld met wat
bevestigd is door iemand die het thuis speelde. Waar het boekje en die
herinnering tegenstrijdig waren (het laagste bod, of troeven verplicht is, of
kaarten dubbel mogen in roem), is bewust gekozen om het boekje te volgen.

Piccolo (bij misère), piccolo ouvert (bij misère ouvert) en piccolo-praatje
(bij praatje) zijn in het boekje geen eigen spelen met een vaste plek in de
lijst, maar toevoegingen: eerst verplicht een slag halen met troefboer, en
daarna verder als het onderliggende spel. Hun plek in de biedvolgorde en hun
bedrag staan er niet expliciet in en zijn dus een gok (net onder het
onderliggende spel), tot we een latere pagina van het boekje hebben die dat
preciseert.

Troef: op zwabber en solo-zwabber na hebben alle spellen een troefkleur, ook
misère ouvert, stil praatje en praatje zelf (bevestigd in het boekje: blz. 27
voor praatje, blz. 29 voor stil praatje, en het eerste voorbeeld bij misère
ouvert kiest ruiten). De piccolo-varianten van die open/praatje-spellen (bij
misère ouvert, stil praatje en praatje) hebben daardoor ook troef: zonder
troefkleur is er immers geen troefboer om die ene verplichte slag mee te
halen.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import NamedTuple, Optional


class Zekerheid(Enum):
    BEVESTIGD = "bevestigd door een speler"
    WAARSCHIJNLIJK = "waarschijnlijk, nog even navragen"
    BRON = "alleen uit bronnen, niet bevestigd"
    ONBEKEND = "onbekend"


class Bod(NamedTuple):
    soort: str                 # 'punten', 'piccolo', 'misere', ...
    doel: Optional[int] = None  # alleen bij 'punten': het aantal punten


@dataclass(frozen=True)
class Contract:
    soort: str
    naam: str
    uitbetaling: int            # centen per speler; bij 'punten' zie Variant.uitbetaling
    troef: bool
    partner: str                # 'geroepen_aas' | 'troefboer' | 'eerste_slagwinnaar' | 'geen'
    doel: str
    bevestigd: bool = False     # bestaat dit spel bij de bekende variant?


# Van laag naar hoog, letterlijk Butselaar's eigen lijst (blz. 8-9), met de
# piccolo-varianten en het stil praatje op de plek die hij er zelf later voor
# voorstelt ("boven misère ouvert, beneden pandoer" voor het stil praatje;
# "lager dan het onderliggende spel" voor de piccolo's).
_SLOTS = [
    ("punten", 130, 150),
    ("piccolo", None, None),           # piccolo-misère: gok, "lager dan misère"
    ("misere", None, None),
    ("punten", 160, 160),
    ("kereltje", None, None),
    ("zwabber", None, None),
    ("punten", 170, 190),
    ("solo_zwabber", None, None),
    ("punten", 200, None),
    ("piccolo_ouvert", None, None),    # gok: "lager dan misère ouvert"
    ("misere_ouvert", None, None),
    ("stil_praatje", None, None),      # Butselaar: boven misère ouvert, beneden pandoer
    ("pandoer", None, None),
    ("stil_piccolo_praatje", None, None),  # gok: "lager dan praatje"
    ("piccolo_praatje", None, None),       # gok: "lager dan praatje"
    ("praatje", None, None),
    ("pandoer_prive", None, None),
]

CONTRACTEN = {c.soort: c for c in [
    Contract("punten", "puntenspel", 0, True, "geroepen_aas", "minstens het geboden aantal punten", True),
    Contract("piccolo", "piccolo (bij misère)", 3, True, "geen", "eerst een slag met troefboer, dan geen slag meer"),
    Contract("misere", "misère", 3, True, "geen", "geen enkele slag halen", True),
    Contract("kereltje", "kereltje", 2, True, "troefboer", "alle slagen halen", True),
    Contract("zwabber", "zwabber", 2, False, "eerste_slagwinnaar", "alle slagen halen", True),
    Contract("solo_zwabber", "solo-zwabber", 5, False, "geen", "alle slagen alleen halen", True),
    Contract("piccolo_ouvert", "piccolo ouvert (bij misère ouvert)", 5, True, "geen", "eerst een slag met troefboer, dan geen slag meer, kaarten open na de eerste slag"),
    Contract("misere_ouvert", "misère ouvert", 6, True, "geen", "geen slag, kaarten open na de eerste slag", True),
    Contract("stil_praatje", "stil praatje", 8, True, "geen", "geen slag, alle kaarten open, tegenstanders zwijgen", True),
    Contract("pandoer", "pandoer", 5, True, "geroepen_aas", "alle slagen halen", True),
    Contract("stil_piccolo_praatje", "stil piccolo-praatje (bij stil praatje)", 6, True, "geen", "eerst een slag met troefboer, dan geen slag meer, alle kaarten open, tegenstanders zwijgen"),
    Contract("piccolo_praatje", "piccolo-praatje (bij praatje)", 7, True, "geen", "eerst een slag met troefboer, dan geen slag meer, alle kaarten open, tegenstanders overleggen"),
    Contract("praatje", "praatje", 9, True, "geen", "geen slag, alle kaarten open, tegenstanders overleggen", True),
    Contract("pandoer_prive", "privé", 10, True, "geen", "alle slagen alleen halen", True),
]}


@dataclass(frozen=True, eq=False)
class Variant:
    naam: str
    lappen: int = 10               # centen die iedereen aan het begin in de pot legt
    laagste_bod: int = 130         # laagste puntenbod (Butselaar; niet de 100 die eerst herinnerd werd)
    bod_stap: int = 10
    husselen: bool = False         # opnieuw verdelen als iedereen past (een van Butselaar's twee varianten)
    roem_melden: str = "na_eerste_slag"   # of 'tijdens_bieden'
    roem_ontkennen: bool = True
    kaarten_dubbel_in_roem: bool = True   # Butselaar: "alle roem is geldig", ook als een kaart 3x meedoet
    # Regels voor het bijspelen (bron: Butselaar 1958)
    troeven_bij_bekennen: bool = True     # mag je troeven terwijl je kunt bekennen?
    overtroeven_verplicht: bool = False   # Butselaar: nooit verplicht hoger te troeven dan wat er ligt
    jas_nooit_verplicht: bool = True      # troefboer hoeft nooit gespeeld te worden (behalve laatste slag)
    zekerheid: dict = field(default_factory=dict)

    # -- biedvolgorde -------------------------------------------------------
    def bod_rang(self, bod: Bod) -> tuple:
        """Sorteersleutel van een bod: hoger = sterker."""
        for i, (soort, lo, hi) in enumerate(_SLOTS):
            if soort != bod.soort:
                continue
            if soort != "punten":
                return (i, 0)
            doel = bod.doel
            if doel is None or (doel - self.laagste_bod) % self.bod_stap:
                continue
            if doel >= max(lo, self.laagste_bod) and (hi is None or doel <= hi):
                return (i, doel)
        raise ValueError(f"Onbekend of ongeldig bod: {bod}")

    def is_hoger(self, bod: Bod, vorig: Optional[Bod]) -> bool:
        return vorig is None or self.bod_rang(bod) > self.bod_rang(vorig)

    # -- uitbetaling --------------------------------------------------------
    def uitbetaling(self, bod: Bod) -> int:
        """Centen die elke deelnemende speler wint of verliest."""
        if bod.soort == "punten":
            doel = bod.doel
            if doel <= 150:
                return 1
            if doel == 160:
                return 2
            if doel <= 190:
                return 3
            return 4
        return CONTRACTEN[bod.soort].uitbetaling

    @property
    def uitbetalingen(self) -> dict:
        """Centen per spel (puntenspellen: zie `uitbetaling`)."""
        return {soort: c.uitbetaling for soort, c in CONTRACTEN.items() if soort != "punten"}

    def mogelijke_boden(self, soorten, huidig_hoogste: Optional[Bod] = None,
                        max_doel: int = 300) -> list:
        """Alle boden (uit `soorten`, bijv. GEIMPLEMENTEERD) die nu een
        geldig, hoger bod zijn dan `huidig_hoogste` -- op volgorde van sterkte.

        Bedoeld om een biedkeuze-lijst mee te vullen die zich uit zichzelf al
        beperkt tot wat werkelijk geboden mag worden, in plaats van alles te
        tonen en pas na een klik een foutmelding te geven (zie `is_hoger`).
        Bij 'punten' komt elk geldig doel (stappen van `bod_stap`, tot en met
        `max_doel`) als eigen bod in de lijst terecht, net als elk ander spel.
        """
        kandidaten = []
        for soort in soorten:
            if soort == "punten":
                doel = self.laagste_bod
                while doel <= max_doel:
                    bod = Bod("punten", doel)
                    try:
                        self.bod_rang(bod)
                    except ValueError:
                        doel += self.bod_stap
                        continue
                    if self.is_hoger(bod, huidig_hoogste):
                        kandidaten.append(bod)
                    doel += self.bod_stap
            else:
                bod = Bod(soort)
                try:
                    self.bod_rang(bod)
                except ValueError:
                    continue
                if self.is_hoger(bod, huidig_hoogste):
                    kandidaten.append(bod)
        return sorted(kandidaten, key=self.bod_rang)

    def open_vragen(self) -> list:
        """Instellingen die nog niet door een speler bevestigd zijn."""
        return [
            (naam, getattr(self, naam), z)
            for naam, z in self.zekerheid.items()
            if z is not Zekerheid.BEVESTIGD
        ]


MIDDEN_NEDERLAND = Variant(
    naam="Midden-Nederland (concept)",
    zekerheid={
        "lappen": Zekerheid.BEVESTIGD,               # 10 cent
        # Laagste bod: eerst 100 herinnerd, daarna bewust gekozen voor
        # Butselaar's 130, na het lezen van hoofdstuk 1.
        "laagste_bod": Zekerheid.BEVESTIGD,
        "bod_stap": Zekerheid.BEVESTIGD,             # Butselaar
        # Kern van de tabel (misère, kereltje, zwabber, solo-zwabber, misère
        # ouvert, pandoer, praatje, privé, en de punten-drempels) komt
        # letterlijk uit Butselaar's eigen lijst. De piccolo-varianten en het
        # stil praatje zijn wél zijn eigen spelen, maar hun exacte plek en
        # bedrag zijn een gok (zie de module-tekst hierboven).
        "uitbetalingen": Zekerheid.BEVESTIGD,
        "husselen": Zekerheid.BEVESTIGD,             # niet bij ons; Butselaar's alternatief: gewoon opnieuw delen
        "roem_melden": Zekerheid.WAARSCHIJNLIJK,     # na de eerste slag
        "roem_ontkennen": Zekerheid.WAARSCHIJNLIJK,  # 'overroemen' bij puntenspelen
        # Butselaar: "alle roem is geldig", een kaart mag in meerdere
        # combinaties meetellen. Dit gaat tegen de eerdere herinnering in,
        # maar is bewust gekozen boven die herinnering.
        "kaarten_dubbel_in_roem": Zekerheid.BEVESTIGD,
        "troeven_bij_bekennen": Zekerheid.BEVESTIGD,     # Butselaar: mag, is niet verplicht
        # Butselaar: overtroeven is nooit verplicht, ook niet als troef is
        # gevraagd. Dit is milder dan de eerdere (Wikipedia/Pagat) standaard.
        "overtroeven_verplicht": Zekerheid.BEVESTIGD,
        "jas_nooit_verplicht": Zekerheid.BEVESTIGD,      # Butselaar, regel 9
    },
)
