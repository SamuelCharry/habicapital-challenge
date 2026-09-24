from django.conf import settings
from django.db import DatabaseError, connection
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthView(APIView):
    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except DatabaseError:
            return Response(
                {
                    "status": "degraded",
                    "database": "unavailable",
                    "version": settings.APP_VERSION,
                },
                status=503,
            )

        return Response(
            {"status": "ok", "database": "ok", "version": settings.APP_VERSION}
        )
