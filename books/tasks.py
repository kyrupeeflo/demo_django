import random
import string
from datetime import date, timedelta

from celery import shared_task

from .models import Book


@shared_task
def add(x, y):
    return x + y


ADJECTIVES = ["Silent", "Golden", "Broken", "Hidden", "Last", "Distant", "Crimson", "Forgotten"]
NOUNS = ["Kingdom", "River", "Shadow", "Promise", "Garden", "Storm", "Secret", "Journey"]
AUTHORS = ["Austen", "Tolkien", "Rowling", "Orwell", "Dickens", "Christie", "King", "Verne"]


def _random_isbn():
    return "".join(random.choices(string.digits, k=13))


@shared_task
def seed_books(count=10000):
    """Create `count` Book rows with random values. Runs in the Celery worker."""
    today = date.today()
    used_isbns = set()
    books = []

    for _ in range(count):
        # ISBN is unique, so avoid collisions within this batch.
        isbn = _random_isbn()
        while isbn in used_isbns:
            isbn = _random_isbn()
        used_isbns.add(isbn)

        books.append(
            Book(
                title=f"The {random.choice(ADJECTIVES)} {random.choice(NOUNS)}",
                author=random.choice(AUTHORS),
                published_date=today - timedelta(days=random.randint(0, 20000)),
                isbn=isbn,
                price=round(random.uniform(1, 999), 2),
            )
        )

    # bulk_create is far faster than 10,000 individual .save() calls.
    # ignore_conflicts skips the rare chance an ISBN already exists in the DB.
    created = Book.objects.bulk_create(books, batch_size=10, ignore_conflicts=True)
    return {"requested": count, "created": len(created)}


@shared_task(bind=True)
def backfill_books(self, target=10000, chunk=500, schedule_name=None):
    """Create books in chunks each run; disable the schedule once `target` is reached."""
    from django_celery_beat.models import PeriodicTask

    # Reuse the bulk-create logic for a single chunk.
    seed_books(chunk)

    total = Book.objects.count()
    done = total >= target

    if done and schedule_name:
        # Turn the recurring schedule off. Beat stops sending it on its next tick.
        PeriodicTask.objects.filter(name=schedule_name).update(enabled=False)

    return {"total": total, "target": target, "done": done}


def start_backfill(target=10000, chunk=500, every_seconds=60):
    """Create (or update) a self-disabling periodic schedule that backfills books."""
    import json

    from django_celery_beat.models import IntervalSchedule, PeriodicTask

    schedule, _ = IntervalSchedule.objects.get_or_create(
        every=every_seconds, period=IntervalSchedule.SECONDS,
    )
    name = "backfill-books"
    PeriodicTask.objects.update_or_create(
        name=name,
        defaults={
            "interval": schedule,
            "task": "books.tasks.backfill_books",
            # The task needs its own schedule name so it can disable this row.
            "kwargs": json.dumps(
                {"target": target, "chunk": chunk, "schedule_name": name}
            ),
            "enabled": True,
        },
    )
    return name
