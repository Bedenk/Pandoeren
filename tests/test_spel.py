import random
import unittest

from pandoeren.cards import Card, Rank, Suit
from pandoeren.spel import (
    EenvoudigeSpeler, RondeResultaat, Zicht, bied_ronde, maat_indien_onthuld,
    speel_ronde,
)
from pandoeren.variant import MIDDEN_NEDERLAND, Bod
from tests.test_engine import hand


class EenBod(EenvoudigeSpeler):
    """Zoals EenvoudigeSpeler, maar biedt precies één keer een vast bod (de
    eerste keer dat het zijn beurt is) en past daarna altijd."""

    def __init__(self, bod: Bod, rng=None):
        super().__init__(rng)
        self.bod = bod
        self._al_geboden = False

    def bieden(self, hand, huidig_hoogste, kijkkaart, variant):
        if not self._al_geboden:
            self._al_geboden = True
            return self.bod
        return None


class AltijdPassen(EenvoudigeSpeler):
    pass  # EenvoudigeSpeler past al altijd


class KiestEigenBoerVoorKereltje(EenBod):
    """Kiest bewust een troefkleur waarvan hij zelf de boer heeft -- om te
    testen dat de engine dat weigert. Gaat ervan uit dat de hand minstens
    één eigen boer heeft (de test kiest daarom een seed waarvoor dat zo is)."""

    def kies_troef_voor_kereltje(self, hand, variant):
        eigen_boeren = [k.suit for k in hand if k.rank is Rank.BOER]
        return eigen_boeren[0]


class VraagtAasVanTroefkleur(EenBod):
    """Vraagt bewust een aas uit de eigen troefkleur -- om te testen dat de
    engine dat weigert (in troef geldt de troefvolgorde, geen 'gevraagd aas')."""

    def kies_troef_en_aas(self, hand, variant):
        troef, _ = super().kies_troef_en_aas(hand, variant)
        return troef, Card(troef, Rank.AAS)


class TestBiedRonde(unittest.TestCase):
    def test_hoogste_bod_wint(self):
        spelers = [AltijdPassen(), EenBod(Bod("punten", 150)), AltijdPassen(), AltijdPassen()]
        handen = [hand("S:7"), hand("S:8"), hand("S:9"), hand("S:10")]
        resultaat = bied_ronde(spelers, handen, hand("H:6")[0], MIDDEN_NEDERLAND)
        self.assertIsNotNone(resultaat)
        bieder, bod, deelgenomen = resultaat
        self.assertEqual(bieder, 1)
        self.assertEqual(bod, Bod("punten", 150))
        self.assertEqual(deelgenomen, {1})

    def test_hoger_bod_overtroeft_lager(self):
        spelers = [
            EenBod(Bod("punten", 130)),
            EenBod(Bod("misere")),
            AltijdPassen(),
            AltijdPassen(),
        ]
        handen = [hand("S:7"), hand("S:8"), hand("S:9"), hand("S:10")]
        bieder, bod, deelgenomen = bied_ronde(spelers, handen, hand("H:6")[0], MIDDEN_NEDERLAND)
        # misère staat hoger dan punten-130 in Butselaar's volgorde
        self.assertEqual(bieder, 1)
        self.assertEqual(bod, Bod("misere"))
        self.assertEqual(deelgenomen, {0, 1})

    def test_rondpassen_als_iedereen_past(self):
        spelers = [AltijdPassen() for _ in range(4)]
        handen = [hand("S:7"), hand("S:8"), hand("S:9"), hand("S:10")]
        self.assertIsNone(bied_ronde(spelers, handen, hand("H:6")[0], MIDDEN_NEDERLAND))


