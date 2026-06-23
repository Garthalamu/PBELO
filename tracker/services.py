from django.db import transaction

from .elo import process_game
from .models import RatingChange, Game, Player

_DEFAULT_MU = 25.0
_DEFAULT_SIGMA = 25.0 / 3


def recalculate_all_elos():
    """
    Rebuild every player's rating from scratch by replaying all games in order.
    Runs inside a single transaction so a failure leaves the DB unchanged.
    """
    with transaction.atomic():
        Player.objects.update(
            singles_mu=_DEFAULT_MU,
            singles_sigma=_DEFAULT_SIGMA,
            doubles_mu=_DEFAULT_MU,
            doubles_sigma=_DEFAULT_SIGMA,
        )
        RatingChange.objects.all().delete()

        games = Game.objects.order_by("played_at")
        for game in games:
            process_game(game)

        return games.count()
