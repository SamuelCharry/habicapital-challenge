from django.http import JsonResponse
from django.urls import path, re_path

from src.presentation.controllers.accounts import (
    AccountsView,
    AccountView,
    BalanceView,
    DepositsView,
    HistoryView,
)
from src.presentation.controllers.credit import CreditPathView, CreditProfileView
from src.presentation.controllers.health import HealthView
from src.presentation.controllers.shared_expenses import (
    AccountSharedExpensesView,
    SharedExpensesView,
    SharedExpenseView,
)
from src.presentation.controllers.transfers import TransfersView


def api_not_found(request):
    return JsonResponse({'detail': 'Not found.'}, status=404)


urlpatterns = [
    path('api/health/', HealthView.as_view(), name='health'),
    path('api/accounts/', AccountsView.as_view(), name='accounts'),
    path('api/accounts/<uuid:account_id>/', AccountView.as_view(), name='account'),
    path('api/accounts/<uuid:account_id>/balance/', BalanceView.as_view(), name='account-balance'),
    path('api/accounts/<uuid:account_id>/history/', HistoryView.as_view(), name='account-history'),
    path('api/accounts/<uuid:account_id>/deposits/', DepositsView.as_view(), name='account-deposits'),
    path(
        'api/accounts/<uuid:account_id>/shared-expenses/',
        AccountSharedExpensesView.as_view(),
        name='account-shared-expenses',
    ),
    path(
        'api/accounts/<uuid:account_id>/credit-path/',
        CreditPathView.as_view(),
        name='account-credit-path',
    ),
    path(
        'api/accounts/<uuid:account_id>/credit-profile/',
        CreditProfileView.as_view(),
        name='account-credit-profile',
    ),
    path('api/transfers/', TransfersView.as_view(), name='transfers'),
    path('api/shared-expenses/', SharedExpensesView.as_view(), name='shared-expenses'),
    path('api/shared-expenses/<uuid:expense_id>/', SharedExpenseView.as_view(), name='shared-expense'),
    # An unmatched /api/ path is still an API request, so it answers in JSON
    # rather than falling through to Django's HTML 404 page.
    re_path(r'^api/', api_not_found),
]
