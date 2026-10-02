#!/usr/bin/env python3
"""Grafische (PySide6) client: jij tegen drie eenvoudige computerspelers.

Zelfde opzet als speeltest.py, maar met een venster in plaats van de
terminal. De spelmodule (pandoeren/spel.py) is hiervoor NIET aangepast: dit
bestand is gewoon een nieuwe `Speler`-implementatie (MenselijkeSpelerQt),
net zoals speeltest.py's MenselijkeSpeler er al een was.

Waarom een aparte thread: `speel_ronde` roept een speler synchroon aan en
verwacht meteen een antwoord terug (in de terminal was dat `input()`, dat
blokkeert de hele terminal en dat is prima). Een Qt-venster mag zijn
hoofdthread nooit zo blokkeren, anders bevriest het scherm en werken klikken
niet meer. Daarom draait een hele ronde in een achtergrondthread
(RondeWorker). Zodra de spelmodule aan de mens iets vraagt, stuurt
MenselijkeSpelerQt een Qt-signaal naar het venster (dat mag altijd, ook
vanuit een andere thread) met wat er nodig is, en wacht daarna -- in de
achtergrondthread, dus zonder het venster te blokkeren -- op een antwoord
via een `queue.Queue`. Een klik in het venster (in de hoofdthread) stopt het
antwoord in die queue, en de achtergrondthread gaat verder.

Draai met: python3 client_qt.py
"""
from __future__ import annotations

import queue
import random
import sys
import threading
import time
from pathlib import Path

from PySide6.QtCore import Qt, QObject, Signal
from PySide6.QtGui import QColor, QPen, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QComboBox, QSpinBox, QListWidget, QListWidgetItem, QGroupBox,
    QMessageBox, QAbstractButton, QSizePolicy,
)

from pandoeren.cards import Card, Rank, Suit, sorteer
from pandoeren.spel import EenvoudigeSpeler, GEIMPLEMENTEERD, maat_indien_onthuld, speel_ronde
from pandoeren.spelregels import legale_kaarten
from pandoeren.variant import CONTRACTEN, MIDDEN_NEDERLAND, Bod

NAAM = {0: "jij", 1: "Piet", 2: "Klaas", 3: "Jan"}  # tijdelijke namen voor de bots
KLEUREN = list(Suit)

# Windrichting per speler aan tafel. Jij (0) zit op Zuid; de speelvolgorde in
# spel.py gaat (leider + j) % 4, dus met de klok mee vanaf Zuid: Zuid -> West
# -> Noord -> Oost, net als aan een echte tafel (vergelijk bridge).
WINDRICHTING = {0: "Zuid", 1: "West", 2: "Noord", 3: "Oost"}

# Eigen ingescande kaarten (optioneel): assets/kaarten/<kleur>_<rang>.png,
# bijv. "schoppen_aas.png". Suit.naam en Rank.naam leveren precies die
# namen op. Ontbreekt een scan (of de hele map), dan tekent KaartWidget de
# kaart gewoon zelf -- er is dus niets verplicht aan te leveren.
ASSETS_KAARTEN = Path(__file__).resolve().parent / "assets" / "kaarten"


def _kleur_label(s: Suit) -> str:
    return f"{s.value} {s.naam}"


def _kaart_pixmap(kaart: Card) -> "QPixmap | None":
    pad = ASSETS_KAARTEN / f"{kaart.suit.naam}_{kaart.rank.naam}.png"
    if not pad.exists():
        return None
    pixmap = QPixmap(str(pad))
    return pixmap if not pixmap.isNull() else None


