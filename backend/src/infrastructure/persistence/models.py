from uuid import uuid4

from django.db import models

from src.domain.entities import EXTERNAL_FUNDING_ID


class AccountModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    handle = models.CharField(max_length=20, unique=True)
    display_name = models.CharField(max_length=200)
    allows_negative_balance = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(models.Q(id=EXTERNAL_FUNDING_ID, handle="EXTERNAL_FUNDING", allows_negative_balance=True) |
                           (~models.Q(id=EXTERNAL_FUNDING_ID) & models.Q(handle__regex=r"^[a-z0-9_]{3,20}$", allows_negative_balance=False))),
                name="account_funding_or_valid_user",
            ),
        ]


class LedgerEntryModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    account = models.ForeignKey(AccountModel, on_delete=models.PROTECT, related_name="ledger_entries")
    counterparty = models.ForeignKey(AccountModel, on_delete=models.PROTECT, related_name="counterparty_entries")
    operation_id = models.UUIDField(db_index=True)
    operation_type = models.CharField(max_length=20)
    amount_minor = models.BigIntegerField()
    currency = models.CharField(max_length=3)
    created_at = models.DateTimeField()

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(currency="COP"), name="ledger_currency_cop"),
            models.CheckConstraint(condition=~models.Q(amount_minor=0), name="ledger_nonzero_amount"),
            models.UniqueConstraint(fields=["operation_id", "account"], name="ledger_operation_account_unique"),
        ]
