# Pandoeren

Het oude Nederlandse kaartspel, als Python-engine. Doel: het spel bewaren, met
regels die per streek of familie instelbaar zijn.

## Opzet

| Bestand | Inhoud |
|---|---|
| `pandoeren/cards.py` | kaarten, 33-kaartenspel, delen, punten, wie wint een slag |
| `pandoeren/roem.py` | roem (reeksen, vier gelijke), stuk, roem ontkennen |
| `pandoeren/spelregels.py` | welke kaart je mag bijspelen (bekennen, troeven, jas) |
| `pandoeren/variant.py` | biedvolgorde, uitbetaling in centen, instellingen per variant |
| `tests/` | tests |

De engine kent geen scherm. De Qt-client (PySide6) komt er later bovenop.

## Tests draaien

Vanuit deze map, zonder extra pakketten:

    python3 -m unittest -v

## De variant

`MIDDEN_NEDERLAND` volgt sinds hoofdstuk 1 van Butselaar (1958) grotendeels dat
boekje: biedvolgorde, bedragen per spel, troeven (nooit verplicht hoger),
en roem (onbeperkt dubbel te gebruiken). `MIDDEN_NEDERLAND.open_vragen()`
geeft de instellingen die nog niet bevestigd zijn, zoals het moment waarop je
roem meldt.

## Bronnen

- A.C. Butselaar, *Pandoeren* (1958) — eigen exemplaar, wordt pagina voor
  pagina verwerkt.
- Aanvullend: Wikipedia, Pagat.com, voor wat het boekje nog niet dekt.
