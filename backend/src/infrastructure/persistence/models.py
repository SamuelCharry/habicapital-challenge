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


class TransferOperationModel(models.Model):
    idempotency_key = models.CharField(max_length=128)
    request_fingerprint = models.CharField(max_length=64)
    operation_id = models.UUIDField(unique=True)
    # Balances may exceed one entry's bigint range. Decimal fields preserve
    # integer precision without imposing that entry limit on ledger totals.
    source_balance_minor = models.DecimalField(max_digits=40, decimal_places=0, null=True)
    destination_balance_minor = models.DecimalField(max_digits=40, decimal_places=0, null=True)
    currency = models.CharField(max_length=3, default="COP")
    shared_expense = models.ForeignKey('SharedExpenseModel', null=True, blank=True, on_delete=models.PROTECT, related_name='transfers')

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["idempotency_key"], name="transfer_idempotency_key_unique"),
            models.CheckConstraint(condition=models.Q(currency="COP"), name="transfer_currency_cop"),
        ]


class SharedExpenseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    title = models.CharField(max_length=200)
    total_minor = models.BigIntegerField()
    currency = models.CharField(max_length=3)
    payer = models.ForeignKey(AccountModel, on_delete=models.PROTECT, related_name='paid_expenses')

    class Meta:
        ordering = ['id']
        constraints = [
            models.CheckConstraint(condition=models.Q(total_minor__gt=0), name='expense_positive_total'),
            models.CheckConstraint(condition=models.Q(currency='COP'), name='expense_currency_cop'),
        ]


class ParticipantModel(models.Model):
    expense = models.ForeignKey(SharedExpenseModel, on_delete=models.PROTECT, related_name='participants')
    account = models.ForeignKey(AccountModel, on_delete=models.PROTECT, related_name='expense_participations')
    share_minor = models.BigIntegerField()

    class Meta:
        ordering = ['account_id']
        constraints = [
            models.UniqueConstraint(fields=['expense', 'account'], name='expense_participant_unique'),
            models.CheckConstraint(condition=models.Q(share_minor__gt=0), name='participant_positive_share'),
        ]
