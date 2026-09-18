from django.urls import path

from .views import LeaveDocumentTemplateView

app_name = "documents"

urlpatterns = [
    path(
        "leave-document-template/",
        LeaveDocumentTemplateView.as_view(),
        name="leave-document-template",
    ),
]