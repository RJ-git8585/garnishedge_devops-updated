from rest_framework import serializers
from user_app.models import EmployerProfile
from datetime import datetime
from django.contrib.auth.hashers import make_password
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import AccessToken

class CustomTokenRefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)

        access_token = AccessToken(data['access'])

        # Add expiration time
        data['access_expires'] = access_token['exp']
        # Add human-readable datetime
        data['access_expires_datetime'] = datetime.fromtimestamp(
            access_token['exp']).isoformat()

        return data

class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError("Passwords do not match.")
        return data



class EmployerRegisterSerializer(serializers.ModelSerializer):
    password1 = serializers.CharField(write_only=True)
    password2 = serializers.CharField(write_only=True)

    class Meta:
        model = EmployerProfile
        fields = [
            'employer_name', 'username', 'email', 'password1', 'password2',
            'federal_employer_identification_number', 'street_name', 'city',
            'state', 'country', 'zipcode', 'number_of_employees',
            'department', 'location'
        ]

    def validate(self, data):
        password1 = data.get('password1')
        password2 = data.get('password2')

        if password1 != password2:
            raise serializers.ValidationError("Passwords do not match")

        if not (len(password1) >= 8 and any(c.isupper() for c in password1) and
                any(c.islower() for c in password1) and any(c.isdigit() for c in password1) and
                any(c in '!@#$%^&*()_+' for c in password1)):
            raise serializers.ValidationError(
                "Password must meet complexity requirements")

        if EmployerProfile.objects.filter(username=data['username']).exists():
            raise serializers.ValidationError("Username already used")

        if EmployerProfile.objects.filter(email=data['email']).exists():
            raise serializers.ValidationError("Email already used")

        return data

    def create(self, validated_data):
        validated_data.pop('password2')
        validated_data['password'] = make_password(
            validated_data.pop('password1'))
        return EmployerProfile.objects.create(**validated_data)