class KaartWidget(QAbstractButton):
    """Tekent een kaart zoals een echte speelkaart, in plaats van een knop
    met tekst erop. Gebruikt bij voorkeur een eigen scan uit assets/kaarten/
    (zie _kaart_pixmap); ontbreekt die -- bijvoorbeeld omdat er nog niet
    gescand is -- dan tekent hij de kaart zelf (QPainter, generiek ontwerp,
    geen bestaand merk): rang en kleursymbool in twee hoeken (de een op zijn
    kop, zoals bij echte kaarten), en een groot symbool in het midden. Rood
    voor harten/ruiten, zwart voor schoppen/klaveren. Blijft gewoon een
    QAbstractButton, dus `clicked`, `setEnabled()` en het aanklikken werken
    zoals bij de oude QPushButton-knoppen.

    `gedimd` is los van `setEnabled()`: een niet-klikbare kaart (bijv. je
    hand tijdens het bieden -- er valt daar toch niets aan te klikken) moet
    gewoon goed leesbaar blijven. Dimmen is voor iets anders: een kaart die
    je nu wel ziet maar niet mag spelen, tijdens het uitspelen van een
    slag."""

    BREEDTE, HOOGTE = 60, 88
    ROOD = {Suit.HARTEN, Suit.RUITEN}

    def __init__(self, kaart: Card, gemarkeerd: bool = False, gedimd: bool = False,
                 breedte: int | None = None, hoogte: int | None = None, parent=None):
        super().__init__(parent)
        self.kaart = kaart
        self.gemarkeerd = gemarkeerd  # gouden rand, bijv. voor de kijkkaart bij het afleggen
        self.gedimd = gedimd          # mag nu niet gespeeld worden (los van klikbaar/setEnabled)
        # `breedte`/`hoogte`: optioneel groter dan de standaardmaat -- gebruikt
        # voor je eigen hand (gewaaierd, zie _hand_tonen), die door het vele
        # scherm dat er tegenwoordig is best wat prominenter mag zijn dan de
        # kaarten op tafel/bij de tegenstanders.
        self.setFixedSize(breedte or self.BREEDTE, hoogte or self.HOOGTE)
        self.setCursor(Qt.PointingHandCursor)
        self._pixmap = _kaart_pixmap(kaart)  # eigen scan, indien aanwezig

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)

        randkleur = QColor("#b8860b") if self.gemarkeerd else QColor("#2b2b2b")
        randdikte = 3 if self.gemarkeerd else 1

        if self._pixmap is not None:
            # Eigen scan: kader tekenen, dan de scan er geschaald in passen.
            painter.setBrush(QColor("#fdfdfd"))
            painter.setPen(QPen(randkleur, randdikte))
            painter.drawRoundedRect(rect, 7, 7)
            binnen = rect.adjusted(3, 3, -3, -3)
            if self.gedimd:
                painter.setOpacity(0.35)
            geschaald = self._pixmap.scaled(
                binnen.width(), binnen.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            x = binnen.x() + (binnen.width() - geschaald.width()) // 2
            y = binnen.y() + (binnen.height() - geschaald.height()) // 2
            painter.drawPixmap(x, y, geschaald)
            painter.setOpacity(1.0)
            return

        # Geen scan gevonden: teken de kaart zelf (zie module-docstring).
        achtergrond = QColor("#dcdcdc") if self.gedimd else QColor("#fdfdfd")
        painter.setBrush(achtergrond)
        painter.setPen(QPen(randkleur, randdikte))
        painter.drawRoundedRect(rect, 7, 7)

        symboolkleur = QColor("#b3261e") if self.kaart.suit in self.ROOD else QColor("#1a1a1a")
        if self.gedimd:
            symboolkleur = symboolkleur.lighter(170)
        painter.setPen(symboolkleur)

        # Lettergrootte schaalt mee met de werkelijke hoogte, want via
        # breedte/hoogte (zie __init__) kan deze kaart groter zijn dan de
        # standaardmaat (bijv. de gewaaierde hand) -- zonder deze schaling
        # zou de tekst daar onnodig klein blijven staan.
        schaal = self.height() / self.HOOGTE
        hoek_font = painter.font()
        hoek_font.setPointSizeF(11 * schaal)
        hoek_font.setBold(True)
        painter.setFont(hoek_font)
        hoektekst = f"{self.kaart.rank.label}\n{self.kaart.suit.value}"
        painter.drawText(rect.adjusted(5, 3, -5, -5), Qt.AlignLeft | Qt.AlignTop, hoektekst)

        painter.save()
        painter.translate(rect.center())
        painter.rotate(180)
        gespiegeld = rect.translated(-rect.center().x(), -rect.center().y())
        painter.drawText(gespiegeld.adjusted(5, 3, -5, -5), Qt.AlignLeft | Qt.AlignTop, hoektekst)
        painter.restore()

        midden_font = painter.font()
        midden_font.setPointSizeF(24 * schaal)
        midden_font.setBold(False)
        painter.setFont(midden_font)
        painter.drawText(rect, Qt.AlignCenter, self.kaart.suit.value)


class AvatarWidget(QWidget):
    """Een rustig, 'volwassen' avatar-rondje per speler -- geen cartoon- of
    emoji-gezicht (pandoeren is daar volgens de speler te serieus een spel
    voor), gewoon een gekleurde cirkel met de eerste letter van de naam
    erin, elke speler zijn eigen gedekte kleur. Puur decoratief/herkenning
    aan tafel, draagt geen spelinformatie."""

    MAAT = 44
    KLEUR = {
        0: QColor("#2c3e63"),  # jij -- gedekt marineblauw
        1: QColor("#6b2d3c"),  # bordeaux
        2: QColor("#2f5233"),  # bosgroen
        3: QColor("#4a4030"),  # warmbruin
    }

    def __init__(self, speler: int, parent=None):
        super().__init__(parent)
        self.speler = speler
        self.setFixedSize(self.MAAT, self.MAAT)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)

        kleur = self.KLEUR.get(self.speler, QColor("#444444"))
        painter.setBrush(kleur)
        painter.setPen(QPen(kleur.darker(130), 2))
        painter.drawEllipse(rect)

        letter_font = painter.font()
        letter_font.setPointSizeF(self.MAAT * 0.4)
        letter_font.setBold(True)
        painter.setFont(letter_font)
        painter.setPen(QColor("#f2f2f2"))
        painter.drawText(rect, Qt.AlignCenter, NAAM[self.speler][0].upper())


class Brug(QObject):
    """Leeft in de hoofdthread. De enige manier waarop de achtergrondthread
    met het venster praat: signalen. Qt zet een signaal dat vanuit een
    andere thread verstuurd wordt automatisch in de wachtrij van de
    hoofdthread (QueuedConnection) -- dat is precies wat we hier nodig
    hebben, en waarom dit een QObject moet zijn en geen gewoon object."""

    vraag = Signal(str, dict, object)     # (soort, payload, antwoorden-queue)
    resultaat = Signal(object)            # RondeResultaat, of None bij rondpassen
    fout = Signal(str)
    tafelroem = Signal(int, list, int)    # (winnaar, gemelde RoemClaims, slag_nummer) --
                                           # puur informatief, geen antwoord nodig (zie
                                           # MenselijkeSpelerQt.toon_tafelroem)


class MenselijkeSpelerQt:
    """Speler-implementatie die elk verzoek doorzet naar het venster (via
    Brug) en blokkeert tot daar een antwoord voor is. Dat blokkeren gebeurt
    in de achtergrondthread, dus het venster blijft ondertussen reageren."""

    def __init__(self, brug: Brug):
        self.brug = brug

    def _vraag(self, soort, **payload):
        antwoorden: queue.Queue = queue.Queue()
        self.brug.vraag.emit(soort, payload, antwoorden)
        return antwoorden.get()

    def bieden(self, hand, huidig_hoogste, kijkkaart, variant):
        return self._vraag(
            "bieden", hand=list(hand), huidig_hoogste=huidig_hoogste,
            kijkkaart=kijkkaart, variant=variant,
        )

    def kies_troef_en_aas(self, hand, variant):
        return self._vraag("kies_troef_en_aas", hand=list(hand), variant=variant)

    def kies_troef(self, hand, variant):
        return self._vraag("kies_troef", hand=list(hand), variant=variant)

    def kies_troef_voor_kereltje(self, hand, variant):
        return self._vraag("kies_troef_voor_kereltje", hand=list(hand), variant=variant)

    def leg_af(self, hand_met_kijkkaart, variant):
        return self._vraag("leg_af", hand_met_kijkkaart=list(hand_met_kijkkaart), variant=variant)

    def speel_kaart(self, zicht, variant):
        return self._vraag("speel_kaart", zicht=zicht, variant=variant)

    def meld_roem(self, aangeboden, variant):
        return self._vraag("meld_roem", aangeboden=list(aangeboden), variant=variant)

    def meld_tafelroem(self, aangeboden, variant):
        return self._vraag("meld_tafelroem", aangeboden=list(aangeboden), variant=variant)

    def toon_tafelroem(self, winnaar, gemeld, slag_nummer):
        # Geen antwoord nodig (dus geen queue zoals _vraag): gewoon melden
        # en daar 3 seconden mee laten staan, ook als het een computerspeler
        # was die meldde -- dat gebeurt hier in de achtergrondthread, dus
        # het venster blijft ondertussen gewoon reageren/tekenen.
        self.brug.tafelroem.emit(winnaar, list(gemeld), slag_nummer)
        time.sleep(3)


