from rest_framework import serializers


class PublicIdRelatedField(serializers.SlugRelatedField):
    def __init__(self, **kwargs):
        kwargs.setdefault("slug_field", "public_id")
        super().__init__(**kwargs)
