from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils import timezone

from .elo import process_game
from .forms import RecordGameForm
from .models import Game


def home(request):
    return render(request, "tracker/home.html")


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
