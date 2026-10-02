import random
import unittest

from pandoeren.cards import (
    Card, Rank, Suit, TOTAAL_PUNTEN, LAATSTE_SLAG_PUNTEN,
    deel, kaart_punten, maak_spel, slag_winnaar,
)
from pandoeren.roem import (
    beste_roem, heeft_stuk, hoogste_enkele_roem, kan_ontkennen, roem_totaal,
)
from pandoeren.variant import MIDDEN_NEDERLAND, Bod, Zekerheid

S, H, R, K = Suit.SCHOPPEN, Suit.HARTEN, Suit.RUITEN, Suit.KLAVEREN


def hand(*kaarten):
    """hand('H:V,B,10', 'S:A') -> kaarten. Kleur:rangen, gescheiden door komma's."""
    kleuren = {"S": S, "H": H, "R": R, "K": K}
    rangen = {"6": Rank.ZES, "7": Rank.ZEVEN, "8": Rank.ACHT, "9": Rank.NEGEN,
              "10": Rank.TIEN, "B": Rank.BOER, "V": Rank.VROUW,
              "H": Rank.HEER, "A": Rank.AAS}
    uit = []
    for groep in kaarten:
        kleur, lijst = groep.split(":")
        uit += [Card(kleuren[kleur], rangen[r]) for r in lijst.split(",")]
    return uit


class TestKaarten(unittest.TestCase):
    def test_spel_heeft_33_unieke_kaarten_met_harten_zes(self):
        spel = maak_spel()
        self.assertEqual(len(spel), 33)
        self.assertEqual(len(set(spel)), 33)
        self.assertIn(Card(H, Rank.ZES), spel)
        self.assertNotIn(Card(S, Rank.ZES), spel)

    def test_totaal_146_punten_bij_elke_troef(self):
        for troef in Suit:
            kaartpunten = sum(kaart_punten(k, troef) for k in maak_spel())
            self.assertEqual(kaartpunten + LAATSTE_SLAG_PUNTEN, TOTAAL_PUNTEN)

    def test_troefpunten(self):
        self.assertEqual(kaart_punten(Card(H, Rank.BOER), H), 20)
        self.assertEqual(kaart_punten(Card(H, Rank.NEGEN), H), 14)
        self.assertEqual(kaart_punten(Card(S, Rank.BOER), H), 1)
        self.assertEqual(kaart_punten(Card(S, Rank.NEGEN), H), 0)

    def test_delen(self):
        handen, kijkkaart = deel(random.Random(1))
        self.assertEqual([len(h) for h in handen], [8, 8, 8, 8])
        alles = [k for h in handen for k in h] + [kijkkaart]
        self.assertEqual(len(set(alles)), 33)

    def test_slag_winnaar(self):
        # troefboer wint van troefnegen en troefaas
        slag = [(0, Card(H, Rank.AAS)), (1, Card(H, Rank.NEGEN)), (2, Card(H, Rank.BOER)), (3, Card(H, Rank.HEER))]
        self.assertEqual(slag_winnaar(slag, H), 2)
        # zonder troef wint de hoogste kaart van de gevraagde kleur
        slag = [(0, Card(S, Rank.TIEN)), (1, Card(R, Rank.AAS)), (2, Card(S, Rank.HEER)), (3, Card(S, Rank.ACHT))]
        self.assertEqual(slag_winnaar(slag, H), 2)
        # laagste troef slaat de gevraagde kleur
        slag = [(0, Card(S, Rank.AAS)), (1, Card(H, Rank.ZES)), (2, Card(S, Rank.HEER)), (3, Card(K, Rank.AAS))]
        self.assertEqual(slag_winnaar(slag, H), 1)
        # zonder troef (misère, zwabber): geen troef
        self.assertEqual(slag_winnaar(slag, None), 0)


