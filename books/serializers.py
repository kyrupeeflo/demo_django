from datetime import date

from rest_framework import serializers

from .models import Book


class BookSerializer(serializers.ModelSerializer):
    title = serializers.CharField(max_length=200)
    author = serializers.CharField(max_length=100)
    published_date = serializers.DateField()
    isbn = serializers.CharField(max_length=13)
    price = serializers.DecimalField(max_digits=6, decimal_places=2)

    class Meta:
        model = Book
        fields = ['id', 'title', 'author', 'published_date', 'isbn', 'price']

    def validate_isbn(self, value):
        """Field-level validation: ISBN must be exactly 13 digits."""
        if not value.isdigit() or len(value) != 13:
            raise serializers.ValidationError("ISBN must be exactly 13 digits.")
        return value

    def validate_price(self, value):
        """Field-level validation: price must be positive."""
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than zero.")
        return value

    def validate_published_date(self, value):
        """Field-level validation: no future publish dates."""
        if value > date.today():
            raise serializers.ValidationError("Published date cannot be in the future.")
        return value

    def validate(self, data):
        """Object-level validation: runs after all field validations pass."""
        # Example: cross-field check, adjust as needed
        if self.title == "Chalisa" and self.author == "Tulsidas":
            raise serializers.ValidationError("Dont add holybooks here.")
        return data