from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from reconciliation.models import CapitalCall, LineItem, Organization

SEED = [
    {
        "slug": "northwind",
        "name": "Northwind Ventures",
        "calls": [
            {
                "number": 1,
                "call_date": date(2026, 3, 25),
                "due_date": date(2026, 4, 10),
                "items": [
                    ("Haller Capital LLC", "CC-1001", "27500.00"),
                    ("Rahul Shah Trust", "CC-1002", "25000.00"),
                    ("Patel Family Trust", "CC-1003", "12500.00"),
                    ("Meridian Partners LP", "CC-1004", "15000.00"),
                    ("Oakridge Holdings LLC", "CC-1005", "15000.00"),
                ],
            },
            {
                "number": 2,
                "call_date": date(2026, 4, 1),
                "due_date": date(2026, 4, 20),
                "items": [("Oakridge Holdings LLC", "CC-1006", "15000.00")],
            },
        ],
    },
    {
        "slug": "bluebird",
        "name": "Bluebird Capital",
        "calls": [
            {
                "number": 1,
                "call_date": date(2026, 4, 1),
                "due_date": date(2026, 4, 15),
                "items": [("Cedar Grove Fund LP", "CC-2001", "40000.00")],
            }
        ],
    },
]

class Command(BaseCommand):
    help = "create the demo organizations, capital calls and line items"

    @transaction.atomic
    def handle(self, *args, **options):
        created = {"organizations": 0, "capital calls": 0, "line items": 0}

        for org_data in SEED:
            org, was_created = Organization.objects.get_or_create(
                slug=org_data["slug"], defaults={"name": org_data["name"]}
            )
            created["organizations"] += was_created

            for call_data in org_data["calls"]:
                call, was_created = CapitalCall.objects.get_or_create(
                    organization=org,
                    number=call_data["number"],
                    defaults={
                        "call_date": call_data["call_date"],
                        "due_date": call_data["due_date"],
                    },
                )
                created["capital calls"] += was_created

                for investor, reference, amount in call_data["items"]:
                    _, was_created = LineItem.objects.get_or_create(
                        capital_call=call,
                        expected_reference=reference,
                        defaults={
                            "investor_name": investor,
                            "amount_called": Decimal(amount)
                        },
                    )
                    created["line items"] += was_created

        summary = ", ".join(f"{n} {label}" for label, n in created.items())
        self.stdout.write(self.style.SUCCESS(f"seed complete. created: {summary}"))
