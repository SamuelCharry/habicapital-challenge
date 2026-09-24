from unittest.mock import patch

import pytest
from django.db import OperationalError, connections
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_health_returns_ok_when_database_reachable():
    with CaptureQueriesContext(connections["default"]) as queries:
        response = APIClient().get("/api/health/")

    assert [query["sql"] for query in queries] == ["SELECT 1"]
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": "ok",
        "version": "0.1.0",
    }


@pytest.mark.django_db
def test_health_reports_degraded_when_database_unavailable():
    with patch(
        "src.presentation.controllers.health.connection.cursor"
    ) as cursor:
        cursor.return_value.__enter__.return_value.execute.side_effect = (
            OperationalError("database unavailable")
        )
        response = APIClient().get("/api/health/")

    assert response.status_code == 503
    assert response.json() == {
        "status": "degraded",
        "database": "unavailable",
        "version": "0.1.0",
    }
    cursor.return_value.__enter__.return_value.execute.assert_called_once_with(
        "SELECT 1"
    )


def test_settings_do_not_wrap_requests_in_transactions():
    assert connections["default"].settings_dict["ATOMIC_REQUESTS"] is False


@pytest.mark.django_db
def test_test_database_is_postgresql():
    connection = connections["default"]
    assert connection.settings_dict["ENGINE"] == "django.db.backends.postgresql"
    with connection.cursor() as cursor:
        cursor.execute("SELECT version()")
        assert cursor.fetchone()[0].startswith("PostgreSQL")
