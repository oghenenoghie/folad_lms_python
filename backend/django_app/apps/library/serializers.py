from rest_framework import serializers

from apps.core.serializers import PublicIdRelatedField
from apps.schools.models import School
from apps.staff.models import Staff
from apps.students.models import Student

from .models import LibraryBook, LibraryCopy, LibraryFine, LibraryLoan, LibraryMember


class LibraryBookSerializer(serializers.ModelSerializer):
    school = PublicIdRelatedField(queryset=School.objects)

    class Meta:
        model = LibraryBook
        fields = [
            "public_id", "school", "isbn", "title", "author", "publisher", "category", "published_year",
        ]


class LibraryCopySerializer(serializers.ModelSerializer):
    book = PublicIdRelatedField(queryset=LibraryBook.objects)

    class Meta:
        model = LibraryCopy
        fields = ["public_id", "book", "copy_number", "status"]
        read_only_fields = ["status"]


class LibraryMemberSerializer(serializers.ModelSerializer):
    school = PublicIdRelatedField(queryset=School.objects)
    student = PublicIdRelatedField(queryset=Student.objects, required=False, allow_null=True)
    staff = PublicIdRelatedField(queryset=Staff.objects, required=False, allow_null=True)

    class Meta:
        model = LibraryMember
        fields = ["public_id", "school", "member_type", "student", "staff", "membership_number", "is_active"]


class LibraryLoanSerializer(serializers.ModelSerializer):
    copy = PublicIdRelatedField(queryset=LibraryCopy.objects)
    member = PublicIdRelatedField(queryset=LibraryMember.objects)

    class Meta:
        model = LibraryLoan
        fields = ["public_id", "copy", "member", "borrowed_date", "due_date", "returned_date", "status"]
        read_only_fields = ["returned_date", "status"]
        extra_kwargs = {"borrowed_date": {"required": False}}
        validators = []


class LibraryFineSerializer(serializers.ModelSerializer):
    loan = PublicIdRelatedField(queryset=LibraryLoan.objects)

    class Meta:
        model = LibraryFine
        fields = ["public_id", "loan", "amount_minor", "currency_code", "reason", "status", "paid_at"]
        read_only_fields = ["currency_code", "status", "paid_at"]
