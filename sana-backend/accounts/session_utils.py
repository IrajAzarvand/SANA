from datetime import timedelta

from django.utils import timezone

from .models import UserSession


IDLE_TIMEOUT = timedelta(minutes=30)
ABSOLUTE_SESSION_LIFETIME = timedelta(hours=12)
ACTIVITY_WRITE_INTERVAL = timedelta(seconds=60)


def get_session_for_token(token, user=None):
    """Return a valid session or None; also revoke expired sessions."""
    session_id = token.payload.get('sid')
    if not session_id:
        return None

    query = UserSession.objects.filter(pk=session_id, revoked_at__isnull=True)
    if user is not None:
        query = query.filter(user=user)
    session = query.first()
    if session is None:
        return None

    now = timezone.now()
    if session.expires_at <= now or session.last_activity_at <= now - IDLE_TIMEOUT:
        UserSession.objects.filter(pk=session.pk, revoked_at__isnull=True).update(revoked_at=now)
        return None

    return session


def touch_session(session):
    """Persist activity at most once per minute to limit database writes."""
    now = timezone.now()
    if now - session.last_activity_at >= ACTIVITY_WRITE_INTERVAL:
        UserSession.objects.filter(
            pk=session.pk,
            revoked_at__isnull=True,
            last_activity_at=session.last_activity_at,
        ).update(last_activity_at=now)
        session.last_activity_at = now