class TestSpeelRondeGeimplementeerd(unittest.TestCase):
    def _speel(self, bod, voorhand=0, seed=1):
        spelers = [AltijdPassen() for _ in range(4)]
        spelers[voorhand] = EenBod(bod)
        return speel_ronde(spelers, MIDDEN_NEDERLAND, random.Random(seed), voorhand)

    def test_rondpassen_geeft_none(self):
        spelers = [AltijdPassen() for _ in range(4)]
        self.assertIsNone(speel_ronde(spelers, MIDDEN_NEDERLAND, random.Random(1)))

    def test_puntenspel_met_geroepen_aas(self):
        resultaat = self._speel(Bod("punten", 130))
        self.assertIsInstance(resultaat, RondeResultaat)
        self.assertEqual(resultaat.contract, Bod("punten", 130))
        self.assertEqual(resultaat.bieder, 0)
        self.assertIsNotNone(resultaat.partner)
        self.assertNotEqual(resultaat.partner, resultaat.bieder)
        self.assertEqual(len(resultaat.slagen), 8)
        # alle 32 gespeelde kaarten (8 slagen x 4 spelers) zijn verschillend
        gespeeld = [kaart for _, slag in resultaat.slagen for _, kaart in slag]
        self.assertEqual(len(gespeeld), 32)
        self.assertEqual(len(set(gespeeld)), 32)
        self.assertIsInstance(resultaat.punten_team, int)
        self.assertGreaterEqual(resultaat.punten_team, 0)
        # Roem/stuk moet tijdens het spel gemeld worden (Butselaar, blz. 12)
        # of hij vervalt -- EenvoudigeSpeler meldt gewoon alles meteen (zie
        # TestRoemMelden hieronder voor het vervallen-gedrag), dus deze
        # waarde zit hier nog steeds gewoon in punten_team verwerkt.
        self.assertIsInstance(resultaat.roem_team, int)
        self.assertGreaterEqual(resultaat.roem_team, 0)
        self.assertLessEqual(resultaat.roem_team, resultaat.punten_team)
        bedrag = MIDDEN_NEDERLAND.uitbetaling(resultaat.contract)
        teken = 1 if resultaat.geslaagd else -1
        self.assertEqual(resultaat.centen[resultaat.bieder], teken * bedrag)
        self.assertEqual(resultaat.centen[resultaat.partner], teken * bedrag)
        self.assertEqual(set(resultaat.centen), {resultaat.bieder, resultaat.partner})

    def test_pandoer_alle_slagen_nodig(self):
        resultaat = self._speel(Bod("pandoer"), seed=2)
        self.assertEqual(resultaat.contract, Bod("pandoer"))
        team = {resultaat.bieder, resultaat.partner}
        alle_slagen_bij_team = all(winnaar in team for winnaar, _ in resultaat.slagen)
        self.assertEqual(resultaat.geslaagd, alle_slagen_bij_team)
        self.assertIsNone(resultaat.punten_team)
        self.assertIsNone(resultaat.roem_team)

    def test_misere_geen_slag_mag(self):
        resultaat = self._speel(Bod("misere"), seed=3)
        self.assertEqual(resultaat.contract, Bod("misere"))
        self.assertIsNone(resultaat.partner)
        geen_slag = not any(w == resultaat.bieder for w, _ in resultaat.slagen)
        self.assertEqual(resultaat.geslaagd, geen_slag)
        self.assertEqual(set(resultaat.centen), {resultaat.bieder})
        self.assertEqual(abs(resultaat.centen[resultaat.bieder]), 3)

    def test_misere_ouvert(self):
        resultaat = self._speel(Bod("misere_ouvert"), seed=4)
        self.assertEqual(resultaat.contract, Bod("misere_ouvert"))
        self.assertIsNotNone(resultaat.troef)  # bevestigd: ook ouvert heeft troef
        self.assertEqual(abs(resultaat.centen[resultaat.bieder]), 6)

    def test_pandoer_prive_alleen_alle_slagen(self):
        resultaat = self._speel(Bod("pandoer_prive"), seed=5)
        alle_zelf = all(w == resultaat.bieder for w, _ in resultaat.slagen)
        self.assertEqual(resultaat.geslaagd, alle_zelf)
        self.assertIsNone(resultaat.partner)
        self.assertEqual(set(resultaat.centen), {resultaat.bieder})
        self.assertEqual(abs(resultaat.centen[resultaat.bieder]), 10)

    def test_declarant_kan_niet_zichzelf_partner_kiezen(self):
        # elke speler heeft precies 1 kaart van elke rang niet in eigen hand
        # nodig; hier vertrouwen we erop dat kies_troef_en_aas dat afdwingt
        # en dat de partnerkeuze altijd een ANDERE speler oplevert.
        for seed in range(10):
            resultaat = self._speel(Bod("punten", 130), seed=seed)
            self.assertNotEqual(resultaat.partner, resultaat.bieder)

    def test_kereltje_partner_is_troefboerhouder(self):
        for seed in range(10):
            resultaat = self._speel(Bod("kereltje"), seed=seed)
            self.assertEqual(resultaat.contract, Bod("kereltje"))
            team = {resultaat.bieder} | ({resultaat.partner} if resultaat.partner is not None else set())
            gespeeld = [(spl, k) for _, slag in resultaat.slagen for spl, k in slag]
            jas = Card(resultaat.troef, Rank.BOER)
            spelers_met_jas = [spl for spl, k in gespeeld if k == jas]
            if spelers_met_jas:
                # als de troefboer daadwerkelijk gespeeld is, zit die speler
                # in het team -- en dat is nooit de bieder zelf (regel: je
                # mag geen troef kiezen waarvan je zelf de boer hebt).
                speler_van_jas = spelers_met_jas[0]
                self.assertNotEqual(speler_van_jas, resultaat.bieder)
                self.assertIn(speler_van_jas, team)
            # de bieder zelf heeft de troefboer nooit in zijn gespeelde kaarten
            eigen_kaarten = [k for spl, k in gespeeld if spl == resultaat.bieder]
            self.assertNotIn(jas, eigen_kaarten)
            self.assertEqual(
                resultaat.geslaagd,
                all(w in team for w, _ in resultaat.slagen),
            )

    def test_zwabber_partner_is_winnaar_eerste_slag(self):
        for seed in range(10):
            resultaat = self._speel(Bod("zwabber"), seed=seed)
            self.assertEqual(resultaat.contract, Bod("zwabber"))
            self.assertIsNone(resultaat.troef)
            eerste_winnaar = resultaat.slagen[0][0]
            verwachte_partner = eerste_winnaar if eerste_winnaar != resultaat.bieder else None
            self.assertEqual(resultaat.partner, verwachte_partner)
            team = {resultaat.bieder} | ({resultaat.partner} if resultaat.partner is not None else set())
            self.assertEqual(
                resultaat.geslaagd,
                all(w in team for w, _ in resultaat.slagen),
            )

    def test_kereltje_eigen_boer_als_troef_is_ongeldig(self):
        # seed 2: speler 0 heeft na het ruilen zelf de schoppenboer.
        spelers = [AltijdPassen() for _ in range(4)]
        spelers[0] = KiestEigenBoerVoorKereltje(Bod("kereltje"))
        with self.assertRaises(ValueError):
            speel_ronde(spelers, MIDDEN_NEDERLAND, random.Random(2), 0)

    def test_gevraagd_aas_uit_troefkleur_is_ongeldig(self):
        # Je mag geen aas (of heer) uit je eigen troefkleur vragen: daar
        # geldt de troefvolgorde (boer, negen, aas, ...), niet de gewone.
        # Zoek een seed waarbij speler 0 zijn eigen troefaas niet al in
        # handen heeft, zodat echt deze regel getest wordt (en niet de
        # eerdere "moet een kaart zijn die je zelf niet hebt"-check).
        for seed in range(20):
            spelers = [AltijdPassen() for _ in range(4)]
            spelers[0] = VraagtAasVanTroefkleur(Bod("punten", 100))
            try:
                speel_ronde(spelers, MIDDEN_NEDERLAND, random.Random(seed), 0)
            except ValueError as e:
                if "troefkleur" in str(e):
                    return
        self.fail("Geen enkele seed leverde een geldige testcase op voor deze regel.")

    def test_solo_zwabber_alleen_alle_slagen(self):
        resultaat = self._speel(Bod("solo_zwabber"), seed=7)
        self.assertIsNone(resultaat.troef)
        self.assertIsNone(resultaat.partner)
        alle_zelf = all(w == resultaat.bieder for w, _ in resultaat.slagen)
        self.assertEqual(resultaat.geslaagd, alle_zelf)
        self.assertEqual(set(resultaat.centen), {resultaat.bieder})
        self.assertEqual(abs(resultaat.centen[resultaat.bieder]), 5)

    def test_piccolo_precies_een_slag_met_troefboer(self):
        for seed in range(10):
            resultaat = self._speel(Bod("piccolo"), seed=seed)
            self.assertIsNone(resultaat.partner)
            eigen_slagen = [s for w, s in resultaat.slagen if w == resultaat.bieder]
            if len(eigen_slagen) == 1:
                eigen_kaart = next(k for spl, k in eigen_slagen[0] if spl == resultaat.bieder)
                verwacht = eigen_kaart == Card(resultaat.troef, Rank.BOER)
            else:
                verwacht = False
            self.assertEqual(resultaat.geslaagd, verwacht)
            self.assertEqual(abs(resultaat.centen[resultaat.bieder]), 3)


