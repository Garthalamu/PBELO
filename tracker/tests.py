from django.test import TestCase
from openskill.models import PlackettLuce


class OpenSkillRatingTests(TestCase):
    def setUp(self):
        self.model = PlackettLuce()
        self.default_mu = 25.0
        self.default_sigma = 25.0 / 3

    def _rating(self, mu=None, sigma=None):
        return self.model.rating(
            mu=mu or self.default_mu,
            sigma=sigma or self.default_sigma,
        )

    def test_winner_gains_loser_loses(self):
        r1, r2 = self._rating(), self._rating()
        [[new_r1], [new_r2]] = self.model.rate([[r1], [r2]], scores=[11, 9])
        self.assertGreater(new_r1.mu, r1.mu)
        self.assertLess(new_r2.mu, r2.mu)

    def test_sigma_decreases_after_game(self):
        r1, r2 = self._rating(), self._rating()
        [[new_r1], [new_r2]] = self.model.rate([[r1], [r2]], scores=[11, 9])
        self.assertLess(new_r1.sigma, r1.sigma)
        self.assertLess(new_r2.sigma, r2.sigma)

    def test_score_order_determines_winner(self):
        # PlackettLuce uses scores for ordering only, not magnitude.
        # Swapping the scores should swap who gains and who loses.
        r1, r2 = self._rating(), self._rating()
        [[team1_wins], [team1_loses]] = self.model.rate([[r1], [r2]], scores=[11, 7])
        [[team2_win_r1], [team2_win_r2]] = self.model.rate([[r1], [r2]], scores=[7, 11])
        self.assertGreater(team1_wins.mu, r1.mu)
        self.assertGreater(team2_win_r2.mu, r2.mu)

    def test_upset_gives_larger_gain(self):
        underdog = self._rating(mu=20.0)
        favourite = self._rating(mu=30.0)
        [[new_underdog], _] = self.model.rate([[underdog], [favourite]], scores=[11, 9])
        [[new_favourite], _] = self.model.rate([[favourite], [underdog]], scores=[11, 9])
        self.assertGreater(new_underdog.mu - underdog.mu, new_favourite.mu - favourite.mu)

    def test_doubles_two_players_per_team(self):
        team1 = [self._rating(), self._rating()]
        team2 = [self._rating(), self._rating()]
        [new_team1, new_team2] = self.model.rate([team1, team2], scores=[11, 7])
        self.assertEqual(len(new_team1), 2)
        self.assertEqual(len(new_team2), 2)
        for r_new, r_old in zip(new_team1, team1):
            self.assertGreater(r_new.mu, r_old.mu)
        for r_new, r_old in zip(new_team2, team2):
            self.assertLess(r_new.mu, r_old.mu)
