import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from accounts.models import User
from .models import ChatSession, ChatMessage


@csrf_exempt
def api_get_history(request):
    """Retrieve all chat sessions and messages for the specified user email."""
    if request.method != "GET":
        return JsonResponse({"success": False, "detail": "Method not allowed"}, status=405)

    email = request.GET.get("email", "").lower().strip()
    if not email:
        return JsonResponse({"success": False, "detail": "Email parameter is required"}, status=400)

    user = User.objects.filter(email=email).first()
    if not user:
        return JsonResponse({"success": True, "sessions": []})

    sessions = ChatSession.objects.filter(user=user).order_by("-updated_at")
    session_data = []

    for s in sessions:
        msgs = s.messages.order_by("timestamp")
        session_data.append({
            "id": str(s.id),
            "title": s.title,
            "updated_at": s.updated_at.isoformat(),
            "created_at": s.created_at.isoformat(),
            "messages": [
                {
                    "id": str(m.id),
                    "role": m.role,
                    "content": m.content,
                    "sources": m.sources,
                    "timestamp": m.timestamp.isoformat(),
                }
                for m in msgs
            ],
        })

    return JsonResponse({"success": True, "sessions": session_data})


@csrf_exempt
def api_save_chat(request):
    """Save or update an entire chat session and its messages."""
    if request.method != "POST":
        return JsonResponse({"success": False, "detail": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"success": False, "detail": "Invalid JSON"}, status=400)

    email = data.get("email", "").lower().strip()
    if not email:
        return JsonResponse({"success": False, "detail": "User email is required"}, status=400)

    user = User.objects.filter(email=email).first()
    if not user:
        return JsonResponse({"success": False, "detail": "User not found"}, status=404)

    session_id = data.get("session_id")
    messages = data.get("messages", [])
    title = data.get("title")

    # Generate a descriptive title from first user message if not given
    if not title and messages:
        first_user_msg = next((m["content"] for m in messages if m.get("role") == "user"), None)
        if first_user_msg:
            title = (first_user_msg[:45] + "...") if len(first_user_msg) > 45 else first_user_msg
        else:
            title = "New Conversation"

    if session_id:
        try:
            session = ChatSession.objects.get(id=int(session_id), user=user)
            if title:
                session.title = title
            session.save()
        except (ChatSession.DoesNotExist, ValueError):
            session = ChatSession.objects.create(user=user, title=title or "New Conversation")
    else:
        session = ChatSession.objects.create(user=user, title=title or "New Conversation")

    # Re-sync messages for this session
    session.messages.all().delete()
    for m in messages:
        sources_json = json.dumps(m.get("sources") or [])
        ChatMessage.objects.create(
            session=session,
            role=m.get("role", "user"),
            content=m.get("content", ""),
            sources_json=sources_json,
        )

    return JsonResponse({
        "success": True,
        "session_id": str(session.id),
        "title": session.title,
    })


@csrf_exempt
def api_delete_session(request, session_id):
    """Delete a specific chat session."""
    if request.method != "DELETE" and request.method != "POST":
        return JsonResponse({"success": False, "detail": "Method not allowed"}, status=405)

    email = request.GET.get("email", "").lower().strip()
    user = User.objects.filter(email=email).first() if email else None

    try:
        if user:
            session = ChatSession.objects.get(id=int(session_id), user=user)
        else:
            session = ChatSession.objects.get(id=int(session_id))
        session.delete()
        return JsonResponse({"success": True, "message": "Session deleted"})
    except (ChatSession.DoesNotExist, ValueError):
        return JsonResponse({"success": False, "detail": "Session not found"}, status=404)


@csrf_exempt
def api_clear_history(request):
    """Clear all chat history for a given user."""
    if request.method != "DELETE" and request.method != "POST":
        return JsonResponse({"success": False, "detail": "Method not allowed"}, status=405)

    email = request.GET.get("email", "").lower().strip()
    user = User.objects.filter(email=email).first()
    if not user:
        return JsonResponse({"success": False, "detail": "User not found"}, status=404)

    ChatSession.objects.filter(user=user).delete()
    return JsonResponse({"success": True, "message": "Chat history cleared successfully"})
