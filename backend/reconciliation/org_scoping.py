from rest_framework.exceptions import NotFound, ParseError

from reconciliation.models import Organization

ORG_HEADER = "X-Organization"


class OrganizationScopedMixin:
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        slug = request.headers.get(ORG_HEADER, "").strip()
        if not slug:
            raise ParseError(f"The {ORG_HEADER} header is required.")
        try:
            request.organization = Organization.objects.get(slug=slug)
        except Organization.DoesNotExist:
            raise NotFound("Organization not found.")