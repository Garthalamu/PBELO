"""
Rating calculations — Phase 2 will replace this with OpenSkill logic.

The old ELO helpers are preserved below for reference until the rewrite lands.
process_game is stubbed; recording a new game will raise NotImplementedError
until Phase 2 is complete.
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
    """Return (new_rating_a, new_rating_b) after a head-to-head result."""
    a_won = score_a > score_b
    mov = math.log2(abs(score_a - score_b) + 1)
    exp_a = expected_score(rating_a, rating_b)
    result_a = 1.0 if a_won else 0.0
    result_b = 1.0 - result_a
    new_a = rating_a + K * mov * (result_a - exp_a)
    new_b = rating_b + K * mov * (result_b - (1 - exp_a))
    return new_a, new_b


def process_game(game) -> None:
    """Replaced in Phase 2 with OpenSkill logic."""
    raise NotImplementedError(
        "OpenSkill rating logic not yet implemented. Complete Phase 2 first."
    )
