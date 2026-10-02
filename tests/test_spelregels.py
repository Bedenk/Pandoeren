import unittest
from dataclasses import replace

from pandoeren.cards import Card, Rank, Suit
from pandoeren.spelregels import legale_kaarten
from pandoeren.variant import MIDDEN_NEDERLAND
from tests.test_engine import hand

S, H, R, K = Suit.SCHOPPEN, Suit.HARTEN, Suit.RUITEN, Suit.KLAVEREN


def slag(*kaarten):
    """slag('S:A', 'H:7') -> [(0, ♠A), (1, ♥7)]"""
    return [(i, hand(k)[0]) for i, k in enumerate(kaarten)]


def legaal(h, gespeeld, troef, variant=MIDDEN_NEDERLAND):
    return set(legale_kaarten(h, gespeeld, troef, variant))


class TestZonderTroef(unittest.TestCase):
    def test_uitkomen_mag_alles(self):
        h = hand("S:A,7", "H:8")
        self.assertEqual(legaal(h, [], None), set(h))

    def test_bekennen(self):
        h = hand("S:A,7", "H:8")
        self.assertEqual(legaal(h, slag("S:10"), None), set(hand("S:A,7")))

    def test_niet_bekennen_alles(self):
        h = hand("H:8,9", "R:A")
        self.assertEqual(legaal(h, slag("S:10"), None), set(h))


class TestMetTroef(unittest.TestCase):
    troef = H

    def test_bekennen_of_troeven(self):
        h = hand("S:A,7", "H:8", "R:9")
        self.assertEqual(legaal(h, slag("S:10"), H), set(hand("S:A,7", "H:8")))

    def test_bekennen_alleen_als_troeven_bij_bekennen_uit_staat(self):
        v = replace(MIDDEN_NEDERLAND, troeven_bij_bekennen=False)
        h = hand("S:A,7", "H:8", "R:9")
        self.assertEqual(legaal(h, slag("S:10"), H, v), set(hand("S:A,7")))

    def test_bekennen_of_willekeurige_troef_niet_alleen_hogere(self):
        # harten 10 ligt al; Butselaar: troeven mag met elke troef, niet
        # alleen een hogere dan wat al ligt.
        h = hand("S:A", "H:7,B")
        self.assertEqual(legaal(h, slag("S:10", "H:10"), H), set(hand("S:A", "H:7,B")))

    def test_niet_bekennen_zonder_troef_op_tafel_alles(self):
        h = hand("H:8", "R:9", "K:A")
        self.assertEqual(legaal(h, slag("S:10"), H), set(h))

    def test_niet_bekennen_alles_mag_ook_lagere_troef(self):
        # kan gevraagde kleur niet bekennen: Butselaar, regel 7, mag alles
        h = hand("H:7,9", "R:9")
        self.assertEqual(legaal(h, slag("S:10", "H:10"), H), set(h))

    def test_troef_gevraagd_moet_troef(self):
        h = hand("H:7", "S:A", "R:9")
        self.assertEqual(legaal(h, slag("H:10"), H), set(hand("H:7")))

    def test_troef_gevraagd_overtroeven_niet_verplicht_standaard(self):
        # Butselaar: overtroeven is nooit verplicht, elke troef mag
        h = hand("H:7,A", "S:A")
        self.assertEqual(legaal(h, slag("H:10"), H), set(hand("H:7,A")))

    def test_troef_gevraagd_overtroeven_verplicht_als_variant_dat_vraagt(self):
        v = replace(MIDDEN_NEDERLAND, overtroeven_verplicht=True)
        h = hand("H:7,A", "S:A")
        self.assertEqual(legaal(h, slag("H:10"), H, v), set(hand("H:A")))

    def test_troef_gevraagd_overtroeven_verplicht_maar_geen_hogere_dan_mag_lager(self):
        v = replace(MIDDEN_NEDERLAND, overtroeven_verplicht=True)
        h = hand("H:7", "S:A")
        self.assertEqual(legaal(h, slag("H:9"), H, v), set(hand("H:7")))

    def test_troef_gevraagd_geen_troef_alles(self):
        h = hand("S:A", "R:9")
        self.assertEqual(legaal(h, slag("H:10"), H), set(h))


class TestJas(unittest.TestCase):
    def test_jas_hoeft_niet(self):
        # harten 9 gevraagd; jas is de enige hogere troef, maar hoeft niet
        h = hand("H:B,7,8", "S:A")
        self.assertEqual(legaal(h, slag("H:9"), H), set(hand("H:B,7,8")))

    def test_jas_verplicht_als_optie_uit(self):
        # ook overtroeven_verplicht=True nodig, anders mag toch elke troef
        v = replace(MIDDEN_NEDERLAND, jas_nooit_verplicht=False, overtroeven_verplicht=True)
        h = hand("H:B,7,8", "S:A")
        self.assertEqual(legaal(h, slag("H:9"), H, v), set(hand("H:B")))

    def test_jas_in_laatste_slag_wel_verplicht(self):
        self.assertEqual(legaal(hand("H:B"), slag("H:9"), H), set(hand("H:B")))


if __name__ == "__main__":
    unittest.main()
