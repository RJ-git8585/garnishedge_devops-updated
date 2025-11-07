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
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError as JWTTokenError
from rest_framework_simplejwt.authentication import JWTAuthentication
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
            
            access_expire = datetime.utcnow() + timedelta(minutes=60)
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


class ValidateTokenAPIView(APIView):
    """
    API view to validate an access token.
    Accepts token either in Authorization header or as a request body parameter.
    """

    permission_classes = [AllowAny]

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                'Authorization',
                openapi.IN_HEADER,
                description='Bearer token (e.g., Bearer <token>)',
                type=openapi.TYPE_STRING,
                required=False
            ),
        ],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'token': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Access token to validate'
                ),
            },
            required=[]
        ),
        responses={
            200: openapi.Response(
                'Token validation result',
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'valid': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                        'token_details': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'user_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                                'exp': openapi.Schema(type=openapi.TYPE_INTEGER),
                                'expires_at': openapi.Schema(type=openapi.TYPE_STRING),
                                'token_type': openapi.Schema(type=openapi.TYPE_STRING),
                            }
                        ),
                        'user_data': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                                'username': openapi.Schema(type=openapi.TYPE_STRING),
                                'email': openapi.Schema(type=openapi.TYPE_STRING),
                                'employer_name': openapi.Schema(type=openapi.TYPE_STRING),
                            }
                        )
                    }
                )
            ),
            400: 'Invalid token or missing token',
            401: 'Invalid or expired token'
        }
    )
    def post(self, request, *args, **kwargs):
        """
        Validate an access token.
        Token can be provided in:
        1. Authorization header: "Bearer <token>"
        2. Request body: {"token": "<token>"}
        """
        token = None
        
        # Try to get token from Authorization header
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
        
        # If not in header, try to get from request body
        if not token:
            token = request.data.get('token')
        
        if not token:
            return ResponseHelper.error_response(
                message='Token is required. Provide it in Authorization header (Bearer <token>) or request body ({"token": "<token>"})',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Validate the token
            jwt_auth = JWTAuthentication()
            validated_token = jwt_auth.get_validated_token(token)
            user = jwt_auth.get_user(validated_token)
            
            # Extract token details
            access_token = AccessToken(token)
            token_payload = access_token.payload
            
            # Calculate expiration datetime
            exp_timestamp = token_payload.get('exp')
            expires_at = datetime.fromtimestamp(exp_timestamp).isoformat() if exp_timestamp else None
            
            # Prepare response data
            response_data = {
                'valid': True,
                'token_details': {
                    'user_id': token_payload.get('user_id'),
                    'exp': exp_timestamp,
                    'expires_at': expires_at,
                    'token_type': token_payload.get('token_type', 'access'),
                },
                'user_data': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'employer_name': getattr(user, 'employer_name', None),
                }
            }
            
            return ResponseHelper.success_response(
                message='Token is valid',
                data=response_data,
                status_code=status.HTTP_200_OK
            )
            
        except (InvalidToken, JWTTokenError) as e:
            return ResponseHelper.error_response(
                message='Invalid or expired token',
                error=str(e),
                status_code=status.HTTP_401_UNAUTHORIZED
            )
        except Exception as e:
            return ResponseHelper.error_response(
                message='Error validating token',
                error=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def get(self, request, *args, **kwargs):
        """
        Validate token from Authorization header (GET method for convenience).
        """
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith('Bearer '):
            return ResponseHelper.error_response(
                message='Authorization header with Bearer token is required',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        token = auth_header.split(' ')[1]
        
        try:
            # Validate the token
            jwt_auth = JWTAuthentication()
            validated_token = jwt_auth.get_validated_token(token)
            user = jwt_auth.get_user(validated_token)
            
            # Extract token details
            access_token = AccessToken(token)
            token_payload = access_token.payload
            
            # Calculate expiration datetime
            exp_timestamp = token_payload.get('exp')
            expires_at = datetime.fromtimestamp(exp_timestamp).isoformat() if exp_timestamp else None
            
            # Prepare response data
            response_data = {
                'valid': True,
                'token_details': {
                    'user_id': token_payload.get('user_id'),
                    'exp': exp_timestamp,
                    'expires_at': expires_at,
                    'token_type': token_payload.get('token_type', 'access'),
                },
                'user_data': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'employer_name': getattr(user, 'employer_name', None),
                }
            }
            
            return ResponseHelper.success_response(
                message='Token is valid',
                data=response_data,
                status_code=status.HTTP_200_OK
            )
            
        except (InvalidToken, JWTTokenError) as e:
            return ResponseHelper.error_response(
                message='Invalid or expired token',
                error=str(e),
                status_code=status.HTTP_401_UNAUTHORIZED
            )
        except Exception as e:
            return ResponseHelper.error_response(
                message='Error validating token',
                error=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
