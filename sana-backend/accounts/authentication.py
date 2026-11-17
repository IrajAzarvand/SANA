from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication

from .session_utils import get_session_for_token, touch_session


class ContractAwareJWTAuthentication(JWTAuthentication):
    """Validate account access and the server-side session on every API request."""

    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None

        user, validated_token = result
        if not user.can_login:
            raise AuthenticationFailed(
                'قرارداد یا دسترسی حساب شما فعال نیست. لطفاً با پشتیبانی سانا تماس بگیرید.'
            )

        session = get_session_for_token(validated_token, user=user)
        if session is None:
            raise AuthenticationFailed(
                'نشست ورود شما منقضی یا باطل شده است. لطفاً دوباره وارد شوید.'
            )

        touch_session(session)
        return user, validated_token
