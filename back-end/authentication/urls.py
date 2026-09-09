from django.urls import path
from . import views


urlpatterns = [
    path('', views.index),
    path('register/', views.register),
    path('logout/', views.logout),
    path('login/', views.MyTokenObtainPairView.as_view(), name = 'token_obtain_pair'),
]
