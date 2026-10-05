from django.urls import path
from . import views


urlpatterns = [
    path('', views.mentor),
    path('stream/', views.stream),
    path('pending/', views.pending),

    path('rules/', views.rules),
    path('rules/save/', views.save_rule),
    path('rules/preview/', views.preview_rule),
    path('suggestion/accept/', views.accept_suggestion),
    path('suggestion/dismiss/', views.dismiss_suggestion),
    path('rules/<int:rule_id>/', views.delete_rule),
]
