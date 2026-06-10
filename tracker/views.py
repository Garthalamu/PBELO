import hmac
import json
import os
from collections import Counter

from django.contrib.auth.hashers import check_password

import plotly.graph_objects as go
from django.contrib import messages
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .elo import process_game
from .forms import RecordGameForm
from .models import EloChange, Game, Player


def _build_elo_chart(elo_changes):
    """Return a line chart figure JSON showing closing ELO per day, or None if no data.

    elo_changes must be ordered by game__played_at ascending.
    """
    if not elo_changes:
        return None

    daily_close: dict = {}
    for ec in elo_changes:
        day = ec["game__played_at"].date()
        daily_close[day] = round(ec["elo_after"], 1)

    dates = list(daily_close.keys())
    closes = list(daily_close.values())

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates,
        y=closes,
        mode="lines+markers",
        line=dict(color="#0d6efd", width=2),
        marker=dict(size=7, color="#0d6efd"),
        hovertemplate="%{x|%b %d, %Y}<br>ELO: %{y}<extra></extra>",
    ))
    fig.add_hline(
        y=1000,
        line=dict(color="#6c757d", width=1, dash="dot"),
        annotation_text="Start (1000)",
        annotation_position="bottom right",
    )
    fig.update_layout(
        margin=dict(l=50, r=20, t=20, b=50),
        paper_bgcolor="white",
        plot_bgcolor="white",
        yaxis=dict(title="ELO", gridcolor="#e9ecef", zeroline=False),
        xaxis=dict(title="Date", gridcolor="#e9ecef", type="date", tickformat="%b %d, %Y"),
        hovermode="closest",
        showlegend=False,
    )
    return json.loads(fig.to_json())


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


def home(request):
    changes_qs = EloChange.objects.select_related("game").order_by("game__played_at")
    players = list(Player.objects.prefetch_related(
        Prefetch("elo_changes", queryset=changes_qs)
    ))

    for player in players:
        all_changes = list(player.elo_changes.all())
        singles = [c for c in all_changes if c.game.game_type == Game.SINGLES]
        doubles = [c for c in all_changes if c.game.game_type == Game.DOUBLES]

        player.singles_games_count = len(singles)
        player.doubles_games_count = len(doubles)
        player.singles_wins = sum(1 for c in singles if c.delta > 0)
        player.doubles_wins = sum(1 for c in doubles if c.delta > 0)

    singles_board = sorted(
        [p for p in players if p.singles_games_count > 0],
        key=lambda p: p.singles_elo, reverse=True,
    )
    doubles_board = sorted(
        [p for p in players if p.doubles_games_count > 0],
        key=lambda p: p.doubles_elo, reverse=True,
    )

    for i, p in enumerate(singles_board):
        p.singles_elo_gap = None if i == 0 else round(singles_board[i - 1].singles_elo - p.singles_elo, 1)
    for i, p in enumerate(doubles_board):
        p.doubles_elo_gap = None if i == 0 else round(doubles_board[i - 1].doubles_elo - p.doubles_elo, 1)

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
            return redirect("home")
    else:
        form = RecordGameForm(initial={"played_at": timezone.now().date()})

    return render(request, "tracker/record_game.html", {"form": form})


def matches(request):
    games = (
        Game.objects.prefetch_related("team1_players", "team2_players")
        .order_by("-played_at", "-id")
    )

    game_rows = []
    for game in games:
        t1 = list(game.team1_players.all())
        t2 = list(game.team2_players.all())
        game_rows.append({
            "game": game,
            "team1": t1,
            "team2": t2,
        })

    return render(request, "tracker/matches.html", {
        "matches": game_rows,
    })


def matchup_calculator(request):
    players = [
        {"id": p.pk, "display_name": p.display_name, "singles_elo": p.singles_elo, "doubles_elo": p.doubles_elo}
        for p in Player.objects.order_by("first_name", "last_name", "nickname")
    ]
    return render(request, "tracker/matchup_calculator.html", {
        "players_json": json.dumps(players),
    })


def player_detail(request, player_id):
    player = get_object_or_404(Player, pk=player_id)

    games = (
        Game.objects.filter(Q(team1_players=player) | Q(team2_players=player))
        .distinct()
        .prefetch_related("team1_players", "team2_players", "elo_changes")
        .order_by("-played_at", "-id")
    )

    elo_changes_by_game = {
        ec.game_id: ec for ec in player.elo_changes.all()
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

        elo_change = elo_changes_by_game.get(game.pk)

        game_rows.append({
            "game": game,
            "won": won,
            "opponents": list(opponents),
            "teammates": list(teammates),
            "player_score": player_score,
            "opp_score": opp_score,
            "elo_delta": elo_change.delta if elo_change else None,
        })

    singles_ranked = list(
        Player.objects.filter(elo_changes__game__game_type=Game.SINGLES)
        .distinct().order_by("-singles_elo")
    )
    doubles_ranked = list(
        Player.objects.filter(elo_changes__game__game_type=Game.DOUBLES)
        .distinct().order_by("-doubles_elo")
    )
    singles_rank = next((i + 1 for i, p in enumerate(singles_ranked) if p.pk == player.pk), None)
    doubles_rank = next((i + 1 for i, p in enumerate(doubles_ranked) if p.pk == player.pk), None)

    elo_history = list(
        player.elo_changes.select_related("game")
        .order_by("game__played_at", "game__id")
        .values("elo_after", "game__played_at", "game__game_type")
    )

    singles_history = [e for e in elo_history if e["game__game_type"] == Game.SINGLES]
    doubles_history = [e for e in elo_history if e["game__game_type"] == Game.DOUBLES]
    first_game_date = elo_history[0]["game__played_at"].date() if elo_history else None

    singles_chart = _build_elo_chart(singles_history)
    doubles_chart = _build_elo_chart(doubles_history)

    singles_games_json = json.dumps([
        {"elo": round(e["elo_after"], 1), "date": e["game__played_at"].strftime("%Y-%m-%d")}
        for e in singles_history
    ])
    doubles_games_json = json.dumps([
        {"elo": round(e["elo_after"], 1), "date": e["game__played_at"].strftime("%Y-%m-%d")}
        for e in doubles_history
    ])

    singles_rows = [r for r in game_rows if r["game"].game_type == Game.SINGLES]
    doubles_rows = [r for r in game_rows if r["game"].game_type == Game.DOUBLES]

    teammate_wins = Counter()
    nemesis_losses = Counter()
    for row in doubles_rows:
        if row["won"]:
            for tm in row["teammates"]:
                teammate_wins[tm] += 1
    for row in game_rows:
        if not row["won"]:
            for opp in row["opponents"]:
                nemesis_losses[opp] += 1
    best_teammate, best_teammate_wins = teammate_wins.most_common(1)[0] if teammate_wins else (None, 0)
    nemesis, nemesis_loss_count = nemesis_losses.most_common(1)[0] if nemesis_losses else (None, 0)

    return render(request, "tracker/player_detail.html", {
        "best_teammate": best_teammate,
        "best_teammate_wins": best_teammate_wins,
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
    })
