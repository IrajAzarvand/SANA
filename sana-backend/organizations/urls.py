from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    OrganizationViewSet,
    BranchViewSet,
    SubscriptionViewSet,
    SubscriptionDeviceViewSet,
    SubscriptionPaymentViewSet,
)

router = DefaultRouter()
router.register(r'organizations', OrganizationViewSet, basename='organization')
router.register(r'branches', BranchViewSet, basename='branch')
router.register(r'subscriptions', SubscriptionViewSet, basename='subscription')
router.register(r'subscription-devices', SubscriptionDeviceViewSet, basename='subscription-device')
router.register(r'subscription-payments', SubscriptionPaymentViewSet, basename='subscription-payment')

urlpatterns = router.urls