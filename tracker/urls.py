from django.urls import path
from . import views

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("", views.home, name="home"),
    path("matches/", views.matches, name="matches"),
    path("record/", views.record_game, name="record_game"),
    path("players/create/", views.create_player, name="create_player"),
    path("matchup/", views.matchup_calculator, name="matchup_calculator"),
    path("matchup/predict/", views.predict_win_api, name="predict_win_api"),
    path("matchup/simulate/", views.simulate_outcome_api, name="simulate_outcome_api"),
    path("compare/", views.player_compare, name="player_compare"),
    path("compare/data/", views.compare_data_api, name="compare_data_api"),
    path("players/<int:player_id>/", views.player_detail, name="player_detail"),
    path("join/<str:token>/", views.token_login, name="token_login"),
]
