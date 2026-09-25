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
