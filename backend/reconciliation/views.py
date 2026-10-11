from rest_framework.generics import ListAPIView

from reconciliation.models import LineItem
from reconciliation.org_scoping import OrganizationScopedMixin
from reconciliation.serializers import LineItemSerializer

# Create your views here.
class LineItemListView(OrganizationScopedMixin, ListAPIView):
    serializer_class = LineItemSerializer

    def get_queryset(self):
        return (
            LineItem.objects.filter(capital_call__organization=self.request.organization)
            .select_related("capital_call")
            .order_by("capital_call__number", "id")
        )