class TestRoem(unittest.TestCase):
    def test_reeksen(self):
        self.assertEqual(beste_roem(hand("H:V,B,10", "S:7", "R:A", "K:8", "K:6"))[0], 20)
        self.assertEqual(beste_roem(hand("H:H,V,B,10", "S:7", "R:A", "K:8"))[0], 50)
        self.assertEqual(beste_roem(hand("H:A,H,V,B,10", "S:7", "R:8", "K:6"))[0], 100)

    def test_lange_reeks_met_harten_zes(self):
        # harten 6 t/m heer: 8 kaarten in één reeks
        h = hand("H:6,7,8,9,10,B,V,H")
        self.assertEqual(beste_roem(h)[0], 160)

    def test_vier_boeren(self):
        h = hand("S:B", "H:B", "R:B", "K:B", "S:7", "H:8", "R:9", "K:A")
        self.assertEqual(beste_roem(h)[0], 200)

    def test_twee_losse_reeksen_tellen_samen(self):
        h = hand("S:A,H,V", "R:9,10,B", "K:7", "H:8")
        self.assertEqual(beste_roem(h)[0], 40)

    def test_kaart_telt_maar_in_een_combinatie(self):
        # H:V,B,10,9 (reeks van 4 = 50) tegenover vier vrouwen (100) + B,10,9 (20)
        h = hand("H:V,B,10,9", "S:V", "R:V", "K:V", "S:7")
        punten, gekozen = beste_roem(h)
        self.assertEqual(punten, 120)
        self.assertEqual(len(gekozen), 2)

    def test_dubbel_gebruik_als_variant(self):
        h = hand("H:V,B,10,9", "S:V", "R:V", "K:V", "S:7")
        self.assertEqual(beste_roem(h, kaarten_dubbel_gebruiken=True)[0], 150)

    def test_geen_roem(self):
        self.assertEqual(beste_roem(hand("H:A,V", "S:7,9", "R:A,10", "K:H,8"))[0], 0)

    def test_volgorde_enkele_roem(self):
        vier_vrouwen = hand("S:V", "H:V", "R:V", "K:V", "S:7", "H:8", "R:9", "K:A")
        vijf_reeks = hand("H:A,H,V,B,10", "S:7", "R:8", "K:6")
        # vier vrouwen en 5-reeks zijn allebei 100, vier gelijke gaat voor
        self.assertTrue(kan_ontkennen(hoogste_enkele_roem(vijf_reeks), vier_vrouwen))
        self.assertFalse(kan_ontkennen(hoogste_enkele_roem(vier_vrouwen), vijf_reeks))

    def test_zelfde_reeks_hogere_kaart_of_kleur_wint(self):
        laag = hand("H:9,10,B", "S:7", "R:8", "K:A", "K:H")
        hoog = hand("H:V,B,10", "S:7", "R:8", "K:A", "K:H")
        self.assertTrue(kan_ontkennen(hoogste_enkele_roem(laag), hoog))
        # zelfde hoogste kaart: schoppen wint van harten
        schoppen = hand("S:V,B,10", "H:7", "R:8", "K:A", "K:H")
        harten = hand("H:V,B,10", "S:7", "R:8", "K:A", "K:H")
        self.assertTrue(kan_ontkennen(hoogste_enkele_roem(harten), schoppen))
        self.assertFalse(kan_ontkennen(hoogste_enkele_roem(schoppen), harten))

    def test_niets_te_ontkennen(self):
        self.assertFalse(kan_ontkennen(None, hand("H:V,B,10")))

    def test_stuk_mag_kaarten_delen_met_andere_roem(self):
        # troef harten: vrouw zit in vier vrouwen (100) en in stuk (20)
        h = hand("H:H,V", "S:V", "R:V", "K:V", "S:7", "R:8")
        self.assertEqual(beste_roem(h)[0], 100)
        self.assertEqual(roem_totaal(h, H), 120)
        # zonder stuk-troef geen extra punten
        self.assertEqual(roem_totaal(h, S), 100)

    def test_vrouw_niet_in_vier_vrouwen_en_driekaart(self):
        # vier vrouwen + boer-vrouw-heer in harten: niet allebei
        h = hand("H:B,V,H", "S:V", "R:V", "K:V", "S:7")
        punten, _ = beste_roem(h)
        self.assertEqual(punten, 100)  # vier vrouwen (en boer/heer blijven los)

    def test_stuk(self):
        self.assertTrue(heeft_stuk(hand("H:H,V", "S:7"), H))
        self.assertFalse(heeft_stuk(hand("H:H", "S:V"), H))
        self.assertFalse(heeft_stuk(hand("H:H,V"), None))


