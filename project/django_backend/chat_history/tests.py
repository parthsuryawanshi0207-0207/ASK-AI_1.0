from django.test import TestCase
from .models import ChatSession

class ChatHistoryTest(TestCase):
    def test_session_creation(self):
        session = ChatSession.objects.create()
        self.assertIsNotNone(session.id)
