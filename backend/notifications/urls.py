"""In-app notification feed URLs (refinement unit 08 §3.4).

Mounted at ``/api/v1/`` with every other app; the browser reaches them through
the ``/api/notifications/`` proxy routes in Next.js, the same split Plans and
Approvals use.
"""

from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("notifications/", views.NotificationListView.as_view()),
    path("notifications/unread-count/", views.UnreadCountView.as_view()),
    path("notifications/mark-all-read/", views.MarkAllReadView.as_view()),
    path("notifications/<uuid:pk>/mark-read/", views.MarkReadView.as_view()),
]
