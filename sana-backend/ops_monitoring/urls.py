from django.urls import path

from .views import LiveLogStreamView, TraccarCaptureLogView, TraccarPortOperationView

app_name = 'ops_monitoring'

urlpatterns = [
    path('gps-monitor/logs/<str:stream_name>/', LiveLogStreamView.as_view(), name='gps-live-logs'),
    path('gps-monitor/ports/', TraccarPortOperationView.as_view(), name='gps-port-operations'),
    path('gps-monitor/ports/capture/<int:port>/', TraccarCaptureLogView.as_view(), name='gps-port-capture-log'),
]
