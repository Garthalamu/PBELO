import hmac
import json
import os
from collections import Counter, defaultdict

from django.contrib.auth.hashers import check_password

import plotly.graph_objects as go
from django.contrib import messages
from django.db.models import Prefetch, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .elo import formatted_ordinal as rating_ordinal, process_game, DEFAULT_DISPLAY_RATING, DEFAULT_MU, predict_win as elo_predict_win, skill_range, gaussian_curve as elo_gaussian_curve, display_params as elo_display_params
from .forms import RecordGameForm, CreatePlayerForm
from .models import RatingChange, Game, Player


def _build_elo_chart(rating_changes):
    """Return a line chart figure JSON showing closing ordinal per day, or None if no data.

    rating_changes must be ordered by game__played_at ascending.
    """
    if not rating_changes:
        return None

    daily_close: dict = {}
    for rc in rating_changes:
        day = rc["game__played_at"].date()
        ordinal = rating_ordinal(rc["mu_after"], rc["sigma_after"])
        daily_close[day] = round(ordinal, 1)

    dates = list(daily_close.keys())
    closes = list(daily_close.values())

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates,
        y=closes,
        mode="lines+markers",
        line=dict(color="#0d6efd", width=2),
        marker=dict(size=7, color="#0d6efd"),
        hovertemplate="%{x|%b %d, %Y}<br>Rating: %{y}<extra></extra>",
    ))
    fig.add_hline(
        y=DEFAULT_DISPLAY_RATING,
        line=dict(color="#6c757d", width=1, dash="dot"),
        annotation_text=f"Start ({DEFAULT_DISPLAY_RATING})",
        annotation_position="bottom right",
    )
    fig.update_layout(
        margin=dict(l=50, r=20, t=20, b=50),
        paper_bgcolor="white",
        plot_bgcolor="white",
        yaxis=dict(title="Rating", gridcolor="#e9ecef", zeroline=False),
        xaxis=dict(title="Date", gridcolor="#e9ecef", type="date", tickformat="%b %d, %Y"),
        hovermode="closest",
        showlegend=False,
    )
    return json.loads(fig.to_json())


def _compute_best_chemistry():
    pair_stats = defaultdict(lambda: {'wins': 0, 'games': 0})
    for game in Game.objects.prefetch_related('team1_players', 'team2_players').filter(game_type=Game.DOUBLES):
        t1 = list(game.team1_players.all())
        t2 = list(game.team2_players.all())
        if len(t1) != 2 or len(t2) != 2:
            continue
        if game.winning_team not in (1, 2):
            continue
        winners = t1 if game.winning_team == 1 else t2
        losers  = t2 if game.winning_team == 1 else t1
        win_key  = frozenset(p.pk for p in winners)
        loss_key = frozenset(p.pk for p in losers)
        pair_stats[win_key]['wins']  += 1
        pair_stats[win_key]['games'] += 1
        pair_stats[loss_key]['games'] += 1
    qualified = {k: v for k, v in pair_stats.items() if v['wins'] / v['games'] >= 0.5}
    if not qualified:
        return frozenset()
    best_key = max(qualified, key=lambda k: (qualified[k]['wins'] + 3) / (qualified[k]['games'] + 6))
    return best_key


def login_view(request):
    if request.session.get("authenticated"):
        return redirect("home")
    error = None
    if request.method == "POST":
        entered = request.POST.get("password", "")
        hashed = os.environ.get("SITE_PASSWORD_HASH", "")
        plain = os.environ.get("SITE_PASSWORD", "pBallers")
        if hashed:
            valid = check_password(entered, hashed)
        else:
            valid = bool(plain) and hmac.compare_digest(entered, plain)
        if valid:
            request.session["authenticated"] = True
            return redirect(request.GET.get("next") or "home")
        error = "Incorrect password."
    return render(request, "tracker/login.html", {"error": error})


def logout_view(request):
    request.session.flush()
    return redirect("login")


def token_login(request, token):
    share_token = os.environ.get("SHARE_TOKEN", "")
    if share_token and hmac.compare_digest(token, share_token):
        request.session["authenticated"] = True
        return redirect("home")
    return redirect("login")


