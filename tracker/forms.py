from django import forms
from .models import Game, Player


class CreatePlayerForm(forms.ModelForm):
    class Meta:
        model = Player
        fields = ["first_name", "last_name", "nickname"]
        labels = {
            "first_name": "First Name",
            "last_name": "Last Name",
            "nickname": "Nickname",
        }

    def clean(self):
        data = super().clean()
        first = data.get("first_name", "").strip()
        last  = data.get("last_name", "").strip()
        nick  = data.get("nickname", "").strip()

        if not first and not nick:
            raise forms.ValidationError("Provide at least a first name or nickname.")

        if nick and Player.objects.filter(nickname__iexact=nick).exists():
            raise forms.ValidationError(f'A player with the nickname "{nick}" already exists.')

        if first and Player.objects.filter(first_name__iexact=first, last_name__iexact=last).exists():
            name = f"{first} {last}".strip()
            raise forms.ValidationError(f'A player named "{name}" already exists.')

        return data


class RecordGameForm(forms.Form):
    game_type = forms.ChoiceField(
        choices=Game.GAME_TYPE_CHOICES,
        widget=forms.RadioSelect,
    )
    played_at = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
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
