"""
OpenSkill (Weng-Lin / Plackett-Luce) rating system for singles and doubles.

Singles: two single-player teams rated head-to-head.
Doubles: each team is rated as a two-player unit; each player's rating is
         updated individually while the team is treated as a group.

Margin of victory is handled via the scores= parameter — a larger gap
produces a proportionally larger rating shift, similar to the old log2 MOV.
"""

from openskill.models import PlackettLuce

_model = PlackettLuce()

# Default player (mu=25, sigma=25/3) has raw ordinal 0, which maps to 1200.
DEFAULT_DISPLAY_RATING = 1200


def ordinal(mu: float, sigma: float) -> float:
    """Raw OpenSkill ordinal — used internally for ranking comparisons."""
    return _model.rating(mu=mu, sigma=sigma).ordinal()


def formatted_ordinal(mu: float, sigma: float) -> int:
    """User-facing rating on a ~200–3000 scale, centred around 1200 for a default player."""
    raw = ((ordinal(mu, sigma) + 19.67) / 58.38) * 2800 + 256.59
    return round(max(200, min(3000, raw)))


def _r(mu: float, sigma: float):
    return _model.rating(mu=mu, sigma=sigma)


def process_singles(game) -> list[dict]:
    p1 = list(game.team1_players.all())[0]
    p2 = list(game.team2_players.all())[0]

    r1 = _r(p1.singles_mu, p1.singles_sigma)
    r2 = _r(p2.singles_mu, p2.singles_sigma)

    [[new_r1], [new_r2]] = _model.rate(
        [[r1], [r2]],
        scores=[game.team1_score, game.team2_score],
    )

    changes = [
        {"player": p1, "mu_before": r1.mu, "sigma_before": r1.sigma,
         "mu_after": new_r1.mu, "sigma_after": new_r1.sigma},
        {"player": p2, "mu_before": r2.mu, "sigma_before": r2.sigma,
         "mu_after": new_r2.mu, "sigma_after": new_r2.sigma},
    ]

    p1.singles_mu, p1.singles_sigma = new_r1.mu, new_r1.sigma
    p2.singles_mu, p2.singles_sigma = new_r2.mu, new_r2.sigma
    p1.save(update_fields=["singles_mu", "singles_sigma"])
    p2.save(update_fields=["singles_mu", "singles_sigma"])

    return changes


def process_doubles(game) -> list[dict]:
    team1 = list(game.team1_players.all())
    team2 = list(game.team2_players.all())

    ratings1 = [_r(p.doubles_mu, p.doubles_sigma) for p in team1]
    ratings2 = [_r(p.doubles_mu, p.doubles_sigma) for p in team2]

    [new_ratings1, new_ratings2] = _model.rate(
        [ratings1, ratings2],
        scores=[game.team1_score, game.team2_score],
    )

    changes = []
    for p, r_old, r_new in zip(team1, ratings1, new_ratings1):
        changes.append({
            "player": p,
            "mu_before": r_old.mu, "sigma_before": r_old.sigma,
            "mu_after": r_new.mu, "sigma_after": r_new.sigma,
        })
        p.doubles_mu, p.doubles_sigma = r_new.mu, r_new.sigma
        p.save(update_fields=["doubles_mu", "doubles_sigma"])

    for p, r_old, r_new in zip(team2, ratings2, new_ratings2):
        changes.append({
            "player": p,
            "mu_before": r_old.mu, "sigma_before": r_old.sigma,
            "mu_after": r_new.mu, "sigma_after": r_new.sigma,
        })
        p.doubles_mu, p.doubles_sigma = r_new.mu, r_new.sigma
        p.save(update_fields=["doubles_mu", "doubles_sigma"])

    return changes


def process_game(game) -> None:
    from .models import RatingChange

    if game.game_type == "singles":
        changes = process_singles(game)
    else:
        changes = process_doubles(game)

    RatingChange.objects.bulk_create([
        RatingChange(game=game, **change) for change in changes
    ])
