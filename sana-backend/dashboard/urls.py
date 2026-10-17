from django.urls import path

from .views import DashboardStatsView, SiteSettingsView

urlpatterns = [
    path('dashboard/stats/', DashboardStatsView.as_view(), name='dashboard-stats'),
    path('site-settings/', SiteSettingsView.as_view(), name='site-settings'),
]
