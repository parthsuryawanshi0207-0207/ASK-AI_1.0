from django.urls import path
from . import views

app_name = "chat_history"

urlpatterns = [
    path("api/history/", views.api_get_history, name="api_get_history"),
    path("api/save/", views.api_save_chat, name="api_save_chat"),
    path("api/session/<int:session_id>/", views.api_delete_session, name="api_delete_session"),
    path("api/clear/", views.api_clear_history, name="api_clear_history"),
]
