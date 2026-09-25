from celery.result import AsyncResult
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Book
from .serializers import BookSerializer
from .tasks import seed_books, start_backfill


class BookViewSet(viewsets.ModelViewSet):
    queryset = Book.objects.all()
    serializer_class = BookSerializer

    @extend_schema(
        summary="Delete all books",
        description="Permanently deletes every Book row and returns how many were removed.",
        request=None,
        responses=inline_serializer(
            "PurgeResponse",
            {"deleted": serializers.IntegerField()},
        ),
    )
    @action(detail=False, methods=["delete"], url_path=r"rip")
    def purge(self, request):
        """Delete all books: DELETE /api/books/purge/"""
        deleted, _ = Book.objects.all().delete()
        return Response({"deleted": deleted}, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Start a self-disabling backfill schedule",
        description="Creates a periodic schedule that adds books in chunks until "
        "`target` is reached, then disables itself.",
        request=inline_serializer(
            "BackfillRequest",
            {
                "target": serializers.IntegerField(default=10000, required=False),
                "chunk": serializers.IntegerField(default=500, required=False),
                "every_seconds": serializers.IntegerField(default=60, required=False),
            },
        ),
        responses=inline_serializer(
            "BackfillResponse",
            {
                "schedule_name": serializers.CharField(),
                "target": serializers.IntegerField(),
                "chunk": serializers.IntegerField(),
                "every_seconds": serializers.IntegerField(),
            },
        ),
    )
    @action(detail=False, methods=["post"])
    def backfill(self, request):
        """Start the backfill schedule: POST /api/books/backfill/"""
        target = int(request.data.get("target", 10000))
        chunk = int(request.data.get("chunk", 500))
        every_seconds = int(request.data.get("every_seconds", 60))
        name = start_backfill(target=target, chunk=chunk, every_seconds=every_seconds)
        return Response(
            {
                "schedule_name": name,
                "target": target,
                "chunk": chunk,
                "every_seconds": every_seconds,
            },
            status=status.HTTP_202_ACCEPTED,
        )

    @extend_schema(
        summary="Seed random books via Celery",
        description="Delegates bulk creation of random books to a Celery worker and "
        "returns immediately with a task id.",
        request=inline_serializer(
            "SeedRequest",
            {"count": serializers.IntegerField(default=10000, required=False)},
        ),
        responses=inline_serializer(
            "SeedResponse",
            {
                "task_id": serializers.CharField(),
                "count": serializers.IntegerField(),
                "status": serializers.CharField(),
            },
        ),
    )
    @action(detail=False, methods=["post"])
    def seed(self, request):
        """Delegate bulk creation to Celery and return immediately."""
        count = int(request.data.get("count", 10000))
        task = seed_books.delay(count)
        return Response(
            {"task_id": task.id, "count": count, "status": "queued"},
            status=status.HTTP_202_ACCEPTED,
        )

    @extend_schema(
        summary="Poll a seeding task",
        parameters=[
            OpenApiParameter(
                "task_id",
                OpenApiTypes.STR,
                OpenApiParameter.PATH,
                description="Celery task id returned by /seed/.",
            )
        ],
        responses=inline_serializer(
            "SeedStatusResponse",
            {
                "task_id": serializers.CharField(),
                "ready": serializers.BooleanField(),
                "state": serializers.CharField(),
                "result": serializers.JSONField(allow_null=True),
            },
        ),
    )
    @action(detail=False, methods=["get"], url_path=r"seed/status/(?P<task_id>[^/.]+)")
    def seed_status(self, request, task_id=None):
        """Poll a seeding task: GET /api/books/seed/status/<task_id>/"""
        result = AsyncResult(task_id)
        payload = {
            "task_id": task_id,
            "ready": result.ready(),
            "state": result.state,
            "result": None,
        }
        if result.successful():
            payload["result"] = result.result
        elif result.failed():
            # result.result is an exception object here, not JSON-serializable.
            payload["result"] = str(result.result)
        return Response(payload)
