from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Count

from .models import Notification
from .serializers import NotificationSerializer
from .pagination import NotificationPagination


class NotificationViewSet(ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = NotificationPagination

    def get_queryset(self):
        user = self.request.user

        qs = Notification.objects.filter(
            user=user,
            tenant_id=user.tenant_id
        ).order_by("-created_at")

        # 🔎 filtre non lus
        unread = self.request.query_params.get("unread")
        if unread == "true":
            qs = qs.filter(is_read=False)

        return qs

    # 🔥 marquer UNE notification comme lue
    @action(detail=True, methods=["post"])
    def mark_as_read(self, request, pk=None):
        notif = self.get_object()

        if not notif.is_read:
            notif.is_read = True
            notif.save(update_fields=["is_read"])

        return Response({"status": "read"})

    # 🔥 marquer TOUT comme lu
    @action(detail=False, methods=["post"])
    def mark_all_as_read(self, request):
        user = request.user

        updated = Notification.objects.filter(
            user=user,
            tenant_id=user.tenant_id,
            is_read=False
        ).update(is_read=True)

        return Response({
            "status": "all read",
            "updated": updated
        })

    # 🔥 compteur notifications non lues
    @action(detail=False, methods=["get"])
    def unread_count(self, request):
        user = request.user

        count = Notification.objects.filter(
            user=user,
            tenant_id=user.tenant_id,
            is_read=False
        ).count()

        return Response({"unread_count": count})