from rest_framework.response import Response
from rest_framework.views import APIView

from src.domain.errors import AccountNotFound, DomainError, SharedExpenseNotFound
from src.infrastructure.container import build_wallet
from src.presentation.serializers import (
    AccountSerializer, BalanceSerializer, CreateAccountSerializer, DepositSerializer,
    DepositResultSerializer, ExactJSONParser, HistorySerializer,
)


class WalletView(APIView):
    parser_classes = [ExactJSONParser]

    def handle_exception(self, exc):
        if isinstance(exc, DomainError):
            return Response({"detail": str(exc)}, status=404 if isinstance(exc, (AccountNotFound, SharedExpenseNotFound)) else 400)
        return super().handle_exception(exc)


class AccountsView(WalletView):
    def get(self, request):
        return Response(AccountSerializer(build_wallet().list_accounts(), many=True).data)

    def post(self, request):
        serializer = CreateAccountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = build_wallet().create_account(**serializer.validated_data)
        return Response(AccountSerializer(result).data, status=201)


class AccountView(WalletView):
    def get(self, request, account_id):
        return Response(AccountSerializer(build_wallet().get_account(account_id)).data)


class BalanceView(WalletView):
    def get(self, request, account_id):
        return Response(BalanceSerializer(build_wallet().balance(account_id)).data)


class HistoryView(WalletView):
    def get(self, request, account_id):
        return Response(HistorySerializer(build_wallet().history(account_id), many=True).data)


class DepositsView(WalletView):
    def post(self, request, account_id):
        serializer = DepositSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = build_wallet().deposit(account_id, **serializer.validated_data)
        return Response(DepositResultSerializer(result).data, status=201)
