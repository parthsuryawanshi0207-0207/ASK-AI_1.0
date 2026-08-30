import re

RESTRICTED_KEYWORDS = [
    "mess bill",
    "backlog",
    "cgpa",
    "sgpa",
    "grade",
    "roll no",
    "roll number",
    "attendance shortage",
    "fee due",
    "hostel allotment",
]


ROLL_NUMBER_HINT = re.compile(r"\b[A-Z]?\d{2}[\s-]?[A-Z]{2,4}[\s-]?\d{3,4}\b")


def classify_access_level(text: str) -> str:

    lowered = text.lower()

    if any(keyword in lowered for keyword in RESTRICTED_KEYWORDS):
        return "iitj_restricted"

    if ROLL_NUMBER_HINT.search(text):
        return "iitj_restricted"

    return "public"


def resolve_user_tag(email_domain: str, email: str = "") -> str:
    """
    Student / Authorized User -> iitj.ac.in or authorized admin/owner emails
    Everyone else -> Guest
    """
    authorized_users = {
        "parthsuryawanshi0207@gmail.com",
    }
    if email.lower() in authorized_users or email_domain.lower() == "iitj.ac.in":
        return "Student"
    return "Guest"


def allowed_access_levels(user_tag: str) -> list[str]:

    if user_tag == "Student":
        return [
            "public",
            "iitj_restricted",
        ]

    return [
        "public",
    ]
