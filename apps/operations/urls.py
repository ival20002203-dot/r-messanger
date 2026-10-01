from django.urls import path
from . import views
app_name="operations"
urlpatterns=[
    path("metrics/",views.metrics,name="metrics"),
    path("client-policy/",views.client_policy,name="client_policy"),
    path("client-update/download/",views.client_update_download,name="client_update_download"),
    path("client-update/feed/<str:platform>/<path:filename>",views.client_update_feed,name="client_update_feed"),
    path("status/",views.status_summary,name="status_summary"),
]