class TestPraatjeFamilie(unittest.TestCase):
    """stil praatje, praatje, piccolo ouvert, stil piccolo-praatje en
    piccolo-praatje: allemaal met troef (bevestigd in het boekje), zonder
    partner. De "open kaarten"/"wel of niet overleggen"-kant is een zaak van
    de toekomstige client, niet van de score -- zie de moduledocstring."""

    def _speel(self, bod, seed):
        spelers = [AltijdPassen() for _ in range(4)]
        spelers[0] = EenBod(bod)
        return speel_ronde(spelers, MIDDEN_NEDERLAND, random.Random(seed), 0)

    def test_stil_praatje_geen_slag_met_troef(self):
        resultaat = self._speel(Bod("stil_praatje"), seed=8)
        self.assertEqual(resultaat.contract, Bod("stil_praatje"))
        self.assertIsNotNone(resultaat.troef)
        self.assertIsNone(resultaat.partner)
        geen_slag = not any(w == resultaat.bieder for w, _ in resultaat.slagen)
        self.assertEqual(resultaat.geslaagd, geen_slag)
        self.assertEqual(abs(resultaat.centen[resultaat.bieder]), 8)

    def test_praatje_geen_slag_met_troef(self):
        resultaat = self._speel(Bod("praatje"), seed=9)
        self.assertEqual(resultaat.contract, Bod("praatje"))
        self.assertIsNotNone(resultaat.troef)
        self.assertIsNone(resultaat.partner)
        geen_slag = not any(w == resultaat.bieder for w, _ in resultaat.slagen)
        self.assertEqual(resultaat.geslaagd, geen_slag)
        self.assertEqual(abs(resultaat.centen[resultaat.bieder]), 9)

    def _check_piccolo_variant(self, soort, seed, bedrag):
        resultaat = self._speel(Bod(soort), seed=seed)
        self.assertEqual(resultaat.contract, Bod(soort))
        self.assertIsNotNone(resultaat.troef)
        self.assertIsNone(resultaat.partner)
        eigen_slagen = [s for w, s in resultaat.slagen if w == resultaat.bieder]
        if len(eigen_slagen) == 1:
            eigen_kaart = next(k for spl, k in eigen_slagen[0] if spl == resultaat.bieder)
            verwacht = eigen_kaart == Card(resultaat.troef, Rank.BOER)
        else:
            verwacht = False
        self.assertEqual(resultaat.geslaagd, verwacht)
        self.assertEqual(abs(resultaat.centen[resultaat.bieder]), bedrag)

    def test_piccolo_ouvert(self):
        for seed in range(10):
            self._check_piccolo_variant("piccolo_ouvert", seed, 5)

    def test_stil_piccolo_praatje(self):
        for seed in range(10):
            self._check_piccolo_variant("stil_piccolo_praatje", seed, 6)

    def test_piccolo_praatje(self):
        for seed in range(10):
            self._check_piccolo_variant("piccolo_praatje", seed, 7)


