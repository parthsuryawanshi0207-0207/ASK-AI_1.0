import json
from django.db import models
from django.conf import settings


class ChatSession(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_sessions",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=255, default="New Conversation")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        user_info = self.user.email if self.user else "Guest"
        return f"{self.title} ({user_info})"


class ChatMessage(models.Model):
    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(max_length=20)  # 'user' | 'assistant'
    content = models.TextField()
    sources_json = models.TextField(blank=True, default="[]")
    timestamp = models.DateTimeField(auto_now_add=True)

    @property
    def sources(self):
        try:
            return json.loads(self.sources_json)
        except Exception:
            return []

    @sources.setter
    def sources(self, value):
        self.sources_json = json.dumps(value or [])

    def __str__(self):
        return f"{self.role}: {self.content[:30]}..."