def home(request):
    changes_qs = RatingChange.objects.select_related("game").order_by("game__played_at")
    players = list(Player.objects.prefetch_related(
        Prefetch("rating_changes", queryset=changes_qs)
    ))

    for player in players:
        all_changes = list(player.rating_changes.all())
        singles = [c for c in all_changes if c.game.game_type == Game.SINGLES]
        doubles = [c for c in all_changes if c.game.game_type == Game.DOUBLES]

        player.singles_games_count = len(singles)
        player.doubles_games_count = len(doubles)
        player.singles_wins = sum(1 for c in singles if c.delta > 0)
        player.doubles_wins = sum(1 for c in doubles if c.delta > 0)

        player.singles_streak = 0
        for c in reversed(singles):
            if c.delta > 0: player.singles_streak += 1
            else: break

        player.doubles_streak = 0
        for c in reversed(doubles):
            if c.delta > 0: player.doubles_streak += 1
            else: break

    singles_board = sorted(
        [p for p in players if p.singles_games_count > 0],
        key=lambda p: p.singles_ordinal, reverse=True,
    )
    doubles_board = sorted(
        [p for p in players if p.doubles_games_count > 0],
        key=lambda p: p.doubles_ordinal, reverse=True,
    )

    for i, p in enumerate(singles_board):
        p.singles_ordinal_gap = None if i == 0 else round(singles_board[i - 1].singles_ordinal - p.singles_ordinal, 1)
    for i, p in enumerate(doubles_board):
        p.doubles_ordinal_gap = None if i == 0 else round(doubles_board[i - 1].doubles_ordinal - p.doubles_ordinal, 1)

    chemistry_pks = _compute_best_chemistry()
    for p in players:
        p.has_chemistry = p.pk in chemistry_pks

    return render(request, "tracker/home.html", {
        "singles_board": singles_board,
        "doubles_board": doubles_board,
    })



def record_game(request):
    if request.method == "POST":
        form = RecordGameForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            played_at = timezone.make_aware(
                timezone.datetime.combine(data["played_at"], timezone.datetime.min.time())
            )
            game = Game.objects.create(
                game_type=data["game_type"],
                played_at=played_at,
                team1_score=data["team1_score"],
                team2_score=data["team2_score"],
            )
            team1 = [data["team1_player1"]]
            team2 = [data["team2_player1"]]
            if data["game_type"] == "doubles":
                team1.append(data["team1_player2"])
                team2.append(data["team2_player2"])

            game.team1_players.set(team1)
            game.team2_players.set(team2)

            process_game(game)

            messages.success(request, "Game recorded and ratings updated.")
            if request.POST.get("_addanother"):
                return redirect("record_game")
            return redirect("home")
    else:
        form = RecordGameForm(initial={"played_at": timezone.now().date()})

    players_json = json.dumps([
        {"id": p.pk, "display_name": p.display_name}
        for p in Player.objects.order_by("first_name", "last_name", "nickname")
    ])
    return render(request, "tracker/record_game.html", {"form": form, "players_json": players_json})


def create_player(request):
    if request.method == "POST":
        form = CreatePlayerForm(request.POST)
        if form.is_valid():
            player = form.save()
            return redirect("player_detail", player_id=player.pk)
    else:
        form = CreatePlayerForm()
    return render(request, "tracker/create_player.html", {"form": form})


def matches(request):
    games = (
        Game.objects.prefetch_related(
            "team1_players",
            "team2_players",
            Prefetch("rating_changes", queryset=RatingChange.objects.only("player_id", "mu_before", "sigma_before", "mu_after", "sigma_after")),
        )
        .order_by("-played_at", "-id")
    )

    game_rows = []
    for game in games:
        t1 = list(game.team1_players.all())
        t2 = list(game.team2_players.all())
        elo_map = {rc.player_id: rc.delta for rc in game.rating_changes.all()}
        game_rows.append({
            "game": game,
            "team1": [(p, round(elo_map[p.pk]) if p.pk in elo_map else None) for p in t1],
            "team2": [(p, round(elo_map[p.pk]) if p.pk in elo_map else None) for p in t2],
        })

    return render(request, "tracker/matches.html", {"matches": game_rows})


def matchup_calculator(request):
    players = [
        {"id": p.pk, "display_name": p.display_name, "singles_ordinal": p.singles_ordinal, "doubles_ordinal": p.doubles_ordinal}
        for p in Player.objects.order_by("first_name", "last_name", "nickname")
    ]
    return render(request, "tracker/matchup_calculator.html", {
        "players_json": json.dumps(players),
    })


