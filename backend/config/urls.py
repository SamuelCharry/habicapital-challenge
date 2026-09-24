from django.urls import path

from src.presentation.controllers.health import HealthView


from src.presentation.controllers.accounts import AccountsView, AccountView, BalanceView, HistoryView, DepositsView

urlpatterns = [
    path("api/health/", HealthView.as_view(), name="health"),
    path("api/accounts/", AccountsView.as_view(), name="accounts"),
    path("api/accounts/<uuid:account_id>/", AccountView.as_view(), name="account"),
    path("api/accounts/<uuid:account_id>/balance/", BalanceView.as_view(), name="account-balance"),
    path("api/accounts/<uuid:account_id>/history/", HistoryView.as_view(), name="account-history"),
    path("api/accounts/<uuid:account_id>/deposits/", DepositsView.as_view(), name="account-deposits"),
]
