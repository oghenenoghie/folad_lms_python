import pytest

from apps.core.storage import get_file_bytes, save_document


@pytest.mark.django_db
def test_get_file_bytes_round_trips_a_saved_document():
    key = save_document(
        key_prefix="test-storage",
        filename="note.txt",
        content=b"hello from a test",
        content_type="text/plain",
    )

    assert get_file_bytes(key) == b"hello from a test"


@pytest.mark.django_db
def test_get_file_bytes_returns_none_for_a_missing_key():
    assert get_file_bytes("test-storage/does-not-exist.txt") is None
