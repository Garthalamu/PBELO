from django import forms
from .models import Game, Location, Player


class RecordGameForm(forms.Form):
    game_type = forms.ChoiceField(
        choices=Game.GAME_TYPE_CHOICES,
        widget=forms.RadioSelect,
    )
    played_at = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    location = forms.ModelChoiceField(
        queryset=Location.objects.all(),
        empty_label="— Select location —",
    )
    team1_player1 = forms.ModelChoiceField(queryset=Player.objects.all(), label="Team 1 — Player 1")
    team1_player2 = forms.ModelChoiceField(queryset=Player.objects.all(), label="Team 1 — Player 2", required=False)
    team1_score = forms.IntegerField(min_value=0, label="Team 1 Score")

    team2_player1 = forms.ModelChoiceField(queryset=Player.objects.all(), label="Team 2 — Player 1")
    team2_player2 = forms.ModelChoiceField(queryset=Player.objects.all(), label="Team 2 — Player 2", required=False)
    team2_score = forms.IntegerField(min_value=0, label="Team 2 Score")

    def clean(self):
        data = super().clean()
        game_type = data.get("game_type")
        t1p1 = data.get("team1_player1")
        t1p2 = data.get("team1_player2")
        t2p1 = data.get("team2_player1")
        t2p2 = data.get("team2_player2")
        score1 = data.get("team1_score")
        score2 = data.get("team2_score")

        if game_type == Game.DOUBLES:
            if not t1p2:
                self.add_error("team1_player2", "Required for doubles.")
            if not t2p2:
                self.add_error("team2_player2", "Required for doubles.")

        players = [p for p in [t1p1, t1p2, t2p1, t2p2] if p is not None]
        if len(players) != len(set(players)):
            raise forms.ValidationError("Each player can only appear once per game.")

        if score1 is not None and score2 is not None and score1 == score2:
            raise forms.ValidationError("Scores cannot be tied — there must be a winner.")

        return data
