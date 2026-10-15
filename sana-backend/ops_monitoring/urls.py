from django.urls import path

from .views import GPSQueueView, LiveLogStreamView

app_name = 'ops_monitoring'

urlpatterns = [
    path('gps-monitor/logs/<str:stream_name>/', LiveLogStreamView.as_view(), name='gps-live-logs'),
    path('gps-monitor/queue/', GPSQueueView.as_view(), name='gps-queue'),
]
