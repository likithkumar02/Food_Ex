from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

User = get_user_model()


def login_role_user(request, user, role=None):
    """
    Store user in their role-specific session slot while preserving any
    other active role sessions (e.g. keeping Customer active when Delivery Partner logs in).
    """
    if role is None:
        role = getattr(user, "role", "customer")

    session = request.session
    session[f"_{role}_user_id"] = str(user.pk)
    session[f"_{role}_backend"] = getattr(
        user, "backend", "django.contrib.auth.backends.ModelBackend"
    )
    session[f"_{role}_hash"] = user.get_session_auth_hash()

    # Always keep standard Django _auth_user_id aligned with the latest login
    session["_auth_user_id"] = str(user.pk)
    session["_auth_user_backend"] = session[f"_{role}_backend"]
    session["_auth_user_hash"] = session[f"_{role}_hash"]

    # Cycle session key to avoid session fixation without clearing existing data
    session.cycle_key()
    session.modified = True


def logout_role_user(request, role):
    """
    Remove ONLY the specified role from session, keeping other role sessions active.
    """
    session = request.session
    session.pop(f"_{role}_user_id", None)
    session.pop(f"_{role}_backend", None)
    session.pop(f"_{role}_hash", None)

    # If the standard _auth_user_id was pointing to this role, reassign to another active role
    remaining_roles = ("customer", "delivery_partner", "restaurant_owner", "admin")
    found_replacement = False
    for other_role in remaining_roles:
        if other_role != role and session.get(f"_{other_role}_user_id"):
            session["_auth_user_id"] = session.get(f"_{other_role}_user_id")
            session["_auth_user_backend"] = session.get(
                f"_{other_role}_backend",
                "django.contrib.auth.backends.ModelBackend",
            )
            session["_auth_user_hash"] = session.get(f"_{other_role}_hash", "")
            found_replacement = True
            break

    if not found_replacement:
        session.pop("_auth_user_id", None)
        session.pop("_auth_user_backend", None)
        session.pop("_auth_user_hash", None)

    session.modified = True


def get_active_roles(request):
    """
    Return a list of roles currently active in this session.
    """
    session = getattr(request, "session", {})
    roles = []
    for role in ("customer", "delivery_partner", "restaurant_owner", "admin"):
        if session.get(f"_{role}_user_id"):
            roles.append(role)
    return roles

