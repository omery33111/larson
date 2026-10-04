from django.urls import path
from . import views


urlpatterns = [
    path('', views.index),
    path('register/', views.register),
    path('logout/', views.logout),
    path('login/', views.MyTokenObtainPairView.as_view(), name = 'token_obtain_pair'),
    path('login/google/', views.google_login),

    # Without this one, the refresh token issued at login was never exchanged for anything.
    path('refresh/', views.MyTokenRefreshView.as_view(), name = 'token_refresh'),

    path('verify/', views.verify_email),
    path('verify/resend/', views.resend_verification),

    path('password/change/', views.change_password),
    path('password/forgot/', views.forgot_password),
    path('password/reset/', views.reset_password),

    path('sessions/end/', views.end_sessions),

    path('export/', views.export_data),
    path('account/', views.delete_account),

    # ------------- EMAIL:
    path('email/preferences/', views.email_preferences),
    # Open on purpose - reached from a link in the mail, where there is no session.
    path('email/unsubscribe/', views.unsubscribe),
]
