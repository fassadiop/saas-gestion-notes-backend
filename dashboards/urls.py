from django.urls import path
from .views import DashboardAcademieView, DashboardIEFView, DashboardNationalView

urlpatterns = [
    path("ief/", DashboardIEFView.as_view()),
    path("academie/", DashboardAcademieView.as_view()),
    path("national/", DashboardNationalView.as_view()),
]