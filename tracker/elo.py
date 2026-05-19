"""
ELO rating calculations for singles and doubles pickleball.

Singles: standard two-player ELO.
Doubles: each team's rating is the average of its two players' doubles ELO.
         All four players are updated based on that team-vs-team matchup.
"""

K = 32


def expected_score(rating_a: float, rating_b: float) -> float:
    """Probability that A beats B given their ratings."""
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))


def updated_ratings(rating_a: float, rating_b: float, a_won: bool) -> tuple[float, float]:
    """Return (new_rating_a, new_rating_b) after a head-to-head result."""
    exp_a = expected_score(rating_a, rating_b)
    score_a = 1.0 if a_won else 0.0
    score_b = 1.0 - score_a
    new_a = rating_a + K * (score_a - exp_a)
    new_b = rating_b + K * (score_b - (1 - exp_a))
    return new_a, new_b


def process_singles(game) -> list[dict]:
    """
    Calculate and apply ELO changes for a singles game.
    Returns a list of EloChange-ready dicts: {player, elo_before, elo_after}.
    """
    players1 = list(game.team1_players.all())
    players2 = list(game.team2_players.all())
    player1 = players1[0]
    player2 = players2[0]

    team1_won = game.winning_team == 1
    new1, new2 = updated_ratings(player1.singles_elo, player2.singles_elo, team1_won)

    changes = [
        {"player": player1, "elo_before": player1.singles_elo, "elo_after": new1},
        {"player": player2, "elo_before": player2.singles_elo, "elo_after": new2},
    ]

    player1.singles_elo = new1
    player2.singles_elo = new2
    player1.save(update_fields=["singles_elo"])
    player2.save(update_fields=["singles_elo"])

    return changes


def process_doubles(game) -> list[dict]:
    """
    Calculate and apply ELO changes for a doubles game.
    Team rating = average of the two players' doubles ELO.
    Each player is updated by the same delta their team earned.
    Returns a list of EloChange-ready dicts: {player, elo_before, elo_after}.
    """
    team1 = list(game.team1_players.all())
    team2 = list(game.team2_players.all())

    team1_rating = sum(p.doubles_elo for p in team1) / len(team1)
    team2_rating = sum(p.doubles_elo for p in team2) / len(team2)

    team1_won = game.winning_team == 1
    new_team1_rating, new_team2_rating = updated_ratings(team1_rating, team2_rating, team1_won)

    team1_delta = new_team1_rating - team1_rating
    team2_delta = new_team2_rating - team2_rating

    changes = []
    for player in team1:
        before = player.doubles_elo
        after = before + team1_delta
        changes.append({"player": player, "elo_before": before, "elo_after": after})
        player.doubles_elo = after
        player.save(update_fields=["doubles_elo"])

    for player in team2:
        before = player.doubles_elo
        after = before + team2_delta
        changes.append({"player": player, "elo_before": before, "elo_after": after})
        player.doubles_elo = after
        player.save(update_fields=["doubles_elo"])

    return changes


def process_game(game) -> None:
    """Apply ELO changes for a game and persist EloChange records."""
    from .models import EloChange

    if game.game_type == "singles":
        changes = process_singles(game)
    else:
        changes = process_doubles(game)

    EloChange.objects.bulk_create([
        EloChange(game=game, **change) for change in changes
    ])
