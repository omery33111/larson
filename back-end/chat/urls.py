from django.urls import path
from . import views


urlpatterns = [
    path('conversations/', views.conversations),
    path('conversations/<int:conversation_id>/', views.conversation),
    path('conversations/<int:conversation_id>/stream/', views.stream),
    path('starred/', views.starred),
    path('messages/<int:message_id>/star/', views.star),
]
