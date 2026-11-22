from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User, UserSession
from organizations.models import Organization
from .session_utils import ABSOLUTE_SESSION_LIFETIME, IDLE_TIMEOUT, touch_session


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True)

    # اطلاعات کامل سازمان
    organization_data = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'mobile',
            'first_name', 'last_name', 'full_name', 'national_id',
            'address',
            'account_type', 'role',
            'organization', 'organization_name', 'organization_data',
            'branch', 'branch_name',
            'is_active', 'archived_at', 'archived_by', 'date_joined',
        ]
        read_only_fields = ['id', 'date_joined', 'archived_at', 'archived_by']

    def get_organization_data(self, obj):
        """اطلاعات کامل سازمان را فقط به نقش‌های مجاز نمایش بده."""
        request = self.context.get('request')
        if request and getattr(request.user, 'is_branch_manager', False):
            return None
        if not obj.organization_id:
            return None
        org = obj.organization
        return {
            'id': org.id,
            'name': org.name,
            'code': org.code,
            'registration_number': org.registration_number,
            'economy_code': org.economy_code,
            'phone': org.phone,
            'email': org.email,
            'address': org.address,
            'website': org.website,
            'status': org.status,
        }

class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = [
            'username', 'password', 'email', 'mobile',
            'first_name', 'last_name', 'national_id',
            'account_type', 'role',
            'organization', 'branch',
        ]

    def validate(self, attrs):
        request = self.context.get('request')
        actor = getattr(request, 'user', None)
        if actor and actor.is_main_user:
            branch = attrs.get('branch')
            if not actor.organization_id:
                raise serializers.ValidationError('مدیر شرکت فاقد سازمان معتبر است.')
            if attrs.get('role') != 'branch_manager' or attrs.get('account_type') != 'organization':
                raise serializers.ValidationError('مدیر شرکت فقط می‌تواند مدیر شعبه برای سازمان خودش ایجاد کند.')
            if not branch or branch.organization_id != actor.organization_id:
                raise serializers.ValidationError({'branch': 'شعبه باید متعلق به سازمان خودتان باشد.'})
            attrs['organization'] = actor.organization
        organization = attrs.get('organization')
        branch = attrs.get('branch')
        role = attrs.get('role')
        account_type = attrs.get('account_type')
        expected_type = {
            'site_admin': 'admin',
            'main_user': 'organization',
            'branch_manager': 'organization',
            'personal_user': 'personal',
        }.get(role)
        if expected_type and account_type != expected_type:
            raise serializers.ValidationError({'account_type': 'نوع حساب با نقش انتخاب‌شده سازگار نیست.'})
        if branch and organization and branch.organization_id != organization.id:
            raise serializers.ValidationError({'branch': 'شعبه انتخاب‌شده متعلق به سازمان انتخاب‌شده نیست.'})
        if branch and not organization:
            attrs['organization'] = branch.organization
            organization = branch.organization
        if role == 'branch_manager' and (not organization or not branch):
            raise serializers.ValidationError({'branch': 'برای مدیر شعبه، انتخاب شرکت و شعبه الزامی است.'})
        if role == 'main_user' and not organization:
            raise serializers.ValidationError({'organization': 'برای مدیر شرکت، انتخاب شرکت الزامی است.'})
        if role == 'main_user' and branch:
            raise serializers.ValidationError({'branch': 'مدیر شرکت نباید به یک شعبه خاص متصل باشد.'})
        if role == 'main_user' and branch:
            raise serializers.ValidationError({'branch': 'مدیر شرکت نباید به یک شعبه خاص متصل باشد.'})
        if role in {'site_admin', 'personal_user'} and (organization or branch):
            raise serializers.ValidationError('ادمین سایت و کاربر شخصی نباید به شرکت یا شعبه سازمانی متصل باشند.')
        if self.instance and self.instance.archived_at and attrs.get('is_active') is True:
            raise serializers.ValidationError({'is_active': 'برای فعال‌سازی حساب بایگانی‌شده ابتدا آن را بازیابی کنید.'})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'email', 'mobile', 'first_name', 'last_name', 'national_id',
            'branch',
        ]

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get('request')
        actor = getattr(request, 'user', None)
        if actor and actor.is_main_user:
            fields['is_active'] = serializers.BooleanField(required=False)
        if actor and actor.is_site_admin:
            fields.update({
                'role': serializers.ChoiceField(choices=User.ROLE_CHOICES, required=False),
                'account_type': serializers.ChoiceField(choices=User.ACCOUNT_TYPE_CHOICES, required=False),
                'organization': serializers.PrimaryKeyRelatedField(
                    queryset=Organization.objects.all(),
                    required=False, allow_null=True,
                ),
                'is_active': serializers.BooleanField(required=False),
            })
        return fields

    def validate(self, attrs):
        request = self.context.get('request')
        actor = getattr(request, 'user', None)
        if actor and actor.is_main_user:
            if 'branch' in attrs:
                branch = attrs['branch']
                if branch and branch.organization_id != actor.organization_id:
                    raise serializers.ValidationError({'branch': 'شعبه باید متعلق به سازمان خودتان باشد.'})
                if branch is None:
                    raise serializers.ValidationError({'branch': 'مدیر شعبه باید به یک شعبه متصل باشد.'})
            if self.instance and self.instance.role != 'branch_manager':
                raise serializers.ValidationError('مدیر شرکت فقط می‌تواند حساب مدیران شعبه را مدیریت کند.')
        organization = attrs.get('organization', getattr(self.instance, 'organization', None))
        branch = attrs.get('branch', getattr(self.instance, 'branch', None))
        role = attrs.get('role', getattr(self.instance, 'role', None))
        account_type = attrs.get('account_type', getattr(self.instance, 'account_type', None))
        expected_type = {
            'site_admin': 'admin',
            'main_user': 'organization',
            'branch_manager': 'organization',
            'personal_user': 'personal',
        }.get(role)
        if expected_type and account_type != expected_type:
            raise serializers.ValidationError({'account_type': 'نوع حساب با نقش انتخاب‌شده سازگار نیست.'})
        if branch and organization and branch.organization_id != organization.id:
            raise serializers.ValidationError({'branch': 'شعبه انتخاب‌شده متعلق به سازمان انتخاب‌شده نیست.'})
        if branch and not organization:
            attrs['organization'] = branch.organization
            organization = branch.organization
        if role == 'branch_manager' and (not organization or not branch):
            raise serializers.ValidationError({'branch': 'برای مدیر شعبه، انتخاب شرکت و شعبه الزامی است.'})
        if role == 'main_user' and not organization:
            raise serializers.ValidationError({'organization': 'برای مدیر شرکت، انتخاب شرکت الزامی است.'})
        if role in {'site_admin', 'personal_user'} and (organization or branch):
            raise serializers.ValidationError('ادمین سایت و کاربر شخصی نباید به شرکت یا شعبه سازمانی متصل باشند.')
        return attrs


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    """Allow an authenticated user to update only their own profile fields."""

    class Meta:
        model = User
        fields = ['email', 'mobile', 'first_name', 'last_name']


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True, write_only=True, trim_whitespace=False)
    new_password = serializers.CharField(required=True, write_only=True, min_length=8, trim_whitespace=False)

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('رمز عبور فعلی اشتباه است')
        return value

    def validate_new_password(self, value):
        user = self.context['request'].user
        if user.check_password(value):
            raise serializers.ValidationError('رمز عبور جدید باید با رمز فعلی متفاوت باشد')
        validate_password(value, user=user)
        return value

    def save(self):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save(update_fields=['password'])
        # Password changes invalidate every browser/device session, including this one.
        UserSession.objects.filter(
            user=user,
            revoked_at__isnull=True,
        ).update(revoked_at=timezone.now())
        return user


