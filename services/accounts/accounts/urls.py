from django.urls import path

from . import views

urlpatterns = [
    path("login", views.sign_in),
    path("register", views.register),
    path("recover", views.recover),
    path("resend", views.resend),
    path("verify/<str:raw>", views.verify),
    path("reset/<str:raw>", views.reset),
    path("logout", views.sign_out),
    path("complete", views.complete),
    path("health/live", views.health_live),
    path("health/ready", views.health_ready),
]
