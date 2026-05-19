from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("matches/", views.matches, name="matches"),
    path("record/", views.record_game, name="record_game"),
    path("players/<int:player_id>/", views.player_detail, name="player_detail"),
]
