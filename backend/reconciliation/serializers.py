from rest_framework import serializers

from reconciliation.models import LineItem


class LineItemSerializer(serializers.ModelSerializer):
    capital_call_number = serializers.IntegerField(source="capital_call.number")
    call_date = serializers.DateField(source="capital_call.call_date")
    due_date = serializers.DateField(source="capital_call.due_date")
    amount_remaining = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )

    class Meta:
        model = LineItem
        fields = [
            "id", "capital_call_number", "call_date", "due_date",
            "investor_name", "expected_reference",
            "amount_called", "amount_funded", "amount_remaining", "status",
        ]