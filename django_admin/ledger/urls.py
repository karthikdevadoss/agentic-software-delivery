from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("spend/", views.spend, name="spend"),
    path("budgets/", views.budgets, name="budgets"),
    path("evals/", views.evals, name="evals"),
]
