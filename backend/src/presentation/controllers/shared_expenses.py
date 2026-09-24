from rest_framework.response import Response

from src.infrastructure.container import build_wallet
from src.presentation.controllers.accounts import WalletView
from src.presentation.serializers import CreateSharedExpenseSerializer, SharedExpenseSerializer


class SharedExpensesView(WalletView):
    def post(self, request):
        serializer = CreateSharedExpenseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = build_wallet().create_shared_expense(**serializer.validated_data)
        return Response(SharedExpenseSerializer(result).data, status=201)

    def get(self, request):
        return Response(SharedExpenseSerializer(build_wallet().list_shared_expenses(), many=True).data)


class SharedExpenseView(WalletView):
    def get(self, request, expense_id):
        return Response(SharedExpenseSerializer(build_wallet().get_shared_expense(expense_id)).data)


class AccountSharedExpensesView(WalletView):
    def get(self, request, account_id):
        return Response(SharedExpenseSerializer(build_wallet().list_shared_expenses(account_id), many=True).data)
