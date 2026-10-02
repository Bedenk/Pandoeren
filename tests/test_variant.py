import unittest

from pandoeren.spel import GEIMPLEMENTEERD
from pandoeren.variant import Bod, MIDDEN_NEDERLAND


class TestMogelijkeBoden(unittest.TestCase):
    def test_zonder_huidig_bod_is_laagste_punten_bod_de_eerste_kandidaat(self):
        kandidaten = MIDDEN_NEDERLAND.mogelijke_boden(GEIMPLEMENTEERD)
        self.assertEqual(kandidaten[0], Bod("punten", 130))
        # Elke kandidaat moet ook echt "hoger" zijn dan niets (d.w.z. een
        # geldig bod op zich), en in oplopende sterkte staan.
        rangen = [MIDDEN_NEDERLAND.bod_rang(b) for b in kandidaten]
        self.assertEqual(rangen, sorted(rangen))

    def test_alleen_hogere_boden_dan_het_huidige(self):
        huidig = Bod("punten", 140)
        kandidaten = MIDDEN_NEDERLAND.mogelijke_boden(GEIMPLEMENTEERD, huidig)
        for bod in kandidaten:
            self.assertTrue(MIDDEN_NEDERLAND.is_hoger(bod, huidig))
        # 130 en 140 zelf mogen niet meer in de lijst staan.
        self.assertNotIn(Bod("punten", 130), kandidaten)
        self.assertNotIn(Bod("punten", 140), kandidaten)
        self.assertIn(Bod("punten", 150), kandidaten)

    def test_na_een_hoog_bod_blijven_alleen_nog_hogere_spelen_over(self):
        huidig = Bod("praatje")
        kandidaten = MIDDEN_NEDERLAND.mogelijke_boden(GEIMPLEMENTEERD, huidig)
        # Alleen wat in Butselaar's lijst boven praatje staat (pandoer_prive,
        # en de piccolo/stil-praatje-varianten die er ooit nog bijkomen) kan
        # overblijven -- in elk geval geen enkel puntenspel meer.
        self.assertTrue(all(bod.soort != "punten" for bod in kandidaten))
        for bod in kandidaten:
            self.assertTrue(MIDDEN_NEDERLAND.is_hoger(bod, huidig))

    def test_pandoer_prive_is_het_hoogste_dus_geen_kandidaten_meer_erna(self):
        huidig = Bod("pandoer_prive")
        kandidaten = MIDDEN_NEDERLAND.mogelijke_boden(GEIMPLEMENTEERD, huidig)
        self.assertEqual(kandidaten, [])


if __name__ == "__main__":
    unittest.main()