class TestVariant(unittest.TestCase):
    """Biedvolgorde en tarief volgens Butselaar (1958), hoofdstuk 1."""

    def test_biedvolgorde(self):
        v = MIDDEN_NEDERLAND
        rang = v.bod_rang
        self.assertLess(rang(Bod("punten", 130)), rang(Bod("punten", 150)))
        self.assertLess(rang(Bod("punten", 150)), rang(Bod("piccolo")))
        self.assertLess(rang(Bod("piccolo")), rang(Bod("misere")))
        self.assertLess(rang(Bod("misere")), rang(Bod("punten", 160)))
        self.assertLess(rang(Bod("punten", 160)), rang(Bod("kereltje")))
        self.assertLess(rang(Bod("kereltje")), rang(Bod("zwabber")))
        self.assertLess(rang(Bod("zwabber")), rang(Bod("punten", 170)))
        self.assertLess(rang(Bod("punten", 190)), rang(Bod("solo_zwabber")))
        self.assertLess(rang(Bod("solo_zwabber")), rang(Bod("punten", 200)))
        self.assertLess(rang(Bod("punten", 200)), rang(Bod("piccolo_ouvert")))
        self.assertLess(rang(Bod("piccolo_ouvert")), rang(Bod("misere_ouvert")))
        self.assertLess(rang(Bod("misere_ouvert")), rang(Bod("stil_praatje")))
        self.assertLess(rang(Bod("stil_praatje")), rang(Bod("pandoer")))
        self.assertLess(rang(Bod("pandoer")), rang(Bod("piccolo_praatje")))
        self.assertLess(rang(Bod("piccolo_praatje")), rang(Bod("praatje")))
        self.assertLess(rang(Bod("praatje")), rang(Bod("pandoer_prive")))

    def test_is_hoger(self):
        v = MIDDEN_NEDERLAND
        self.assertTrue(v.is_hoger(Bod("punten", 140), None))
        self.assertTrue(v.is_hoger(Bod("misere"), Bod("punten", 150)))
        self.assertFalse(v.is_hoger(Bod("punten", 150), Bod("misere")))
        self.assertFalse(v.is_hoger(Bod("punten", 140), Bod("punten", 140)))

    def test_laagste_bod_is_130(self):
        with self.assertRaises(ValueError):
            MIDDEN_NEDERLAND.bod_rang(Bod("punten", 120))
        MIDDEN_NEDERLAND.bod_rang(Bod("punten", 130))  # mag wel

    def test_ongeldig_bod(self):
        with self.assertRaises(ValueError):
            MIDDEN_NEDERLAND.bod_rang(Bod("punten", 135))
        with self.assertRaises(ValueError):
            MIDDEN_NEDERLAND.bod_rang(Bod("punten", 120))

    def test_uitbetaling(self):
        u = MIDDEN_NEDERLAND.uitbetaling
        self.assertEqual([u(Bod("punten", d)) for d in (130, 150, 160, 170, 190, 200, 220)],
                         [1, 1, 2, 3, 3, 4, 4])
        self.assertEqual(u(Bod("misere")), 3)
        self.assertEqual(u(Bod("kereltje")), 2)
        self.assertEqual(u(Bod("zwabber")), 2)
        self.assertEqual(u(Bod("solo_zwabber")), 5)
        self.assertEqual(u(Bod("misere_ouvert")), 6)
        self.assertEqual(u(Bod("stil_praatje")), 8)
        self.assertEqual(u(Bod("pandoer")), 5)
        self.assertEqual(u(Bod("praatje")), 9)
        self.assertEqual(u(Bod("pandoer_prive")), 10)

    def test_open_vragen(self):
        namen = {naam for naam, _, _ in MIDDEN_NEDERLAND.open_vragen()}
        # de kern van de tabel is nu bevestigd (Butselaar), dit blijft open:
        self.assertIn("roem_melden", namen)
        self.assertIn("roem_ontkennen", namen)
        self.assertNotIn("uitbetalingen", namen)
        self.assertNotIn("husselen", namen)
        self.assertNotIn("laagste_bod", namen)
        self.assertNotIn("overtroeven_verplicht", namen)
        self.assertNotIn("kaarten_dubbel_in_roem", namen)


if __name__ == "__main__":
    unittest.main()
