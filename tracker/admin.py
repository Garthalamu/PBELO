from django.contrib import admin
from .models import EloChange, Game, Player


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ("name", "singles_elo", "doubles_elo", "created_at")
    search_fields = ("name",)


class EloChangeInline(admin.TabularInline):
    model = EloChange
    extra = 0
    readonly_fields = ("player", "elo_before", "elo_after", "delta")


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ("__str__", "game_type", "team1_score", "team2_score", "played_at")
    list_filter = ("game_type",)
    inlines = [EloChangeInline]


@admin.register(EloChange)
class EloChangeAdmin(admin.ModelAdmin):
    list_display = ("player", "game", "elo_before", "elo_after", "delta")
    list_filter = ("game__game_type",)
