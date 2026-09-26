from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import User


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
            'is_active', 'date_joined',
        ]
        read_only_fields = ['id', 'date_joined']

    def get_organization_data(self, obj):
        """اطلاعات کامل سازمان کاربر"""
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


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=8)

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('رمز عبور فعلی اشتباه است')
        return value

    def save(self):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user


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

        # افزودن اطلاعات کامل کاربر به پاسخ
        data['user'] = UserSerializer(user).data

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

    