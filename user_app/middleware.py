# middleware.py
from django.http import JsonResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from django.utils.timezone import now
from django.db.models import F


class TokenAuthMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if 'HTTP_AUTHORIZATION' in request.META:
            auth = JWTAuthentication()
            try:
                auth.get_user(auth.get_validated_token(
                    request.META['HTTP_AUTHORIZATION'].split(' ')[1]))
            except InvalidToken:
                return JsonResponse({'error': 'Invalid token'}, status=401)
        else:
            return JsonResponse({'error': 'Authorization header missing'}, status=401)

        response = self.get_response(request)
        return response


