from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import LeaveApplicationViewSet, SupportingDocumentViewSet

router = DefaultRouter()
router.register(r"leave-applications", LeaveApplicationViewSet, basename="leave-application")

supporting_doc_list = SupportingDocumentViewSet.as_view({"get": "list", "post": "create"})
supporting_doc_detail = SupportingDocumentViewSet.as_view(
    {"get": "retrieve", "delete": "destroy"}
)

app_name = "leave"

urlpatterns = [
    path("", include(router.urls)),
    path(
        "leave-applications/<uuid:application_pk>/documents/",
        supporting_doc_list,
        name="supportingdocument-list",
    ),
    path(
        "leave-applications/<uuid:application_pk>/documents/<uuid:pk>/",
        supporting_doc_detail,
        name="supportingdocument-detail",
    ),
]
