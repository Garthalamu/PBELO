"""
ELO rating calculations for singles and doubles pickleball.

Singles: standard two-player ELO with margin of victory scaling.
Doubles: each team's rating is the average of its two players' doubles ELO.
         All four players are updated based on that team-vs-team matchup.

Margin of victory multiplier: log2(|score_diff| + 1)
  - 1-point win  → ×1.0  (baseline, identical to plain ELO)
  - 2-point win  → ×1.58
  - 5-point win  → ×2.58
  - 11-point win → ×3.58
The same multiplier is applied to both sides, preserving zero-sum.
"""

import math

K = 26


def expected_score(rating_a: float, rating_b: float) -> float:
    """Probability that A beats B given their ratings."""
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))


def updated_ratings(
    rating_a: float,
    rating_b: float,
    score_a: int,
    score_b: int,
) -> tuple[float, float]:
    """Return (new_rating_a, new_rating_b) after a head-to-head result.

    score_a and score_b are the actual game scores; the winner is derived
    from them and the margin scales the K-factor logarithmically.
    """
    a_won = score_a > score_b
    mov = math.log2(abs(score_a - score_b) + 1)
    exp_a = expected_score(rating_a, rating_b)
    result_a = 1.0 if a_won else 0.0
    result_b = 1.0 - result_a
    new_a = rating_a + K * mov * (result_a - exp_a)
    new_b = rating_b + K * mov * (result_b - (1 - exp_a))
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

    new1, new2 = updated_ratings(
        player1.singles_elo, player2.singles_elo,
        game.team1_score, game.team2_score,
    )

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

    new_team1_rating, new_team2_rating = updated_ratings(
        team1_rating, team2_rating,
        game.team1_score, game.team2_score,
    )

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
