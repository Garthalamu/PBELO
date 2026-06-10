from django.urls import path
from . import views

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("", views.home, name="home"),
    path("matches/", views.matches, name="matches"),
    path("record/", views.record_game, name="record_game"),
    path("matchup/", views.matchup_calculator, name="matchup_calculator"),
    path("players/<int:player_id>/", views.player_detail, name="player_detail"),
]
