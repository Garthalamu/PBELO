import os
import re

from django.contrib import admin, messages
from django.contrib.auth.hashers import make_password
from django.shortcuts import redirect, render
from django.urls import path

from .models import EloChange, Game, Player
from .services import recalculate_all_elos

ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")


def _write_env_key(key, value):
    """Update or insert a KEY=VALUE line in the .env file."""
    try:
        with open(ENV_PATH, "r") as f:
            content = f.read()
    except FileNotFoundError:
        content = ""

    line = f'{key}="{value}"'
    pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
    if pattern.search(content):
        content = pattern.sub(line, content)
    else:
        content = content.rstrip("\n") + "\n" + line + "\n"

    with open(ENV_PATH, "w") as f:
        f.write(content)

    os.environ[key] = value


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ("__str__", "singles_elo", "doubles_elo", "created_at")
    search_fields = ("first_name", "last_name", "nickname")


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
            path("set-password/", self.admin_site.admin_view(self.set_password_view), name="set_site_password"),
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

    def set_password_view(self, request):
        if request.method == "POST":
            raw = request.POST.get("password", "").strip()
            confirm = request.POST.get("password_confirm", "").strip()
            if not raw:
                self.message_user(request, "Password cannot be empty.", messages.ERROR)
            elif raw != confirm:
                self.message_user(request, "Passwords do not match.", messages.ERROR)
            else:
                hashed = make_password(raw)
                _write_env_key("SITE_PASSWORD_HASH", hashed)
                self.message_user(request, "Site password updated successfully.", messages.SUCCESS)
                return redirect("admin:tracker_game_changelist")

        context = {
            **self.admin_site.each_context(request),
            "title": "Set Site Password",
        }
        return render(request, "admin/tracker/game/set_password.html", context)


@admin.register(EloChange)
class EloChangeAdmin(admin.ModelAdmin):
    list_display = ("player", "game", "elo_before", "elo_after", "delta")
    list_filter = ("game__game_type",)
