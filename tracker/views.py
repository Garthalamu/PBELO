import json

import plotly.graph_objects as go
from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .elo import process_game
from .forms import RecordGameForm
from .models import Game, Player


def _build_elo_chart(elo_changes):
    """Return Plotly candlestick figure JSON for ELO history, or None if no data.

    Each bar represents one calendar day:
      open  = ELO before the first game that day
      close = ELO after the last game that day
      high  = highest ELO value touched during the day
      low   = lowest  ELO value touched during the day
    Green when the day ended higher than it opened, red when lower.
    elo_changes must be ordered by game__played_at ascending.
    """
    if not elo_changes:
        return None

    # Group into per-day buckets preserving chronological order.
    # daily_values holds every ELO value touched: the opening value (elo_before
    # of the first game) plus every elo_after across all games that day.
    daily_open: dict = {}
    daily_close: dict = {}
    daily_values: dict = {}  # all ELO values seen that day, for true high/low

    for ec in elo_changes:
        day = ec["game__played_at"].date()
        if day not in daily_open:
            daily_open[day] = round(ec["elo_before"], 1)
            daily_values[day] = [round(ec["elo_before"], 1)]
        daily_close[day] = round(ec["elo_after"], 1)
        daily_values[day].append(round(ec["elo_after"], 1))

    dates = list(daily_open.keys())
    opens = [daily_open[d] for d in dates]
    closes = [daily_close[d] for d in dates]
    highs = [max(daily_values[d]) for d in dates]
    lows = [min(daily_values[d]) for d in dates]

    fig = go.Figure(data=[
        go.Scatter(
            x=dates,
            y=closes,
            mode="lines",
            line=dict(color="#495057", width=1.5, dash="dash"),
            hoverinfo="skip",
            name="Closing ELO",
        ),
        go.Candlestick(
        x=dates,
        open=opens,
        high=highs,
        low=lows,
        close=closes,
        increasing=dict(line=dict(color="#198754"), fillcolor="#198754"),
        decreasing=dict(line=dict(color="#dc3545"), fillcolor="#dc3545"),
        hovertext=[
            f"{d.strftime('%b %d, %Y')}<br>Open: {o}<br>High: {h}<br>Low: {l}<br>Close: {c}<br>Change: {c - o:+.1f}"
            for d, o, h, l, c in zip(dates, opens, highs, lows, closes)
        ],
        hoverinfo="text",
        name="Daily Range",
    )])

    fig.add_hline(
        y=1000,
        line=dict(color="#adb5bd", width=1, dash="dot"),
        annotation_text="Start (1000)",
        annotation_position="bottom right",
    )
    fig.update_layout(
        margin=dict(l=50, r=20, t=20, b=50),
        paper_bgcolor="white",
        plot_bgcolor="white",
        yaxis=dict(title="ELO", gridcolor="#e9ecef", zeroline=False),
        xaxis=dict(title="Date", gridcolor="#e9ecef", type="date", tickformat="%b %d, %Y", rangeslider=dict(visible=False)),
        hovermode="x",
    )
    return json.loads(fig.to_json())


def home(request):
    players = Player.objects.annotate(
        singles_games=Count("elo_changes", filter=Q(elo_changes__game__game_type="singles")),
        doubles_games=Count("elo_changes", filter=Q(elo_changes__game__game_type="doubles")),
    )
    singles_board = players.filter(singles_games__gt=0).order_by("-singles_elo")
    doubles_board = players.filter(doubles_games__gt=0).order_by("-doubles_elo")
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


def player_detail(request, player_id):
    player = get_object_or_404(Player, pk=player_id)

    games = (
        Game.objects.filter(Q(team1_players=player) | Q(team2_players=player))
        .distinct()
        .prefetch_related("team1_players", "team2_players", "elo_changes")
        .order_by("-played_at")
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

    elo_history = list(
        player.elo_changes.select_related("game")
        .order_by("game__played_at")
        .values("elo_before", "elo_after", "game__played_at", "game__game_type")
    )
    singles_chart = _build_elo_chart([e for e in elo_history if e["game__game_type"] == Game.SINGLES])
    doubles_chart = _build_elo_chart([e for e in elo_history if e["game__game_type"] == Game.DOUBLES])

    singles_rows = [r for r in game_rows if r["game"].game_type == Game.SINGLES]
    doubles_rows = [r for r in game_rows if r["game"].game_type == Game.DOUBLES]

    return render(request, "tracker/player_detail.html", {
        "player": player,
        "singles_rows": singles_rows,
        "doubles_rows": doubles_rows,
        "singles_wins": singles_wins,
        "singles_losses": singles_losses,
        "doubles_wins": doubles_wins,
        "doubles_losses": doubles_losses,
        "singles_chart": json.dumps(singles_chart),
        "doubles_chart": json.dumps(doubles_chart),
    })
