# Changelog

Versienummers volgen [Semantic Versioning](https://semver.org/lang/nl/):
`MAJOR.MINOR.PATCH`. Zolang we op `0.x` staan is alles nog beta -- een
MINOR-bump (0.1.0 -> 0.2.0) mag dus ook zonder volledige achterwaartse
compatibiliteit. Het versienummer zelf staat in `pandoeren/__init__.py`
(`__version__`) en is te zien in de titelbalk van de Qt-client.

## 0.1.1 -- 2026-10-05

- Programma-icoon toegevoegd: de eigen ingescande hartenaas
  (`assets/icon.png`/`assets/icon.ico`), zichtbaar in het venster, de
  taakbalk en (op Windows) op `pandoeren.exe` zelf. Voor een Linux-menu-item
  wijst `Icon=` in je `.desktop`-bestand naar `assets/icon.png`.

## 0.1.0 -- 2026-10-05

Eerste versie die als los pakket is uitgedeeld, bedoeld voor de eerste
beta-testers (o.a. Ronald).

- Speelbare engine (`pandoeren/`) met bieden, troef kiezen, kaarten
  bijspelen, roem (hand en -- als aanname, nog niet boekje-bevestigd --
  op tafel), en afrekenen, volgens Butselaar (1958).
- Qt-client (`client_qt.py`): speeltafel met avatars, waaierende hand,
  roem melden, banner met automatisch passende hoogte.
- Terminal-client (`speeltest.py`) voor snel testen zonder GUI.
- Geautomatiseerde Windows- en Linux-build via GitHub Actions, gepubliceerd
  als losse downloads op de Releases-pagina (geen installatie nodig).
- Biedkeuze in de Qt-client toont alleen nog boden die op dat moment
  geldig zijn.
