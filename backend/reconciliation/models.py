from django.db import models
from django.core.exceptions import ValidationError
from django.db.models import F, Q

from decimal import Decimal

# Create your models here.
class Organization(models.Model):
    slug = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name

class CapitalCall(models.Model):
    organization = models.ForeignKey(
        Organization, 
        on_delete=models.PROTECT, 
        related_name="capital_calls"
    )
    number = models.PositiveIntegerField()
    call_date = models.DateField()
    due_date = models.DateField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "number"], 
                name="uniq_call_number_per_org"
            ),
            models.CheckConstraint(
                condition=Q(due_date__gte=F("call_date")),
                name="call_due_on_or_after_call_date",
            ),
        ]

    def __str__(self):
        return f"{self.organization.slug} call #{self.number}"

class LineItem(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        PARTIALLY_FUNDED = "partially_funded", "Partially funded"
        FUNDED = "funded", "Funded"

    capital_call = models.ForeignKey(
        CapitalCall, on_delete=models.PROTECT, related_name="line_items"
    )
    investor_name = models.CharField(max_length=200)
    expected_reference = models.CharField(max_length=50)
    amount_called = models.DecimalField(max_digits=14, decimal_places=2)
    amount_funded = models.DecimalField(
        max_digits=14, 
        decimal_places=2, 
        default=Decimal("0.00")
    )
    status = models.CharField(
        max_length=20, 
        choices=Status.choices, 
        default=Status.OPEN
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["capital_call", "expected_reference"],
                name="uniq_reference_per_call",
            ),
            models.CheckConstraint(
                condition=Q(amount_called__gt=0), 
                name="line_item_called_positive"
            ),
            models.CheckConstraint(
                condition=Q(amount_funded__gte=0)
                & Q(amount_funded__lte=F("amount_called")),
                name="line_item_funded_within_called",
            ),
            models.CheckConstraint(
                condition=(
                    Q(status="open", amount_funded=0)
                    | Q(
                        status="partially_funded",
                        amount_funded__gt=0,
                        amount_funded__lt=F("amount_called")
                    )
                    | Q(
                        status="funded", 
                        amount_funded=F("amount_called")
                    )
                ),
                name="line_item_status_matches_funding",
            ),
        ]

    @property
    def organization_id(self):
        return self.capital_call.organization_id

    @property
    def amount_remaining(self):
        return self.amount_called - self.amount_funded

    def recompute_status(self):
        if self.amount_funded == 0:
            self.status = self.Status.OPEN
        elif self.amount_funded == self.amount_called:
            self.status = self.Status.FUNDED
        else:
            self.status = self.Status.PARTIALLY_FUNDED

    def __str__(self):
        return f"{self.investor_name} ({self.expected_reference})"


class BankTransaction(models.Model):
    class Type(models.TextChoices):
        CREDIT = "credit", "Credit"
        DEBIT = "debit", "Debit"

    class Status(models.TextChoices):
        SUGGESTED = "suggested", "Suggested"
        NEEDS_REVIEW = "needs_review", "Needs review"
        RECONCILED = "reconciled", "Reconciled"
        IGNORED = "ignored", "Ignored"

    organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, related_name="transactions"
    )
    date = models.DateField()
    description = models.TextField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    transaction_type = models.CharField(max_length=10, choices=Type.choices)
    bank_reference = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=Status.choices)
    review_reason = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "bank_reference"],
                name="uniq_bank_reference_per_org",
            ),
            models.CheckConstraint(
                condition=~Q(amount=0), 
                name="txn_amount_not_zero"
            ),
            models.CheckConstraint(
                condition=(
                    Q(transaction_type="credit", amount__gt=0)
                    | Q(transaction_type="debit", amount__lt=0)
                ),
                name="txn_sign_matches_type",
            ),
            models.CheckConstraint(
                condition=(
                    Q(transaction_type="credit")
                    | Q(status="ignored")
                ),
                name="txn_debit_must_be_ignored",
            ),
        ]
        indexes = [
            models.Index(
                fields=["organization", "-date"],
                name="txn_org_date_idx"
            ),
        ]

    def __str__(self):
        return f"{self.bank_reference} {self.amount}"


class Match(models.Model):
    class Status(models.TextChoices):
        PROPOSED = "proposed", "Proposed"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    transaction = models.ForeignKey(
        BankTransaction,
        on_delete=models.CASCADE,
        related_name="matches",
    )
    line_item = models.ForeignKey(
        LineItem,
        on_delete=models.PROTECT,
        related_name="matches",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PROPOSED,
    )
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["transaction", "line_item"],
                name="uniq_match_per_txn_line_item",
            ),
            models.UniqueConstraint(
                fields=["transaction"],
                condition=Q(status="approved"),
                name="one_approved_match_per_txn",
            ),
        ]

    def validate_same_organization(self):
        transaction_org_id = self.transaction.organization_id
        line_item_org_id = self.line_item.capital_call.organization_id

        if transaction_org_id != line_item_org_id:
            raise ValidationError(
                "transaction and line must belong to the same organization"
            )

    def clean(self):
        self.validate_same_organization()

    def save(self, *args, **kwargs):
        self.validate_same_organization()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.transaction_id} : "
            f"{self.line_item_id} ({self.status})"
        )