def predict_win_api(request):
    if not request.session.get("authenticated"):
        return JsonResponse({"error": "Not authenticated"}, status=401)

    t1_param = request.GET.get("t1", "")
    t2_param = request.GET.get("t2", "")
    game_type = request.GET.get("type", "singles")

    try:
        t1_ids = [int(x) for x in t1_param.split(",") if x.strip()]
        t2_ids = [int(x) for x in t2_param.split(",") if x.strip()]
    except ValueError:
        return JsonResponse({"error": "Invalid player IDs"}, status=400)

    if not t1_ids or not t2_ids:
        return JsonResponse({"error": "Teams must have at least one player"}, status=400)

    players = {p.pk: p for p in Player.objects.filter(pk__in=t1_ids + t2_ids)}
    if len(players) < len(set(t1_ids + t2_ids)):
        return JsonResponse({"error": "One or more players not found"}, status=404)

    mu_field = "doubles_mu" if game_type == "doubles" else "singles_mu"
    sigma_field = "doubles_sigma" if game_type == "doubles" else "singles_sigma"

    team1 = [(getattr(players[pid], mu_field), getattr(players[pid], sigma_field)) for pid in t1_ids]
    team2 = [(getattr(players[pid], mu_field), getattr(players[pid], sigma_field)) for pid in t2_ids]

    p1, p2 = elo_predict_win(team1, team2)
    return JsonResponse({"t1": p1, "t2": p2})


def player_compare(request):
    players = Player.objects.order_by("first_name", "last_name", "nickname")
    players_json = json.dumps([{"id": p.pk, "display_name": p.display_name} for p in players])
    return render(request, "tracker/player_compare.html", {"players_json": players_json})


def compare_data_api(request):
    if not request.session.get("authenticated"):
        return JsonResponse({"error": "Not authenticated"}, status=401)
    try:
        p1_id = int(request.GET.get("p1", ""))
        p2_id = int(request.GET.get("p2", ""))
    except (ValueError, TypeError):
        return JsonResponse({"error": "p1 and p2 required"}, status=400)

    game_type = request.GET.get("type", "singles")
    try:
        p1 = Player.objects.get(pk=p1_id)
        p2 = Player.objects.get(pk=p2_id)
    except Player.DoesNotExist:
        return JsonResponse({"error": "Player not found"}, status=404)

    if game_type == "doubles":
        mu1, sigma1 = p1.doubles_mu, p1.doubles_sigma
        mu2, sigma2 = p2.doubles_mu, p2.doubles_sigma
    else:
        mu1, sigma1 = p1.singles_mu, p1.singles_sigma
        mu2, sigma2 = p2.singles_mu, p2.singles_sigma

    x1, y1 = elo_gaussian_curve(mu1, sigma1)
    x2, y2 = elo_gaussian_curve(mu2, sigma2)

    def _short(p):
        if p.nickname:
            return p.nickname
        if p.first_name and p.last_name:
            return f"{p.first_name} {p.last_name[0]}."
        return p.display_name

    d_mu1, d_sigma1 = elo_display_params(mu1, sigma1)
    d_mu2, d_sigma2 = elo_display_params(mu2, sigma2)

    return JsonResponse({
        "p1": {
            "name": p1.display_name,
            "short_name": _short(p1),
            "curve": {"x": [round(v, 2) for v in x1], "y": [round(v, 6) for v in y1]},
            "rating": round(rating_ordinal(mu1, sigma1)),
            "mu": round(d_mu1),
            "sigma": round(d_sigma1),
        },
        "p2": {
            "name": p2.display_name,
            "short_name": _short(p2),
            "curve": {"x": [round(v, 2) for v in x2], "y": [round(v, 6) for v in y2]},
            "rating": round(rating_ordinal(mu2, sigma2)),
            "mu": round(d_mu2),
            "sigma": round(d_sigma2),
        },
    })


