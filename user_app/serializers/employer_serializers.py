from rest_framework import serializers
from user_app.models import EmployerProfile

class EmployerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployerProfile
        fields = '__all__'

class GetEmployerDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployerProfile
        fields = '__all__'
