from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    VehicleTypeViewSet,
    VehicleViewSet,
    DeviceModelViewSet,
    DeviceViewSet,
    DriverViewSet,
    DeviceLifecycleEventViewSet,
)

router = DefaultRouter()
router.register(r'vehicle-types', VehicleTypeViewSet, basename='vehicle-type')
router.register(r'vehicles', VehicleViewSet, basename='vehicle')
router.register(r'device-models', DeviceModelViewSet, basename='device-model')
router.register(r'devices', DeviceViewSet, basename='device')
router.register(r'drivers', DriverViewSet, basename='driver')
router.register(r'device-lifecycle-events', DeviceLifecycleEventViewSet, basename='device-lifecycle-event')

urlpatterns = router.urls