class ContractAwareTokenRefreshSerializer(TokenRefreshSerializer):
    """Rotate refresh tokens atomically against the server-side session."""

    def validate(self, attrs):
        refresh = RefreshToken(attrs['refresh'])
        user_id = refresh.payload.get(api_settings.USER_ID_CLAIM)
        user = get_user_model().objects.filter(
            **{api_settings.USER_ID_FIELD: user_id}
        ).first()

        if user is None or not user.can_login:
            raise ValidationError({
                'detail': 'قرارداد یا دسترسی حساب شما فعال نیست. لطفاً با پشتیبانی سانا تماس بگیرید.'
            })

        # Serialize concurrent refreshes for one session. Without the row lock,
        # two tabs could both accept the same JTI and invalidate each other's
        # newly rotated token.
        invalid_session = False
        with transaction.atomic():
            session = UserSession.objects.select_for_update().filter(
                pk=refresh.payload.get('sid'),
                user=user,
                revoked_at__isnull=True,
            ).first()
            now = timezone.now()
            if session is None:
                invalid_session = True
            elif session.expires_at <= now or session.last_activity_at <= now - IDLE_TIMEOUT:
                session.revoked_at = now
                session.save(update_fields=['revoked_at'])
                invalid_session = True
            elif session.current_refresh_jti != refresh['jti']:
                invalid_session = True
            else:
                touch_session(session)
                data = super().validate(attrs)

                # Only the newest refresh token remains usable for this session.
                rotated_refresh = data.get('refresh')
                if rotated_refresh:
                    rotated = RefreshToken(rotated_refresh)
                    session.current_refresh_jti = rotated['jti']
                    session.save(update_fields=['current_refresh_jti'])

        if invalid_session:
            raise AuthenticationFailed(
                'نشست ورود شما منقضی یا باطل شده است. لطفاً دوباره وارد شوید.'
            )
        return data


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """افزودن اطلاعات کاربر به پاسخ لاگین"""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # افزودن claimهای اضافی
        token['role'] = user.role
        token['account_type'] = user.account_type
        token['full_name'] = user.full_name
        if user.organization_id:
            token['organization_id'] = user.organization_id
            token['organization_name'] = user.organization.name
        if user.branch_id:
            token['branch_id'] = user.branch_id
            token['branch_name'] = user.branch.name

        return token


    def validate(self, attrs):
        data = super().validate(attrs)

        user = self.user

        # چک کردن دسترسی کاربر
        if not user.is_site_admin:
            # چک ۱: سازمان غیرفعال
            if user.organization_id and user.organization.status != 'active':
                raise serializers.ValidationError({
                    'detail': 'حساب سازمانی شما غیرفعال شده است. لطفاً با پشتیبانی سانا تماس بگیرید.'
                })

            # چک ۲: قرارداد فعال
            if not user.has_active_subscription:
                raise serializers.ValidationError({
                    'detail': 'اشتراک شما فعال نیست. لطفاً با پشتیبانی سانا تماس بگیرید.'
                })

        # Create a server-side session only after all login checks succeed.
        request = self.context.get('request')
        now = timezone.now()
        session = UserSession.objects.create(
            user=user,
            created_at=now,
            last_activity_at=now,
            expires_at=now + ABSOLUTE_SESSION_LIFETIME,
            ip_address=(request.META.get('REMOTE_ADDR') if request else None),
            user_agent=(request.META.get('HTTP_USER_AGENT', '')[:512] if request else ''),
        )
        refresh = RefreshToken(data['refresh'])
        refresh['sid'] = str(session.pk)
        session.current_refresh_jti = refresh['jti']
        session.save(update_fields=['current_refresh_jti'])
        data['refresh'] = str(refresh)
        data['access'] = str(refresh.access_token)

        # افزودن اطلاعات کامل کاربر به پاسخ
        data['user'] = UserSerializer(user, context={'request': request}).data

        # افزودن اطلاعات اشتراک
        subscription = user.active_subscription
        if subscription:
            data['subscription'] = {
                'contract_number': subscription.contract_number,
                'start_date': subscription.start_date,
                'end_date': subscription.end_date,
                'days_until_expiry': subscription.days_until_expiry,
                'is_expiring_soon': subscription.is_expiring_soon,
            }

        return data

    