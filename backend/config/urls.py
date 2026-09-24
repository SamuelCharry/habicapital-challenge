from django.urls import path

from src.presentation.controllers.health import HealthView


urlpatterns = [path("api/health/", HealthView.as_view(), name="health")]
