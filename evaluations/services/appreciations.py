from evaluations.models import Appreciation


def get_appreciation(*, tenant, moyenne):
    if moyenne is None:
        return None

    return (
        Appreciation.objects
        .filter(
            tenant=tenant,
            moyenne_min__lte=moyenne
        )
        .order_by("-moyenne_min")
        .first()
    )