class TestAlleContractenSpeelbaar(unittest.TestCase):
    """Elk van de veertien spellen uit variant.CONTRACTEN moet zonder fouten
    een volledige ronde kunnen spelen (geen NotImplementedError meer)."""

    def test_elk_contract_speelt_een_ronde_zonder_fouten(self):
        from pandoeren.spel import GEIMPLEMENTEERD
        from pandoeren.variant import CONTRACTEN

        self.assertEqual(set(GEIMPLEMENTEERD), set(CONTRACTEN))
        for seed, soort in enumerate(sorted(CONTRACTEN)):
            bod = Bod(soort, 130) if soort == "punten" else Bod(soort)
            spelers = [AltijdPassen() for _ in range(4)]
            spelers[0] = EenBod(bod)
            resultaat = speel_ronde(spelers, MIDDEN_NEDERLAND, random.Random(seed), 0)
            self.assertIsInstance(resultaat, RondeResultaat, msg=soort)
            self.assertEqual(len(resultaat.slagen), 8, msg=soort)


class TestMaatOnthulling(unittest.TestCase):
    """maat_indien_onthuld() mag de maat pas prijsgeven zodra dat ook aan
    tafel zichtbaar zou zijn (Butselaar): de gevraagde kaart gespeeld, of de
    BIEDER zelf die zijn eerste slag binnenhaalt (de maat haalt hem dan van
    tafel) -- niet eerder, en ook niet als de maat zelf een slag wint zonder
    dat de gevraagde kaart daarbij valt (dat is aan tafel niet van een
    gewone slagwinst te onderscheiden), ook al kent Zicht.partner het
    antwoord intern al vanaf slag 1."""

    def _zicht(self, bieder=0, partner=1, gevraagde_kaart=None,
               huidige_slag=None, gespeelde_slagen=None):
        return Zicht(
            ik=0, hand=[], troef=Suit.SCHOPPEN, contract=Bod("punten", 130),
            bieder=bieder, partner=partner,
            huidige_slag=huidige_slag or [], gespeelde_slagen=gespeelde_slagen or [],
            gevraagde_kaart=gevraagde_kaart,
        )

    def test_geen_maat_dus_niets_te_onthullen(self):
        zicht = self._zicht(partner=None)
        self.assertIsNone(maat_indien_onthuld(zicht, mijn_index=0))

    def test_ik_zit_niet_in_dit_team(self):
        # bieder=0, partner=1, maar ik ben speler 2 (tegenstander) -- geen
        # eigen maat om te onthullen, wat er ook al gespeeld is.
        aas = Card(Suit.KLAVEREN, Rank.AAS)
        zicht = self._zicht(gevraagde_kaart=aas, huidige_slag=[(3, aas)])
        self.assertIsNone(maat_indien_onthuld(zicht, mijn_index=2))

    def test_nog_niets_gespeeld_dus_nog_niet_onthuld(self):
        aas = Card(Suit.KLAVEREN, Rank.AAS)
        zicht = self._zicht(gevraagde_kaart=aas)
        self.assertIsNone(maat_indien_onthuld(zicht, mijn_index=0))

    def test_gevraagde_kaart_in_lopende_slag_onthult_meteen(self):
        aas = Card(Suit.KLAVEREN, Rank.AAS)
        zicht = self._zicht(gevraagde_kaart=aas, huidige_slag=[(1, aas)])
        self.assertEqual(maat_indien_onthuld(zicht, mijn_index=0), 1)

    def test_gevraagde_kaart_in_afgeronde_slag_onthult(self):
        aas = Card(Suit.KLAVEREN, Rank.AAS)
        andere = Card(Suit.SCHOPPEN, Rank.ZEVEN)
        slag = [(0, andere), (1, aas), (2, andere), (3, andere)]
        zicht = self._zicht(gevraagde_kaart=aas, gespeelde_slagen=[(2, slag)])
        self.assertEqual(maat_indien_onthuld(zicht, mijn_index=0), 1)

    def test_eerste_slag_gewonnen_door_bieder_onthult_ook_zonder_gevraagde_kaart(self):
        # Zoals bij kereltje: geen gevraagde_kaart, maar de bieder zelf wint
        # de eerste slag en de maat (troefboer-houder) haalt hem van tafel.
        kaart = Card(Suit.SCHOPPEN, Rank.ZEVEN)
        slag = [(0, kaart), (1, kaart), (2, kaart), (3, kaart)]
        zicht = self._zicht(gevraagde_kaart=None, gespeelde_slagen=[(0, slag)])
        self.assertEqual(maat_indien_onthuld(zicht, mijn_index=0), 1)

    def test_eerste_slag_gewonnen_door_maat_zelf_onthult_niets(self):
        # De maat wint een slag, maar zonder dat de gevraagde kaart valt --
        # aan een echte tafel is dat niet te onderscheiden van een gewone
        # slagwinst, dus dit mag de maat nog niet verraden.
        kaart = Card(Suit.SCHOPPEN, Rank.ZEVEN)
        slag = [(0, kaart), (1, kaart), (2, kaart), (3, kaart)]
        zicht = self._zicht(gevraagde_kaart=None, gespeelde_slagen=[(1, slag)])
        self.assertIsNone(maat_indien_onthuld(zicht, mijn_index=0))

    def test_slag_gewonnen_door_tegenstander_onthult_niets(self):
        kaart = Card(Suit.SCHOPPEN, Rank.ZEVEN)
        slag = [(0, kaart), (1, kaart), (2, kaart), (3, kaart)]
        zicht = self._zicht(gevraagde_kaart=None, gespeelde_slagen=[(2, slag)])
        self.assertIsNone(maat_indien_onthuld(zicht, mijn_index=0))

    def test_werkt_ook_als_ikzelf_de_maat_ben_niet_de_bieder(self):
        aas = Card(Suit.KLAVEREN, Rank.AAS)
        zicht = self._zicht(bieder=2, partner=0, gevraagde_kaart=aas, huidige_slag=[(2, aas)])
        self.assertEqual(maat_indien_onthuld(zicht, mijn_index=0), 2)

    def test_bieder_wint_eerste_slag_onthult_ook_als_ikzelf_de_maat_ben(self):
        kaart = Card(Suit.SCHOPPEN, Rank.ZEVEN)
        slag = [(2, kaart), (0, kaart), (1, kaart), (3, kaart)]
        zicht = self._zicht(bieder=2, partner=0, gevraagde_kaart=None, gespeelde_slagen=[(2, slag)])
        self.assertEqual(maat_indien_onthuld(zicht, mijn_index=0), 2)