def player_detail(request, player_id):
    player = get_object_or_404(Player, pk=player_id)

    games = (
        Game.objects.filter(Q(team1_players=player) | Q(team2_players=player))
        .distinct()
        .prefetch_related("team1_players", "team2_players", "rating_changes")
        .order_by("-played_at", "-id")
    )

    elo_changes_by_game = {
        rc.game_id: rc for rc in player.rating_changes.all()
    }

    singles_wins = singles_losses = doubles_wins = doubles_losses = 0
    game_rows = []
    for game in games:
        in_team1 = player in game.team1_players.all()
        won = (in_team1 and game.winning_team == 1) or (not in_team1 and game.winning_team == 2)
        opponents = game.team2_players.all() if in_team1 else game.team1_players.all()
        teammates = (game.team1_players.all() if in_team1 else game.team2_players.all()).exclude(pk=player.pk)

        if game.game_type == Game.SINGLES:
            if won:
                singles_wins += 1
            else:
                singles_losses += 1
        else:
            if won:
                doubles_wins += 1
            else:
                doubles_losses += 1

        if in_team1:
            player_score, opp_score = game.team1_score, game.team2_score
        else:
            player_score, opp_score = game.team2_score, game.team1_score

        rating_change = elo_changes_by_game.get(game.pk)

        game_rows.append({
            "game": game,
            "won": won,
            "opponents": list(opponents),
            "teammates": list(teammates),
            "player_score": player_score,
            "opp_score": opp_score,
            "rating_delta": rating_change.delta if rating_change else None,
        })

    singles_ranked = sorted(
        Player.objects.filter(rating_changes__game__game_type=Game.SINGLES).distinct(),
        key=lambda p: p.singles_ordinal,
        reverse=True,
    )
    doubles_ranked = sorted(
        Player.objects.filter(rating_changes__game__game_type=Game.DOUBLES).distinct(),
        key=lambda p: p.doubles_ordinal,
        reverse=True,
    )
    singles_rank = next((i + 1 for i, p in enumerate(singles_ranked) if p.pk == player.pk), None)
    doubles_rank = next((i + 1 for i, p in enumerate(doubles_ranked) if p.pk == player.pk), None)

    rating_history = list(
        player.rating_changes.select_related("game")
        .order_by("game__played_at", "game__id")
        .values("mu_after", "sigma_after", "game__played_at", "game__game_type")
    )

    singles_history = [e for e in rating_history if e["game__game_type"] == Game.SINGLES]
    doubles_history = [e for e in rating_history if e["game__game_type"] == Game.DOUBLES]
    first_game_date = rating_history[0]["game__played_at"].date() if rating_history else None

    singles_chart = _build_elo_chart(singles_history)
    doubles_chart = _build_elo_chart(doubles_history)

    def _game_entry(e):
        center, upper, lower = skill_range(e["mu_after"], e["sigma_after"])
        return {
            "rating": round(rating_ordinal(e["mu_after"], e["sigma_after"]), 1),
            "center": round(center, 1),
            "upper": round(upper, 1),
            "lower": round(lower, 1),
            "date": e["game__played_at"].strftime("%Y-%m-%d"),
        }

    singles_games_json = json.dumps([_game_entry(e) for e in singles_history])
    doubles_games_json = json.dumps([_game_entry(e) for e in doubles_history])

    singles_rows = [r for r in game_rows if r["game"].game_type == Game.SINGLES]
    doubles_rows = [r for r in game_rows if r["game"].game_type == Game.DOUBLES]

    singles_streak = 0
    for row in singles_rows:
        if row["won"]: singles_streak += 1
        else: break

    doubles_streak = 0
    for row in doubles_rows:
        if row["won"]: doubles_streak += 1
        else: break

    singles_peak_ordinal = round(max((rating_ordinal(e["mu_after"], e["sigma_after"]) for e in singles_history), default=player.singles_ordinal), 1)
    doubles_peak_ordinal = round(max((rating_ordinal(e["mu_after"], e["sigma_after"]) for e in doubles_history), default=player.doubles_ordinal), 1)

    def _best_streak(rows_newest_first):
        best = streak = 0
        for row in reversed(rows_newest_first):
            if row["won"]:
                streak += 1
                if streak > best:
                    best = streak
            else:
                streak = 0
        return best

    singles_best_streak = _best_streak(singles_rows)
    doubles_best_streak = _best_streak(doubles_rows)

    ranks = [r for r in [singles_rank, doubles_rank] if r is not None]
    best_rank = min(ranks) if ranks else None
    player_award = 'gold' if best_rank == 1 else 'silver' if best_rank == 2 else 'bronze' if best_rank == 3 else None

    singles_show_peak = singles_peak_ordinal != round(player.singles_ordinal, 1)
    doubles_show_peak = doubles_peak_ordinal != round(player.doubles_ordinal, 1)
    singles_show_best_streak = singles_best_streak >= 3 and singles_best_streak > singles_streak
    doubles_show_best_streak = doubles_best_streak >= 3 and doubles_best_streak > doubles_streak

    h2h_map = {}
    for row in game_rows:
        for opp in row["opponents"]:
            if opp not in h2h_map:
                h2h_map[opp] = {"sw": 0, "sl": 0, "dw": 0, "dl": 0}
            entry = h2h_map[opp]
            if row["game"].game_type == Game.SINGLES:
                if row["won"]: entry["sw"] += 1
                else:          entry["sl"] += 1
            else:
                if row["won"]: entry["dw"] += 1
                else:          entry["dl"] += 1

    h2h_rows = sorted([
        {
            "opponent": opp,
            "singles_wins": s["sw"], "singles_losses": s["sl"],
            "doubles_wins": s["dw"], "doubles_losses": s["dl"],
            "total": s["sw"] + s["sl"] + s["dw"] + s["dl"],
        }
        for opp, s in h2h_map.items()
    ], key=lambda x: (
        -(x["singles_wins"] + x["doubles_wins"]) / x["total"],
        x["opponent"].display_name,
    ))

    teammate_stats = {}
    nemesis_losses = Counter()
    for row in doubles_rows:
        for tm in row["teammates"]:
            if tm not in teammate_stats:
                teammate_stats[tm] = {'wins': 0, 'games': 0}
            teammate_stats[tm]['games'] += 1
            if row["won"]:
                teammate_stats[tm]['wins'] += 1
    for row in game_rows:
        if not row["won"]:
            for opp in row["opponents"]:
                nemesis_losses[opp] += 1

    if teammate_stats:
        best_teammate = max(teammate_stats, key=lambda tm: (teammate_stats[tm]['wins'] + 3) / (teammate_stats[tm]['games'] + 6))
        best_teammate_wins = teammate_stats[best_teammate]['wins']
        best_teammate_games = teammate_stats[best_teammate]['games']
        best_teammate_adj_pct = round((best_teammate_wins + 3) / (best_teammate_games + 6) * 100)
    else:
        best_teammate = best_teammate_wins = best_teammate_games = best_teammate_adj_pct = None

    nemesis, nemesis_loss_count = nemesis_losses.most_common(1)[0] if nemesis_losses else (None, 0)

    teammate_rows = sorted([
        {
            "teammate": tm,
            "wins": s["wins"],
            "losses": s["games"] - s["wins"],
            "games": s["games"],
            "win_pct": round(s["wins"] / s["games"] * 100),
            "adj_win_pct": round((s["wins"] + 3) / (s["games"] + 6) * 100),
        }
        for tm, s in teammate_stats.items()
    ], key=lambda x: (-x["adj_win_pct"], x["teammate"].display_name))

    chemistry_pks = _compute_best_chemistry()
    has_chemistry = player.pk in chemistry_pks
    has_streak = singles_streak >= 3 or doubles_streak >= 3
    if player_award is None and has_chemistry:
        player_award = 'chemistry'
    elif player_award is None and has_streak:
        player_award = 'streak'

    return render(request, "tracker/player_detail.html", {
        "best_teammate": best_teammate,
        "best_teammate_wins": best_teammate_wins,
        "best_teammate_games": best_teammate_games,
        "best_teammate_adj_pct": best_teammate_adj_pct,
        "nemesis": nemesis,
        "nemesis_loss_count": nemesis_loss_count,
        "player": player,
        "game_rows": game_rows,
        "singles_wins": singles_wins,
        "singles_losses": singles_losses,
        "doubles_wins": doubles_wins,
        "doubles_losses": doubles_losses,
        "singles_chart": json.dumps(singles_chart),
        "doubles_chart": json.dumps(doubles_chart),
        "singles_games_json": singles_games_json,
        "doubles_games_json": doubles_games_json,
        "singles_rank": singles_rank,
        "doubles_rank": doubles_rank,
        "first_game_date": first_game_date,
        "h2h_rows": h2h_rows,
        "teammate_rows": teammate_rows,
        "singles_streak": singles_streak,
        "doubles_streak": doubles_streak,
        "singles_peak_ordinal": singles_peak_ordinal,
        "doubles_peak_ordinal": doubles_peak_ordinal,
        "singles_best_streak": singles_best_streak,
        "doubles_best_streak": doubles_best_streak,
        "singles_show_peak": singles_show_peak,
        "doubles_show_peak": doubles_show_peak,
        "singles_show_best_streak": singles_show_best_streak,
        "doubles_show_best_streak": doubles_show_best_streak,
        "player_award": player_award,
        "has_chemistry": has_chemistry,
        "default_rating": DEFAULT_DISPLAY_RATING,
        "default_mu": DEFAULT_MU,
    })
