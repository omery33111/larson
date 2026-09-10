from django.urls import path
from . import views


urlpatterns = [
    path('', views.index),
    path('register/', views.register),
    path('logout/', views.logout),
    path('login/', views.MyTokenObtainPairView.as_view(), name = 'token_obtain_pair'),

    # Without this one, the refresh token issued at login was never exchanged for anything.
    path('refresh/', views.MyTokenRefreshView.as_view(), name = 'token_refresh'),

    path('verify/', views.verify_email),
    path('verify/resend/', views.resend_verification),

    path('password/change/', views.change_password),
    path('password/forgot/', views.forgot_password),
    path('password/reset/', views.reset_password),

    path('export/', views.export_data),
    path('account/', views.delete_account),
]