class NooitMeldt(EenBod):
    """Zoals EenBod, maar meldt nooit roem -- gebruikt om te testen dat
    ongemelde roem (hand én tafel) echt vervalt (Butselaar, blz. 12)."""

    def meld_roem(self, aangeboden, variant):
        return []

    def meld_tafelroem(self, aangeboden, variant):
        return []


class TestRoemMelden(unittest.TestCase):
    """EenvoudigeSpeler (en dus EenBod) meldt alles meteen zodra het kan --
    zie EenvoudigeSpeler.meld_roem. Deze tests vergelijken twee identieke
    rondes (zelfde deling, zelfde speelbeslissingen -- alleen de
    speler-eigen rng's zijn ook vast gezet, anders kiest kies_troef_en_aas
    willekeurig een andere kleur/kaart en zijn de rondes niet meer
    vergelijkbaar) waarin alleen het wel/niet melden verschilt."""

    def _speel(self, cls, voorhand=0, bod_doel=60):
        spelers = [AltijdPassen(random.Random(99)) for _ in range(4)]
        spelers[voorhand] = cls(Bod("punten", bod_doel), random.Random(99))
        return speel_ronde(spelers, MIDDEN_NEDERLAND, random.Random(0), voorhand)

    def test_nooit_melden_kost_alle_hand_en_tafelroem(self):
        altijd = self._speel(EenBod, voorhand=0)
        nooit = self._speel(NooitMeldt, voorhand=0)
        # Zelfde deling en dezelfde speelbeslissingen (zie _speel): bieder,
        # partner en troef moeten dus gelijk zijn, anders is de vergelijking
        # zinloos.
        self.assertEqual(altijd.bieder, nooit.bieder)
        self.assertEqual(altijd.partner, nooit.partner)
        self.assertEqual(altijd.troef, nooit.troef)
        # Deze deling heeft daadwerkelijk roem op te melden (zie het seed-
        # onderzoek in het gesprek met de gebruiker, 2026-10-02) -- anders
        # test dit niets.
        self.assertGreater(altijd.roem_team, 0)
        self.assertEqual(nooit.roem_team, 0)
        # De kaartpunten zelf (dus los van roem) zijn ongewijzigd: hetzelfde
        # spel is gespeeld, alleen het melden verschilt.
        self.assertEqual(
            altijd.punten_team - altijd.roem_team,
            nooit.punten_team - nooit.roem_team,
        )
        # Door het gemiste roem haalt 'nooit' het bod dus eerder niet.
        self.assertGreaterEqual(altijd.punten_team, nooit.punten_team)
        # roem_meldingen (de uitgeschreven lijst, voor in de client) moet
        # precies optellen tot roem_team, en bij 'nooit' leeg zijn -- er is
        # dan immers niets gemeld.
        self.assertEqual(sum(m.punten for m in altijd.roem_meldingen), altijd.roem_team)
        self.assertEqual(nooit.roem_meldingen, [])
        self.assertTrue(all(m.plaats in ("hand", "tafel") for m in altijd.roem_meldingen))
        # Elke melding heeft een eigen, specifieke omschrijving (bijv. "stuk"
        # of "3-reeks, hoogste heer ♠") -- geen verzamelterm als "roem/stuk".
        self.assertTrue(all("roem/stuk" not in m.omschrijving for m in altijd.roem_meldingen))

    def test_gemelde_roem_mag_nog_ontkend_worden(self):
        # Het bestaande ontken-mechanisme (hogere roem bij een tegenstander)
        # moet onveranderd blijven werken op de gemelde reeksen/vier-gelijke
        # -- alleen stuk en roem-op-tafel blijven daarvan uitgezonderd, zie
        # spel.py. Dit test geen specifiek scenario, alleen dat het resultaat
        # geldig blijft (geen crash, roem_team >= 0) voor een paar seeds.
        for seed in range(10):
            spelers = [AltijdPassen(random.Random(seed)) for _ in range(4)]
            spelers[0] = EenBod(Bod("punten", 60), random.Random(seed))
            resultaat = speel_ronde(spelers, MIDDEN_NEDERLAND, random.Random(seed), 0)
            self.assertGreaterEqual(resultaat.roem_team, 0)


if __name__ == "__main__":
    unittest.main()
