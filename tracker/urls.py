from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("record/", views.record_game, name="record_game"),
]
