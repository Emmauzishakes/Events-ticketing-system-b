# from rest_framework import serializers
# from django.contrib.auth.models import User
# from .models import CreatorApplication

# class UserRegisterSerializer(serializers.ModelSerializer):
#     password = serializers.CharField(write_only=True)

#     class Meta:
#         model = User
#         fields = ['username', 'email', 'password']

#     def create(self, validated_data):
#         user = User.objects.create_user(
#             username=validated_data['username'],
#             email=validated_data.get('email', ''),
#             password=validated_data['password']
#         )
#         return user

# class CreatorApplicationSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = CreatorApplication
#         fields = ['brand_name', 'description', 'website_url', 'phone_number', 'national_id_passport']