from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication


class ContractAwareJWTAuthentication(JWTAuthentication):
    """Re-check customer access on every request, not only at login time."""

    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None

        user, validated_token = result
        if not user.can_login:
            raise AuthenticationFailed(
                'قرارداد یا دسترسی حساب شما فعال نیست. لطفاً با پشتیبانی سانا تماس بگیرید.'
            )

        return user, validated_token
