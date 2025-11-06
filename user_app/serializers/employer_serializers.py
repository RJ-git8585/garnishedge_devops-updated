from rest_framework import serializers
from user_app.models import EmployerProfile

class EmployerProfileSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)
    
    class Meta:
        model = EmployerProfile
        fields = '__all__'
    
    def update(self, instance, validated_data):
        # Handle password separately if provided
        password = validated_data.pop('password', None)
        if password:
            instance.set_password(password)
        
        # Update other fields using parent's update method
        return super().update(instance, validated_data)

class GetEmployerDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployerProfile
        fields = '__all__'
