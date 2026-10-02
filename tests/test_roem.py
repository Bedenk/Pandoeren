import unittest

from pandoeren.cards import Suit
from pandoeren.roem import hand_roem_claims, stuk_claim, tafel_roem_claims
from tests.test_engine import hand

S, H, R, K = Suit.SCHOPPEN, Suit.HARTEN, Suit.RUITEN, Suit.KLAVEREN


class TestHandRoemClaims(unittest.TestCase):
    def test_reeks_in_hand_is_een_losse_claim(self):
        h = hand("S:8,9,10", "H:7,8,9,10,B")
        claims = hand_roem_claims(h)
        # Twee onafhankelijke reeksen (schoppen 8-9-10 en harten 7-8-9-10-B,
        # een 5-reeks) staan niet met elkaar in conflict (andere kleur,
        # andere kaarten), dus allebei worden ze als losse claim teruggegeven.
        self.assertEqual(len(claims), 2)
        self.assertEqual(sorted(c.punten for c in claims), [20, 100])

    def test_geen_roem_geeft_lege_lijst(self):
        h = hand("S:7", "H:8", "R:9", "K:10", "S:6", "H:B", "R:V", "K:H")
        self.assertEqual(hand_roem_claims(h), [])

    def test_stuk_claim_alleen_bij_heer_en_vrouw_troef(self):
        h = hand("S:H,V", "H:7,8")
        self.assertIsNotNone(stuk_claim(h, S))
        self.assertIsNone(stuk_claim(h, H))  # geen heer+vrouw harten in hand
        self.assertIsNone(stuk_claim(h, None))

    def test_stuk_claim_punten_en_kaarten(self):
        h = hand("S:H,V", "H:7")
        claim = stuk_claim(h, S)
        self.assertEqual(claim.punten, 20)
        self.assertEqual(claim.omschrijving, "stuk")
        self.assertEqual(len(claim.kaarten), 2)


class TestTafelRoemClaims(unittest.TestCase):
    def test_driekaart_op_tafel_uit_verschillende_handen(self):
        # Vier verschillende spelers spelen elk één schoppenkaart die
        # toevallig -- of expres, dat maakt de engine niet uit -- een reeks
        # van drie opeenvolgende kaarten bevat (8,9,10), plus een losse,
        # niet-aansluitende aas.
        slag = [
            (0, hand("S:8")[0]), (1, hand("S:9")[0]),
            (2, hand("S:10")[0]), (3, hand("S:A")[0]),
        ]
        claims = tafel_roem_claims(slag, troef=H)
        soorten = {c.omschrijving for c in claims}
        self.assertTrue(any(c.punten == 20 for c in claims))  # de 3-reeks 8-9-10
        self.assertFalse(any("stuk" in s for s in soorten))  # geen troef-heer/vrouw hier

    def test_stuk_op_tafel_van_twee_verschillende_spelers(self):
        # Precies het voorbeeld van de gebruiker: bieder speelt troefboer,
        # zijn maat gooit troefheer bij, een tegenstander moet troefvrouw
        # bijleggen -- heer en vrouw troef komen zo uit twee verschillende
        # handen in dezelfde slag terecht.
        slag = [
            (0, hand("S:B")[0]), (1, hand("S:H")[0]),
            (2, hand("S:V")[0]), (3, hand("S:9")[0]),
        ]
        claims = tafel_roem_claims(slag, troef=S)
        stuk = [c for c in claims if c.omschrijving.startswith("stuk")]
        self.assertEqual(len(stuk), 1)
        self.assertEqual(stuk[0].punten, 20)

    def test_gemengde_kleuren_tellen_niet_als_reeks(self):
        slag = [
            (0, hand("S:8")[0]), (1, hand("H:9")[0]),
            (2, hand("R:10")[0]), (3, hand("K:7")[0]),
        ]
        claims = tafel_roem_claims(slag, troef=None)
        self.assertEqual(claims, [])

    def test_vier_gelijke_kleuren_telt_niet_op_tafel(self):
        # Vier boeren, elk uit een andere kleur -- geen reeks (verschillende
        # kleuren) en geen stuk; per de gebruiker telt dit niet op tafel.
        slag = [
            (0, hand("S:B")[0]), (1, hand("H:B")[0]),
            (2, hand("R:B")[0]), (3, hand("K:B")[0]),
        ]
        claims = tafel_roem_claims(slag, troef=None)
        self.assertEqual(claims, [])

    def test_vierkaart_past_wel_maar_vijfkaart_kan_niet_op_tafel(self):
        slag = [
            (0, hand("S:7")[0]), (1, hand("S:8")[0]),
            (2, hand("S:9")[0]), (3, hand("S:10")[0]),
        ]
        claims = tafel_roem_claims(slag, troef=None)
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0].punten, 50)  # reeks4


if __name__ == "__main__":
    unittest.main()
