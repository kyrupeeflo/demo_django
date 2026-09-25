from datetime import datetime, timedelta, timezone

from django.test import TestCase, override_settings

from books.tasks import add


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class CeleryTests(TestCase):

    def test_add_task_runs(self):
        result = add.apply_async((2, 3))
        self.assertEqual(result.get(), 5)

    def test_add_with_countdown(self):
        # In eager mode countdown is ignored, so the task runs immediately.
        result = add.apply_async((2, 3), countdown=3)
        self.assertEqual(result.get(), 5)

    def test_add_with_eta(self):
        # eta must be timezone-aware; it is also ignored in eager mode.
        run_at = datetime.now(timezone.utc) + timedelta(seconds=5)
        result = add.apply_async((2, 3), eta=run_at)
        self.assertEqual(result.get(), 5)
