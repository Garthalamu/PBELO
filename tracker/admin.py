from django.contrib import admin, messages
from django.shortcuts import redirect, render
from django.urls import path

from .models import EloChange, Game, Player
from .services import recalculate_all_elos


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
    change_list_template = "admin/tracker/game/change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path("recalculate-elo/", self.admin_site.admin_view(self.recalculate_elo_view), name="recalculate_elo"),
        ]
        return custom + urls

    def recalculate_elo_view(self, request):
        if request.method == "POST":
            count = recalculate_all_elos()
            self.message_user(request, f"ELO recalculated across {count} game(s).", messages.SUCCESS)
            return redirect("admin:tracker_game_changelist")

        game_count = Game.objects.count()
        player_count = Player.objects.count()
        context = {
            **self.admin_site.each_context(request),
            "title": "Recalculate ELO Ratings",
            "game_count": game_count,
            "player_count": player_count,
        }
        return render(request, "admin/tracker/game/recalculate_confirm.html", context)


@admin.register(EloChange)
class EloChangeAdmin(admin.ModelAdmin):
    list_display = ("player", "game", "elo_before", "elo_after", "delta")
    list_filter = ("game__game_type",)
