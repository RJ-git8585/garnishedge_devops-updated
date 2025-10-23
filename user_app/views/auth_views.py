from tokenize import TokenError
from django.shortcuts import get_object_or_404
from rest_framework import status
from django.core.mail import send_mail
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from user_app.models.employer import EmployerProfile
from processor.garnishment_library.utils.response import ResponseHelper
from django.contrib.auth import login as auth_login
from django.contrib.auth.hashers import check_password
from rest_framework_simplejwt.tokens import RefreshToken
from datetime import datetime, timedelta
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenRefreshView
from user_app.serializers import (CustomTokenRefreshSerializer,
                           EmployerRegisterSerializer, PasswordResetRequestSerializer, PasswordResetConfirmSerializer)
from rest_framework.permissions import AllowAny


class CustomTokenRefreshView(TokenRefreshView):
    serializer_class = CustomTokenRefreshSerializer


class LoginAPIView(APIView):
    """
    API view for employer login.
    
    """

    permission_classes = [AllowAny]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'email': openapi.Schema(type=openapi.TYPE_STRING, description='Employer email'),
                'password': openapi.Schema(type=openapi.TYPE_STRING, description='Password'),
            },
            required=['email', 'password']
        ),
        responses={
            200: openapi.Response('Login successful'),
            400: 'Invalid credentials or missing fields',
            500: 'Internal server error'
        }
    )
    def post(self, request, *args, **kwargs):
        """
        Authenticate employer and return JWT tokens.
        """
        data = request.data
        email = data.get('email')
        password = data.get('password')

        if not email or not password:
            return Response({'success': False, 'message': 'Email and password are required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = EmployerProfile.objects.get(email=email)
            if not check_password(password, user.password):
                return Response({'success': False, 'message': 'Invalid credentials'}, status=status.HTTP_400_BAD_REQUEST)
        except EmployerProfile.DoesNotExist:
            return Response({'success': False, 'message': 'Invalid credentials'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'success': False, 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            user.backend = 'django.contrib.auth.backends.ModelBackend'
            auth_login(request, user)
            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)
            
            access_expire = datetime.utcnow() + timedelta(minutes=5)
            refresh_expire = datetime.utcnow() + timedelta(days=1)

            response = Response({
                'success': True,
                'message': 'Login successful',
                'access_token': access_token,
                'refresh_token': str(refresh),
                'access_expires': access_expire,
                'refresh_expires': refresh_expire,
                'session_id': request.session.session_key,
                'user_data': {
                    "id": user.id,
                    'username': user.username,
                    'name': user.employer_name,
                    'email': user.email,
                }
            }, status=status.HTTP_200_OK)


            response.set_cookie(
                key='access',
                value=access_token,
                httponly=False,
                samesite='Lax',
                secure=False,
                expires=access_expire,
            )
            response.set_cookie(
                key='refresh',
                value=str(refresh),
                httponly=False,
                samesite='Lax',
                secure=False,
                expires=refresh_expire,
            )
            return response
        except Exception as e:
            import traceback as t
            return Response({'success': False, 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RegisterAPIView(APIView):
    """
    API view for employer registration.
    """
    
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        request_body=EmployerRegisterSerializer,
        responses={
            201: 'Successfully registered',
            400: 'Validation Failed',
            500: 'Internal server error'
        }
    )
    def post(self, request):
        try:
            serializer = EmployerRegisterSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return ResponseHelper.success_response("Successfully registered", status_code=status.HTTP_201_CREATED)
            return ResponseHelper.error_response("Validation Failed", serializer.errors, status_code=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return ResponseHelper.error_response("Internal server error", str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LogoutAPIView(APIView):
    """
    API view for employer logout.
    """

    @swagger_auto_schema(
        responses={
            205: 'Logout successful',
            400: 'No refresh token found or invalid/expired token',
            500: 'Internal server error'
        }
    )
    def post(self, request):
        refresh_token = request.COOKIES.get('refresh')

        if not refresh_token:
            return Response({"message": "No refresh token found"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError:
            return ResponseHelper.error_response("Invalid or expired token", status_code=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return ResponseHelper.error_response("Internal server error", str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

        response = ResponseHelper.success_response(
            "Logout successful", status_code=status.HTTP_205_RESET_CONTENT)
        response.delete_cookie('access')
        response.delete_cookie('refresh')
        return response


class PasswordResetRequestView(APIView):
    """
    API view to request a password reset link.
    """

    @swagger_auto_schema(
        request_body=PasswordResetRequestSerializer,
        responses={
            200: 'Password reset link sent',
            404: 'User with this email does not exist',
            500: 'Internal server error'
        }
    )
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        try:
            user = EmployerProfile.objects.get(email=email)
            token = RefreshToken.for_user(user).access_token
            reset_url = f'https://garnishment-react-main.vercel.app/reset-password/{str(token)}'
            send_mail(
                'Password Reset Request',
                f'Click the link to reset your password: {reset_url}',
                'your-email@example.com',
                [email],
            )
            return Response({"message": "Password reset link sent.", "status_code": status.HTTP_200_OK})
        except EmployerProfile.DoesNotExist:
            return Response({"error": "User with this email does not exist."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e), "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR})


class PasswordResetConfirmView(APIView):
    """
    API view to confirm password reset.
    """

    @swagger_auto_schema(
        request_body=PasswordResetConfirmSerializer,
        responses={
            200: 'Password reset successful',
            400: 'Invalid token',
            500: 'Internal server error'
        }
    )
    def post(self, request, token):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_password = serializer.validated_data['password']
        try:
            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)
            user_id = access_token['user_id']
            user = EmployerProfile.objects.get(employer_id=user_id)
            user.set_password(new_password)
            user.save()
            get_object_or_404(EmployerProfile,
                              employer_name=user.employer_name, id=user.id)
            return Response({"message": "Password reset successful.", "status_code": status.HTTP_200_OK})
        except (EmployerProfile.DoesNotExist, TokenError):
            return Response({"error": "Invalid token."}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e), "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR})
