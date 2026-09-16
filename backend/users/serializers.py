from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Serializer for user profile data."""

    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "email", "role", "full_name"]

    def get_full_name(self, obj: User) -> str:
        return obj.get_full_name()


class LoginSerializer(serializers.Serializer):
    """Serializer for login endpoint."""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
