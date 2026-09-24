from rest_framework.response import Response

from src.domain.errors import IdempotencyConflict, InsufficientFunds
from src.infrastructure.container import build_wallet
from src.presentation.controllers.accounts import WalletView
from src.presentation.serializers import TransferSerializer, TransferResultSerializer


class TransfersView(WalletView):
    def handle_exception(self, exc):
        if isinstance(exc, InsufficientFunds):
            return Response({"detail": str(exc)}, status=422)
        if isinstance(exc, IdempotencyConflict):
            return Response({"detail": str(exc)}, status=409)
        return super().handle_exception(exc)

    def post(self, request):
        serializer = TransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = build_wallet().transfer(**serializer.validated_data)
        return Response(TransferResultSerializer(result).data, status=200 if result.replayed else 201)
