from django.urls import path
from . import views


urlpatterns = [
    path('', views.mentor),
    path('stream/', views.stream),
    path('pending/', views.pending),
]
