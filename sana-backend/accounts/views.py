from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import User
from .serializers import (
    UserSerializer,
    UserCreateSerializer,
    UserUpdateSerializer,
    ChangePasswordSerializer,
    CustomTokenObtainPairSerializer,
)
from .permissions import IsSiteAdminOrReadOnly


class CustomTokenObtainPairView(TokenObtainPairView):
    """لاگین با JWT — پاسخ شامل اطلاعات کاربر"""
    serializer_class = CustomTokenObtainPairSerializer


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.select_related('organization', 'branch').all()
    permission_classes = [IsAuthenticated, IsSiteAdminOrReadOnly]

    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        if self.action in ['update', 'partial_update']:
            return UserUpdateSerializer
        return UserSerializer

    def get_queryset(self):
        user = self.request.user

        # ادمین کل سایت همه رو می‌بینه
        if user.is_site_admin:
            qs = User.objects.all()
        # مدیر شرکت فقط کاربران سازمان خودش
        elif user.is_main_user and user.organization:
            qs = User.objects.filter(organization=user.organization)
        # مدیر شعبه فقط کاربران شعبه خودش
        elif user.is_branch_manager and user.branch:
            qs = User.objects.filter(branch=user.branch)
        # کاربر شخصی فقط خودش
        else:
            qs = User.objects.filter(id=user.id)

        # فیلترها
        role = self.request.query_params.get('role')
        if role:
            qs = qs.filter(role=role)

        account_type = self.request.query_params.get('account_type')
        if account_type:
            qs = qs.filter(account_type=account_type)

        organization = self.request.query_params.get('organization')
        if organization:
            qs = qs.filter(organization_id=organization)

        return qs.select_related('organization', 'branch')

    @action(detail=False, methods=['get'])
    def me(self, request):
        """اطلاعات کاربر جاری"""
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def change_password(self, request):
        """تغییر رمز عبور کاربر جاری"""
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response({'detail': 'رمز عبور با موفقیت تغییر کرد'})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)