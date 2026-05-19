from django.test import TestCase
from .elo import expected_score, updated_ratings, K


class ExpectedScoreTests(TestCase):
    def test_equal_ratings_is_50_percent(self):
        self.assertAlmostEqual(expected_score(1000, 1000), 0.5)

    def test_higher_rated_favored(self):
        self.assertGreater(expected_score(1200, 1000), 0.5)

    def test_lower_rated_underdog(self):
        self.assertLess(expected_score(1000, 1200), 0.5)

    def test_symmetry(self):
        a = expected_score(1100, 900)
        b = expected_score(900, 1100)
        self.assertAlmostEqual(a + b, 1.0)


class UpdatedRatingsTests(TestCase):
    def test_winner_gains_loser_loses(self):
        new_a, new_b = updated_ratings(1000, 1000, a_won=True)
        self.assertGreater(new_a, 1000)
        self.assertLess(new_b, 1000)

    def test_ratings_are_zero_sum(self):
        new_a, new_b = updated_ratings(1000, 1200, a_won=True)
        self.assertAlmostEqual(new_a + new_b, 2200.0)

    def test_upset_gives_larger_gain(self):
        # Underdog wins — should gain more than a favourite winning
        new_underdog, _ = updated_ratings(1000, 1200, a_won=True)
        new_favourite, _ = updated_ratings(1200, 1000, a_won=True)
        underdog_gain = new_underdog - 1000
        favourite_gain = new_favourite - 1200
        self.assertGreater(underdog_gain, favourite_gain)

    def test_k_factor_caps_max_change(self):
        # Maximum possible gain is K (when expected score ~0)
        new_a, _ = updated_ratings(0, 10000, a_won=True)
        self.assertLessEqual(new_a - 0, K)
