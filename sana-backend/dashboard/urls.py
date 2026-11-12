from django.urls import path

from .views import DashboardStatsView, SiteSettingsView
from .admin_overview import AdminDashboardOverviewView

urlpatterns = [
    path('dashboard/stats/', DashboardStatsView.as_view(), name='dashboard-stats'),
    path('dashboard/admin-overview/', AdminDashboardOverviewView.as_view(), name='dashboard-admin-overview'),
    path('site-settings/', SiteSettingsView.as_view(), name='site-settings'),
]
