from django.urls import path
from . import views


urlpatterns = [
    path('', views.overview),
    path('profile/', views.profile),
    path('profile/generate/', views.generate),
]