class RondeWorker(threading.Thread):
    """Speelt precies één ronde, in een eigen thread (daemon, dus de app kan
    altijd gewoon afsluiten)."""

    def __init__(self, brug: Brug, spelers, variant, voorhand: int):
        super().__init__(daemon=True)
        self.brug = brug
        self.spelers = spelers
        self.variant = variant
        self.voorhand = voorhand

    def run(self):
        try:
            resultaat = speel_ronde(self.spelers, self.variant, random.Random(), self.voorhand)
        except Exception as e:  # noqa: BLE001 -- naar het venster i.p.v. een crash
            self.brug.fout.emit(f"{type(e).__name__}: {e}")
            return
        self.brug.resultaat.emit(resultaat)


class Hoofdvenster(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pandoeren -- Midden-Nederland")
        self.resize(960, 960)

        self.brug = Brug()
        self.brug.vraag.connect(self.op_vraag, Qt.QueuedConnection)
        self.brug.resultaat.connect(self.op_resultaat, Qt.QueuedConnection)
        self.brug.fout.connect(self.op_fout, Qt.QueuedConnection)
        self.brug.tafelroem.connect(self.op_tafelroem, Qt.QueuedConnection)

        self.totalen = {i: 0 for i in range(4)}
        self.pot = 4 * MIDDEN_NEDERLAND.lappen  # eenmalig ingelegd bij het begin van het spel
        self.ronde = 0
        self._antwoorden: queue.Queue | None = None
        self._huidig_hoogste: Bod | None = None

        # -- lay-out --------------------------------------------------------
        layout = QVBoxLayout(self)

        boven_rij = QHBoxLayout()
        self.stand_label = QLabel()
        boven_rij.addWidget(self.stand_label)
        boven_rij.addStretch()
        self.maat_label = QLabel()
        boven_rij.addWidget(self.maat_label)
        boven_rij.addStretch()
        self.pot_label = QLabel()
        boven_rij.addWidget(self.pot_label)
        layout.addLayout(boven_rij)

        # instructie_label wordt hierna ingebouwd in de tafel zelf (als
        # donkere banner, zie _bouw_tafel) -- daarom hier al aanmaken maar
        # nog niet aan `layout` toevoegen.
        self.instructie_label = QLabel("Klaar om te beginnen.")
        self.instructie_label.setWordWrap(True)

        self.slag_label = QLabel()
        self.slag_label.setWordWrap(True)
        layout.addWidget(self.slag_label)

        layout.addWidget(self._bouw_tafel())

        self.hand_box = QGroupBox("Jouw kaarten")
        self.hand_layout = QHBoxLayout(self.hand_box)
        layout.addWidget(self.hand_box)

        layout.addWidget(QLabel("Gespeelde slagen deze ronde:"))
        self.slagen_log = QListWidget()
        self.slagen_log.setMaximumHeight(150)  # genoeg voor alle 8 slagen in één oogopslag
        layout.addWidget(self.slagen_log)
        self._gelogde_slagen = 0  # hoeveel slagen van deze ronde al in slagen_log staan

        bied_rij = QHBoxLayout()
        self.bied_keuze = QComboBox()
        self.bied_doel = QSpinBox()
        self.bied_doel.setRange(MIDDEN_NEDERLAND.laagste_bod, 300)
        self.bied_doel.setSingleStep(MIDDEN_NEDERLAND.bod_stap)
        self.bied_knop = QPushButton("Bied")
        self.pas_knop = QPushButton("Pas")
        self.bied_keuze.currentTextChanged.connect(self._bijwerken_bied_doel_zichtbaar)
        self.bied_knop.clicked.connect(self._bieden_klik)
        self.pas_knop.clicked.connect(self._pas_klik)
        bied_rij.addWidget(self.bied_keuze)
        bied_rij.addWidget(self.bied_doel)
        bied_rij.addWidget(self.bied_knop)
        bied_rij.addWidget(self.pas_knop)
        self.bied_box = QGroupBox("Bieden")
        self.bied_box.setLayout(bied_rij)
        layout.addWidget(self.bied_box)

        keuze_rij = QHBoxLayout()
        self.keuze_combo = QComboBox()
        self.keuze_knop = QPushButton("Kies")
        self.keuze_knop.clicked.connect(self._keuze_klik)
        keuze_rij.addWidget(self.keuze_combo)
        keuze_rij.addWidget(self.keuze_knop)
        self.keuze_box = QGroupBox("Kies troef")
        self.keuze_box.setLayout(keuze_rij)
        layout.addWidget(self.keuze_box)

        # Roem melden (hand of tafel, zie pandoeren/roem.py: RoemClaim) --
        # een lijst met aanvinkbare items plus een knop om door te gaan.
        # Niets aanvinken mag ook (dan meld je nu gewoon niets).
        meld_layout = QVBoxLayout()
        self.meld_lijst = QListWidget()
        self.meld_knop = QPushButton("Meld gekozen roem (of niets aanvinken)")
        self.meld_knop.clicked.connect(self._meld_klik)
        meld_layout.addWidget(self.meld_lijst)
        meld_layout.addWidget(self.meld_knop)
        self.meld_box = QGroupBox("Roem melden")
        self.meld_box.setLayout(meld_layout)
        layout.addWidget(self.meld_box)

        self.volgende_knop = QPushButton("Nieuwe ronde")
        self.volgende_knop.clicked.connect(self.nieuwe_ronde)
        layout.addWidget(self.volgende_knop)

        self.log = QListWidget()
        self.log.setMaximumHeight(70)  # kleiner -- geeft ruimte aan 'gespeelde slagen' hierboven
        layout.addWidget(self.log)

        self._alles_verbergen()
        self._stand_bijwerken()

    # -- de tafel (groen laken, windhoeken) --------------------------------
    def _bouw_tafel(self) -> QWidget:
        """Groen-lakense tafel met de 4 spelers op hun windrichting (jij
        altijd op Zuid, zie WINDRICHTING hierboven) en in het midden de
        kijkkaart. Elke windhoek krijgt een eigen 'windcel' (avatar, naam,
        stand + voor tegenstanders een kaartenteller + een plek voor de
        kaart die ze deze slag gespeeld hebben) -- zie `_maak_windcel` en
        `_zet_slag_kaart`. Tussen de West/Oost-rij en Zuid komt een eigen
        rij voor de instructietekst, als donkere afgeronde banner
        gecentreerd op het laken (net als bij veel kaartspel-apps: 'Geef
        drie kaarten door aan ...')."""
        tafel = QWidget()
        tafel.setObjectName("tafel")
        tafel.setStyleSheet(
            "QWidget#tafel {"
            "  background-color: #1f6f43;"
            "  border: 6px solid #5a3a22;"
            "  border-radius: 22px;"
            "}"
            "QWidget#tafel QLabel { color: #f2f2f2; }"
            "QWidget#tafel QLabel[rol='naam'] { font-weight: bold; }"
            "QWidget#tafel QLabel[rol='windrichting'] { color: #cfe8d8; font-size: 10px; }"
            "QWidget#tafel QLabel[rol='punten'] { color: #ffe9a8; font-size: 11px; }"
            "QWidget#tafel QLabel[rol='marker'] { color: #ffe9a8; font-weight: bold; font-size: 14px; }"
            "QLabel#banner {"
            "  background-color: rgba(20, 20, 20, 170);"
            "  color: #f2f2f2;"
            "  border-radius: 12px;"
            "  padding: 8px 16px;"
            "}"
        )
        tafel.setMinimumHeight(460)

        rooster = QGridLayout(tafel)
        rooster.setContentsMargins(18, 18, 18, 18)
        rooster.setSpacing(10)
        for kolom in range(3):
            rooster.setColumnStretch(kolom, 1)
        for rij in range(4):
            # De bannerrij (rij 2) krijgt geen stretch: die moet precies zo
            # hoog worden als de instructietekst nodig heeft (zie hieronder
            # bij het toevoegen van instructie_label), niet een gelijk deel
            # van de resterende ruimte zoals de windhoek-rijen.
            rooster.setRowStretch(rij, 0 if rij == 2 else 1)

        self._windcellen: dict[int, dict] = {}
        posities = {2: (0, 1), 1: (1, 0), 3: (1, 2), 0: (3, 1)}  # speler -> (rij, kolom)
        for speler, (rij, kolom) in posities.items():
            cel = self._maak_windcel(speler)
            rooster.addWidget(cel, rij, kolom)

        # Midden: de kijkkaart, zichtbaar voor iedereen totdat troef gekozen
        # is (zie _kijkkaart_tonen).
        midden = QWidget()
        midden_layout = QVBoxLayout(midden)
        midden_layout.setContentsMargins(0, 0, 0, 0)
        midden_titel = QLabel("Kijkkaart")
        midden_titel.setProperty("rol", "windrichting")
        midden_titel.setAlignment(Qt.AlignHCenter)
        midden_layout.addWidget(midden_titel)
        self.kijkkaart_houder = QVBoxLayout()
        self.kijkkaart_houder.setAlignment(Qt.AlignHCenter)
        midden_layout.addLayout(self.kijkkaart_houder)
        self._kijkkaart_widget = None
        rooster.addWidget(midden, 1, 1, Qt.AlignCenter)

        # De bannerrij (tussen de West/Oost-rij en Zuid) met de
        # instructietekst, die hiervoor los boven de tafel stond. De banner
        # moet in hoogte meegroeien met het aantal regels dat de tekst nodig
        # heeft (sommige instructies zijn lang en pasten anders niet).
        # Daarvoor mag de label NIET met een alignment-vlag toegevoegd worden
        # (dat laat de grid-cel de label op zijn sizeHint() zetten, wat bij
        # word-wrap niet de echte breedte/hoogte is) -- in plaats daarvan
        # vult de label de volle breedte van de kolommen, zodat Qt de
        # hoogte-voor-die-breedte (heightForWidth) correct kan berekenen,
        # en een verticale sizePolicy van Minimum zodat de rij niet groter
        # wordt dan strikt nodig.
        self.instructie_label.setObjectName("banner")
        self.instructie_label.setAlignment(Qt.AlignCenter)
        self.instructie_label.setSizePolicy(
            QSizePolicy.Preferred, QSizePolicy.Minimum
        )
        rooster.addWidget(self.instructie_label, 2, 0, 1, 3)

        return tafel

    def _maak_windcel(self, speler: int) -> QWidget:
        """Eén plek aan tafel: naam + windrichting, voor tegenstanders ook
        hoeveel kaarten ze nog hebben, en een houder voor de kaart die deze
        speler in de lopende slag heeft gespeeld (leeg als dat nog niet zo
        is). Blijft het hele spel lang hetzelfde widget; alleen de inhoud
        van de kaart-houder en de teller wisselen (zie `_zet_slag_kaart` en
        `_kaarten_over_bijwerken`), net als bij de kijkkaart hierboven."""
        cel = QWidget()
        cel_layout = QVBoxLayout(cel)
        cel_layout.setContentsMargins(0, 0, 0, 0)
        cel_layout.setAlignment(Qt.AlignHCenter)

        # Avatar met daarnaast een plek voor kleine markeringen: een "M"
        # zodra deze speler als je maat is onthuld, en een sterretje als
        # hij deze slag is uitgekomen (zijn kaart bepaalt dan de gevraagde
        # kleur) -- zie _markers_bijwerken. Beide zijn leeg/onzichtbaar
        # totdat van toepassing.
        avatar_rij = QHBoxLayout()
        avatar_rij.setSpacing(4)
        avatar_rij.addStretch()
        avatar = AvatarWidget(speler)
        avatar_rij.addWidget(avatar)
        marker_label = QLabel("")
        marker_label.setProperty("rol", "marker")
        marker_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        avatar_rij.addWidget(marker_label)
        avatar_rij.addStretch()
        cel_layout.addLayout(avatar_rij)

        naam_label = QLabel(NAAM[speler])
        naam_label.setProperty("rol", "naam")
        naam_label.setAlignment(Qt.AlignHCenter)
        cel_layout.addWidget(naam_label)

        wind_label = QLabel(WINDRICHTING[speler])
        wind_label.setProperty("rol", "windrichting")
        wind_label.setAlignment(Qt.AlignHCenter)
        cel_layout.addWidget(wind_label)

        punten_label = QLabel("0")
        punten_label.setProperty("rol", "punten")
        punten_label.setAlignment(Qt.AlignHCenter)
        cel_layout.addWidget(punten_label)

        aantal_label = None
        if speler != 0:
            aantal_label = QLabel("8 kaarten")
            aantal_label.setProperty("rol", "windrichting")
            aantal_label.setAlignment(Qt.AlignHCenter)
            cel_layout.addWidget(aantal_label)

        kaart_houder = QVBoxLayout()
        kaart_houder.setAlignment(Qt.AlignHCenter)
        cel_layout.addLayout(kaart_houder)

        self._windcellen[speler] = {
            "kaart_houder": kaart_houder,
            "kaart_widget": None,
            "aantal_label": aantal_label,
            "punten_label": punten_label,
            "marker_label": marker_label,
        }
        return cel

    def _markers_bijwerken(self):
        """Zet de kleine markering(en) naast elke avatar: "M" bij de speler
        die (eenmaal onthuld, zie _bijwerken_maat_onthulling) je maat is, en
        een sterretje bij wie deze slag is uitgekomen -- diens kaart bepaalt
        immers de gevraagde kleur waar de anderen aan moeten houden (zie
        _slag_tonen). Makkelijker in één oogopslag te zien dan het zelf uit
        de kaarten op tafel af te leiden."""
        for speler in range(4):
            delen = []
            if speler == getattr(self, "_maat_speler", None):
                delen.append("M")
            if speler == getattr(self, "_leider_slag", None):
                delen.append("★")
            self._windcellen[speler]["marker_label"].setText(" ".join(delen))

    def _zet_slag_kaart(self, speler: int, kaart):
        """Wisselt de kaart die in de windcel van `speler` ligt (net als
        `_kijkkaart_tonen`, maar dan per windhoek) -- `kaart=None` maakt de
        plek weer leeg."""
        cel = self._windcellen[speler]
        houder = cel["kaart_houder"]
        if cel["kaart_widget"] is not None:
            houder.removeWidget(cel["kaart_widget"])
            cel["kaart_widget"].deleteLater()
            cel["kaart_widget"] = None
        if kaart is not None:
            widget = KaartWidget(kaart)
            widget.setEnabled(False)
            houder.addWidget(widget)
            cel["kaart_widget"] = widget

    def _kaarten_over_bijwerken(self, zicht):
        """Werkt de 'X kaarten'-teller bij tegenstanders bij, afgeleid uit
        wat ze deze ronde al gespeeld hebben (8 kaarten per speler bij de
        start). Puur ter sfeer/oriëntatie -- precies wat je ook aan een
        echte tafel zou zien (hoeveel kaarten iemand nog in zijn hand
        heeft), geen extra informatie over wélke kaarten dat zijn."""
        gespeeld = {i: 0 for i in range(4)}
        for _, slag in zicht.gespeelde_slagen:
            for speler, _ in slag:
                gespeeld[speler] += 1
        for speler, _ in zicht.huidige_slag:
            gespeeld[speler] += 1
        for speler in range(1, 4):
            aantal_label = self._windcellen[speler]["aantal_label"]
            aantal_label.setText(f"{8 - gespeeld[speler]} kaarten")

    # -- kleine hulpjes -------------------------------------------------
    def _stand_bijwerken(self):
        self.stand_label.setText(
            "Stand: " + ", ".join(f"{NAAM[i]} {self.totalen[i]:+d}" for i in range(4))
        )
        self.pot_label.setText(f"Pot: {self.pot} cent")
        for speler in range(4):
            self._windcellen[speler]["punten_label"].setText(f"{self.totalen[speler]:+d}")

    def _alles_verbergen(self):
        self.bied_box.setVisible(False)
        self.keuze_box.setVisible(False)
        self.meld_box.setVisible(False)

    # Je eigen hand mag prominenter/groter zijn dan de kaarten op tafel --
    # moderne schermen zijn ruim genoeg (>1920x1080), en acht gewaaierde
    # kaarten op deze maat passen daar makkelijk in. De negatieve spacing
    # (zie hieronder) laat ze overlappen, net als een hand kaarten op een
    # echte tafel.
    HAND_BREEDTE, HAND_HOOGTE = 88, 130
    HAND_OVERLAP = -34  # negatieve spacing tussen kaarten = gewaaierd effect

    def _hand_tonen(self, kaarten, aanklikbaar=None):
        """Bouwt de rij kaarten opnieuw op, gewaaierd (overlappend) en
        groter dan de kaarten op tafel/bij de tegenstanders.

        `aanklikbaar=None` (bieden, troef kiezen, ...): kaarten alleen laten
        zien, niet klikbaar -- maar wel gewoon goed leesbaar, er is dan toch
        niets om aan te klikken.
        `aanklikbaar=<set>` (een slag spelen): alleen die kaarten zijn
        klikbaar; de rest wordt getoond maar gedimd, zodat duidelijk is wat
        je nu niet mag spelen.
        """
        while self.hand_layout.count():
            item = self.hand_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.hand_layout.setSpacing(self.HAND_OVERLAP)
        for kaart in sorteer(kaarten):
            if aanklikbaar is None:
                knop = KaartWidget(kaart, breedte=self.HAND_BREEDTE, hoogte=self.HAND_HOOGTE)
                knop.setEnabled(False)
            else:
                mag = kaart in aanklikbaar
                knop = KaartWidget(
                    kaart, gedimd=not mag,
                    breedte=self.HAND_BREEDTE, hoogte=self.HAND_HOOGTE,
                )
                knop.setEnabled(mag)
            knop.clicked.connect(lambda _=False, k=kaart: self._kaart_gekozen(k))
            # Elke volgende kaart overlapt de vorige: daarom moet de laatst
            # toegevoegde kaart bovenop liggen (raise), anders zit hij
            # grotendeels verstopt onder zijn linkerbuur.
            self.hand_layout.addWidget(knop)
            knop.raise_()

    def _kijkkaart_tonen(self, kaart):
        """Wisselt de ene, herbruikte kaartweergave naast 'Kijkkaart op
        tafel:' -- geen kaart als er nog niets gedeeld is."""
        if self._kijkkaart_widget is not None:
            self.kijkkaart_houder.removeWidget(self._kijkkaart_widget)
            self._kijkkaart_widget.deleteLater()
            self._kijkkaart_widget = None
        if kaart is not None:
            self._kijkkaart_widget = KaartWidget(kaart)
            self._kijkkaart_widget.setEnabled(True)
            self.kijkkaart_houder.addWidget(self._kijkkaart_widget)

    def _slag_tonen(self, huidige_slag):
        """Laat de kaarten van de nog lopende slag zien, elk bij de
        windhoek van de speler die hem gespeeld heeft (zie `_zet_slag_kaart`
        en WINDRICHTING) -- zodat je op de tafel kunt volgen wat je
        tegenstanders opgooien, niet alleen wat jijzelf speelt."""
        gespeeld_door = dict(huidige_slag)
        for speler in range(4):
            self._zet_slag_kaart(speler, gespeeld_door.get(speler))
        # Wie als eerste een kaart in deze slag legde, bepaalt de gevraagde
        # kleur -- zie _markers_bijwerken voor het sterretje dat daarbij
        # naast zijn avatar komt.
        self._leider_slag = huidige_slag[0][0] if huidige_slag else None
        self._markers_bijwerken()

    @staticmethod
    def _kaart_html(kaart: Card) -> str:
        """Kaarttekst als HTML, in rood voor harten/ruiten -- zelfde
        kleurindeling als op de kaarten zelf, leest een stuk makkelijker
        terug dan alles in dezelfde kleur."""
        kleur = "#b3261e" if kaart.suit in KaartWidget.ROOD else "#1a1a1a"
        return f'<span style="color: {kleur};">{kaart}</span>'

    def _log_nieuwe_slagen(self, gespeelde_slagen):
        """Zet elke afgeronde slag die nog niet in `slagen_log` staat erin --
        zo blijft zichtbaar wat er al gespeeld is, ook nadat de slag zelf uit
        'Deze slag' is verdwenen (bijv. welke azen of tienen al weg zijn).
        Gebruikt een QLabel per regel (rich text) in plaats van platte
        tekst, zodat de harten/ruiten-symbolen rood kunnen."""
        for i in range(self._gelogde_slagen, len(gespeelde_slagen)):
            winnaar, slag = gespeelde_slagen[i]
            kaarten_html = ", ".join(f"{NAAM[s]}: {self._kaart_html(k)}" for s, k in slag)
            label = QLabel(f"Slag {i + 1}: <b>{NAAM[winnaar]}</b> wint -- {kaarten_html}")
            label.setTextFormat(Qt.RichText)
            item = QListWidgetItem()
            self.slagen_log.addItem(item)
            self.slagen_log.setItemWidget(item, label)
            item.setSizeHint(label.sizeHint())
        self._gelogde_slagen = len(gespeelde_slagen)
        self.slagen_log.scrollToBottom()

    def _kaart_gekozen(self, kaart):
        if self._antwoorden is not None:
            antwoorden, self._antwoorden = self._antwoorden, None
            self._alles_verbergen()
            antwoorden.put(kaart)

    def _log(self, tekst):
        self.log.addItem(tekst)
        self.log.scrollToBottom()

    # -- ronde starten ----------------------------------------------------
    def nieuwe_ronde(self):
        self.volgende_knop.setEnabled(False)
        self.slag_label.setText("")
        self._slag_tonen([])
        for speler in range(1, 4):
            self._windcellen[speler]["aantal_label"].setText("8 kaarten")
        self.slagen_log.clear()
        self._gelogde_slagen = 0
        self.maat_label.setText("")
        self._maat_onthuld = False
        self._maat_speler = None
        self._markers_bijwerken()
        self._kijkkaart_tonen(None)
        self.instructie_label.setText("Nieuwe ronde wordt gedeeld...")
        voorhand = self.ronde % 4
        self._log(f"-- Ronde {self.ronde + 1}, deler/voorhand: {NAAM[voorhand]} --")
        spelers = [
            MenselijkeSpelerQt(self.brug), EenvoudigeSpeler(),
            EenvoudigeSpeler(), EenvoudigeSpeler(),
        ]
        self.worker = RondeWorker(self.brug, spelers, MIDDEN_NEDERLAND, voorhand)
        self.worker.start()

    # -- vragen vanuit de achtergrondthread --------------------------------
    def op_vraag(self, soort, payload, antwoorden):
        self._antwoorden = antwoorden
        self._alles_verbergen()
        methode = getattr(self, f"_vraag_{soort}")
        methode(payload)

    def op_tafelroem(self, winnaar, gemeld, slag_nummer):
        """Puur informatief (geen antwoord nodig, zie Brug.tafelroem): toont
        even wie er roem op tafel meldde -- ook als dat een computerspeler
        was, niet alleen bij jouw eigen slagen. De achtergrondthread houdt
        dit zelf al 3 seconden aan (MenselijkeSpelerQt.toon_tafelroem), dus
        hier hoeft niet apart een timer ingesteld te worden: de eerstvolgende
        instructietekst overschrijft dit vanzelf zodra die 3 seconden om
        zijn."""
        omschrijving = " + ".join(f"{c.omschrijving} ({c.punten})" for c in gemeld)
        self.instructie_label.setText(f"{NAAM[winnaar]} meldt roem: {omschrijving} (slag {slag_nummer})")

    def _vraag_bieden(self, payload):
        hand = payload["hand"]
        huidig_hoogste = payload["huidig_hoogste"]
        variant = payload["variant"]
        self._huidig_hoogste = huidig_hoogste
        self._variant = variant
        self._hand_tonen(hand)
        self._kijkkaart_tonen(payload["kijkkaart"])
        huidig = f"'{huidig_hoogste}'" if huidig_hoogste is not None else "nog niemand"
        self.instructie_label.setText(f"Jouw beurt om te bieden. Hoogste bod tot nu toe: {huidig}.")
        self.bied_keuze.clear()
        self.bied_keuze.addItems(sorted(GEIMPLEMENTEERD))
        self.bied_box.setVisible(True)
        self._bijwerken_bied_doel_zichtbaar()

    def _bijwerken_bied_doel_zichtbaar(self):
        self.bied_doel.setVisible(self.bied_keuze.currentText() == "punten")

    def _bieden_klik(self):
        soort = self.bied_keuze.currentText()
        doel = self.bied_doel.value() if soort == "punten" else None
        bod = Bod(soort, doel)
        try:
            if not self._variant.is_hoger(bod, self._huidig_hoogste):
                QMessageBox.warning(self, "Ongeldig bod", f"'{bod}' is niet hoger dan '{self._huidig_hoogste}'.")
                return
        except ValueError as e:
            QMessageBox.warning(self, "Ongeldig bod", str(e))
            return
        self._antwoord_geven(bod)

    def _pas_klik(self):
        self._antwoord_geven(None)

    def _antwoord_geven(self, waarde):
        if self._antwoorden is not None:
            antwoorden, self._antwoorden = self._antwoorden, None
            self._alles_verbergen()
            antwoorden.put(waarde)

    def _vraag_kies_troef(self, payload):
        hand = payload["hand"]
        self._hand_tonen(hand)
        self.instructie_label.setText("Welke kleur wordt troef?")
        self._keuze_opties({_kleur_label(s): s for s in KLEUREN}, self._troef_gekozen)

    def _vraag_kies_troef_voor_kereltje(self, payload):
        hand = payload["hand"]
        self._hand_tonen(hand)
        eigen_boeren = {k.suit for k in hand if k.rank is Rank.BOER}
        geldig = [s for s in KLEUREN if s not in eigen_boeren] or list(KLEUREN)
        self.instructie_label.setText(
            "Welke kleur wordt troef? (Bij kereltje niet een kleur waarvan je "
            "zelf de boer hebt -- die kleuren staan niet in de lijst.)"
        )
        self._keuze_opties({_kleur_label(s): s for s in geldig}, self._troef_gekozen)

    def _troef_gekozen(self, troef):
        # Zodra troef vaststaat, hoeft de kijkkaart niet langer zichtbaar te
        # blijven: hij mag dan blind (omgekeerd) worden.
        self._kijkkaart_tonen(None)
        self._antwoord_geven(troef)

    def _vraag_kies_troef_en_aas(self, payload):
        hand = payload["hand"]
        self._hand_tonen(hand)
        self._aas_hand = hand
        self.instructie_label.setText(
            "Kies eerst de troefkleur, dan welke aas (of heer) je vraagt."
        )
        self._keuze_opties({_kleur_label(s): s for s in KLEUREN}, self._troef_voor_aas_gekozen)

    def _troef_voor_aas_gekozen(self, troef):
        # Troef staat nu vast (de gevraagde aas/heer volgt hierna nog): de
        # kijkkaart mag vanaf hier blind.
        self._kijkkaart_tonen(None)
        # De troefkleur zelf mag je niet vragen: daar geldt de troefvolgorde
        # (boer, negen, aas, ...) en niet de gewone -- die kleur staat dus
        # niet in de lijst.
        eigen_azen = {k.suit for k in self._aas_hand if k.rank is Rank.AAS}
        vrije_kleuren = [s for s in KLEUREN if s not in eigen_azen and s != troef]
        if vrije_kleuren:
            self.instructie_label.setText("Van welke kleur vraag je de aas?")
            self._keuze_opties(
                {_kleur_label(s): s for s in vrije_kleuren},
                lambda kleur: self._antwoord_geven((troef, Card(kleur, Rank.AAS))),
            )
        else:
            self.instructie_label.setText("Je hebt alle andere azen zelf: van welke kleur vraag je de heer?")
            kandidaten = (
                [s for s in KLEUREN if Card(s, Rank.HEER) not in self._aas_hand and s != troef]
                or [s for s in KLEUREN if s != troef]
            )
            self._keuze_opties(
                {_kleur_label(s): s for s in kandidaten},
                lambda kleur: self._antwoord_geven((troef, Card(kleur, Rank.HEER))),
            )

    def _keuze_opties(self, opties: dict, callback):
        """opties: {label: waarde}. callback(waarde) als er op 'Kies' geklikt wordt."""
        self.keuze_combo.clear()
        self.keuze_combo.addItems(list(opties.keys()))
        self._keuze_callback = lambda: callback(opties[self.keuze_combo.currentText()])
        self.keuze_box.setVisible(True)

    def _keuze_klik(self):
        if self._antwoorden is None:
            return
        self._keuze_callback()

    def _vraag_leg_af(self, payload):
        hand_met_kijkkaart = payload["hand_met_kijkkaart"]
        kijkkaart = hand_met_kijkkaart[-1]
        self.instructie_label.setText(
            "Je hebt het bod gewonnen! Welke kaart leg je gedekt weg? De kaart "
            "met de gouden rand is de kijkkaart -- leg je die zelf terug, dan "
            "speel je verder met je eigen 8 kaarten (ruilen is niet verplicht)."
        )
        while self.hand_layout.count():
            item = self.hand_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.hand_layout.setSpacing(self.HAND_OVERLAP)
        for kaart in sorteer(hand_met_kijkkaart):
            knop = KaartWidget(
                kaart, gemarkeerd=(kaart == kijkkaart),
                breedte=self.HAND_BREEDTE, hoogte=self.HAND_HOOGTE,
            )
            knop.clicked.connect(lambda _=False, k=kaart: self._kaart_gekozen(k))
            self.hand_layout.addWidget(knop)
            knop.raise_()

    def _bijwerken_maat_onthulling(self, zicht):
        """Toont 'Maat: naam' pas op het moment dat dat volgens Butselaar ook
        aan een echte tafel zichtbaar wordt (zie `maat_indien_onthuld` in
        spel.py) -- niet eerder, ook al kent de spelmodule `zicht.partner`
        intern al vanaf slag 1."""
        if self._maat_onthuld:
            return
        maat = maat_indien_onthuld(zicht, mijn_index=0)  # ikzelf ben altijd speler 0
        if maat is not None:
            self._maat_onthuld = True
            self._maat_speler = maat
            self.maat_label.setText(f"Maat: {NAAM[maat]}")
            self._markers_bijwerken()

    def _vraag_speel_kaart(self, payload):
        zicht = payload["zicht"]
        variant = payload["variant"]
        self._log_nieuwe_slagen(zicht.gespeelde_slagen)
        self._bijwerken_maat_onthulling(zicht)
        self._kaarten_over_bijwerken(zicht)
        self.slag_label.setText(
            "" if zicht.huidige_slag else "Jij speelt uit voor deze slag."
        )
        self._slag_tonen(zicht.huidige_slag)
        mogelijk = set(legale_kaarten(zicht.hand, zicht.huidige_slag, zicht.troef, variant))
        self.instructie_label.setText("Welke kaart speel je?")
        self._hand_tonen(zicht.hand, mogelijk)

    # -- roem melden (hand en tafel) ----------------------------------------
    def _meld_tonen(self, aangeboden, titel: str):
        """Toont de aangeboden roem als aanvinkbare regels in `meld_lijst`.
        Niets aanvinken en op de knop klikken mag ook -- dan meld je nu
        gewoon niets (en loop je het risico dat het straks vervalt, precies
        zoals aan een echte tafel)."""
        self._meld_aanbod = list(aangeboden)
        self.meld_lijst.clear()
        for claim in self._meld_aanbod:
            item = QListWidgetItem(f"{claim.omschrijving} ({claim.punten} punten)")
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.meld_lijst.addItem(item)
        self.meld_box.setTitle(titel)
        self.meld_box.setVisible(True)

    def _vraag_meld_roem(self, payload):
        self._meld_tonen(payload["aangeboden"], "Roem melden (in je hand)")
        self.instructie_label.setText(
            "Heb je nu roem te melden? Vink aan wat je meldt (of niets), en klik op de knop."
        )

    def _vraag_meld_tafelroem(self, payload):
        self._meld_tonen(payload["aangeboden"], "Roem melden (op tafel, deze slag)")
        self.instructie_label.setText(
            "Er is roem gevallen in de slag die je net won! Vink aan wat je meldt (of niets)."
        )

    def _meld_klik(self):
        gekozen = [
            claim for i, claim in enumerate(self._meld_aanbod)
            if self.meld_lijst.item(i).checkState() == Qt.Checked
        ]
        self.meld_box.setVisible(False)
        self._antwoord_geven(gekozen)

    # -- einde van de ronde -------------------------------------------------
    def op_resultaat(self, resultaat):
        self._alles_verbergen()
        self.slag_label.setText("")
        self._slag_tonen([])  # laatste slag niet blijven tonen na afloop van de ronde
        self.hand_box.setTitle("Jouw kaarten")
        while self.hand_layout.count():
            item = self.hand_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if resultaat is None:
            self.instructie_label.setText("Iedereen paste (rondpassen) -- opnieuw delen.")
            self._log("Rondpassen.")
        else:
            self._log_nieuwe_slagen(resultaat.slagen)  # ook de laatste slag(en) nog loggen
            for speler, bedrag in resultaat.centen.items():
                self.totalen[speler] += bedrag
                self.pot -= bedrag  # winst wordt uit de pot gehaald, verlies erin terugbetaald
            uitkomst = "gehaald" if resultaat.geslaagd else "niet gehaald"
            partner_tekst = f", partner {NAAM[resultaat.partner]}" if resultaat.partner is not None else ""
            roem_tekst = f" (w.o. {resultaat.roem_team} roem)" if resultaat.roem_team else ""
            punten_tekst = (
                f", {resultaat.punten_team} punten{roem_tekst}"
                if resultaat.punten_team is not None else ""
            )
            self.instructie_label.setText(
                f"Uitslag: {CONTRACTEN[resultaat.contract.soort].naam} door {NAAM[resultaat.bieder]}"
                f"{partner_tekst}{punten_tekst} -- {uitkomst}."
            )
            self._log(
                f"{CONTRACTEN[resultaat.contract.soort].naam} door {NAAM[resultaat.bieder]}"
                f"{partner_tekst}{punten_tekst} -- {uitkomst}; "
                + ", ".join(f"{NAAM[s]} {b:+d}" for s, b in sorted(resultaat.centen.items()))
            )
            # Niet alleen het totaal, ook wát er precies gemeld is -- anders
            # is "roem" een verzamelnaam die (zoals bleek) voor verwarring
            # zorgt tussen bijv. een driekaart en stuk.
            for m in resultaat.roem_meldingen:
                plek = f"hand van {NAAM[m.speler]}" if m.plaats == "hand" else (
                    f"tafel, slag {m.slag_nummer}, gewonnen door {NAAM[m.speler]}"
                )
                self._log(f"  roem gemeld: {m.omschrijving} ({m.punten} punten, {plek})")
            self._stand_bijwerken()
        self.ronde += 1
        self.volgende_knop.setEnabled(True)

    def op_fout(self, tekst):
        self._alles_verbergen()
        QMessageBox.critical(self, "Er ging iets mis", tekst)
        self.volgende_knop.setEnabled(True)


def main():
    app = QApplication(sys.argv)
    venster = Hoofdvenster()
    venster.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
