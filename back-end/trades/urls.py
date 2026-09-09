from django.urls import path
from . import views


urlpatterns = [
    path('', views.trade_list),
    path('upload/', views.upload),
    path('confirm/', views.confirm),
    path('summary/', views.summary),
    path('resume/', views.resume),
]
