from django.db import models
from django.utils import timezone


class Player(models.Model):
    first_name = models.CharField(max_length=50, blank=True)
    last_name = models.CharField(max_length=50, blank=True)
    nickname = models.CharField(max_length=50, blank=True)
    singles_elo = models.FloatField(default=1000.0)
    doubles_elo = models.FloatField(default=1000.0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["first_name", "last_name", "nickname"]

    @property
    def display_name(self):
        if self.nickname:
            return self.nickname
        return f"{self.first_name} {self.last_name}".strip()

    def __str__(self):
        return self.display_name


class Game(models.Model):
    SINGLES = "singles"
    DOUBLES = "doubles"
    GAME_TYPE_CHOICES = [(SINGLES, "Singles"), (DOUBLES, "Doubles")]

    game_type = models.CharField(max_length=10, choices=GAME_TYPE_CHOICES)
    played_at = models.DateTimeField(default=timezone.now)
    team1_players = models.ManyToManyField(Player, related_name="team1_games")
    team2_players = models.ManyToManyField(Player, related_name="team2_games")
    team1_score = models.PositiveSmallIntegerField()
    team2_score = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["-played_at"]

    def __str__(self):
        return f"{self.get_game_type_display()} on {self.played_at.date()}"

    @property
    def winning_team(self):
        if self.team1_score > self.team2_score:
            return 1
        if self.team2_score > self.team1_score:
            return 2
        return None


class EloChange(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="elo_changes")
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="elo_changes")
    elo_before = models.FloatField()
    elo_after = models.FloatField()

    class Meta:
        ordering = ["game__played_at"]

    def __str__(self):
        return f"{self.player} | {self.elo_before:.1f} → {self.elo_after:.1f}"

    @property
    def delta(self):
        return self.elo_after - self.elo_before
