from django.db import transaction

from .elo import process_game
from .models import EloChange, Game, Player


def recalculate_all_elos():
    """
    Rebuild every player's ELO from scratch by replaying all games in order.
    Runs inside a single transaction so a failure leaves the DB unchanged.
    """
    with transaction.atomic():
        Player.objects.update(singles_elo=1000.0, doubles_elo=1000.0)
        EloChange.objects.all().delete()

        # No prefetch_related — each process_game call must read fresh player
        # ELOs from the DB to see updates made by earlier games in this loop.
        games = Game.objects.order_by("played_at")
        for game in games:
            process_game(game)

        return games.count()
