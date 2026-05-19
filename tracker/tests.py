from django.test import TestCase
from .elo import expected_score, updated_ratings, K
import math


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
        new_a, new_b = updated_ratings(1000, 1000, 11, 9)
        self.assertGreater(new_a, 1000)
        self.assertLess(new_b, 1000)

    def test_ratings_are_zero_sum(self):
        new_a, new_b = updated_ratings(1000, 1200, 11, 9)
        self.assertAlmostEqual(new_a + new_b, 2200.0)

    def test_upset_gives_larger_gain(self):
        new_underdog, _ = updated_ratings(1000, 1200, 11, 9)
        new_favourite, _ = updated_ratings(1200, 1000, 11, 9)
        self.assertGreater(new_underdog - 1000, new_favourite - 1200)

    def test_larger_margin_gives_larger_change(self):
        _, new_b_close = updated_ratings(1000, 1000, 11, 9)   # 2-point win
        _, new_b_wide = updated_ratings(1000, 1000, 11, 0)    # 11-point win
        self.assertGreater(1000 - new_b_wide, 1000 - new_b_close)

    def test_one_point_win_uses_baseline_k(self):
        # log2(1 + 1) == 1.0, so MOV multiplier is exactly 1 — identical to plain ELO.
        new_a, _ = updated_ratings(1000, 1000, 11, 10)
        expected_gain = K * 1.0 * (1.0 - 0.5)
        self.assertAlmostEqual(new_a - 1000, expected_gain)
