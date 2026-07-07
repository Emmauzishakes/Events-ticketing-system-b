# from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
# from django.contrib.auth.models import User
# from django.middleware.csrf import get_token
# from django.views.decorators.csrf import ensure_csrf_cookie
# from rest_framework.decorators import api_view, permission_classes
# from rest_framework.permissions import IsAuthenticated, AllowAny
# from rest_framework.response import Response
# from rest_framework import status

# from .models import CreatorApplication
# from .serializers import UserRegisterSerializer, CreatorApplicationSerializer

# @api_view(['GET'])
# @ensure_csrf_cookie
# def get_csrf_token(request):
#     """Next.js will call this to initialize the CSRF token cookie."""
#     return Response({"message": "CSRF cookie set"})

# @api_view(['POST'])
# @permission_classes([AllowAny])
# def register_viewer(request):
#     """Registers a basic viewer account."""
#     serializer = UserRegisterSerializer(data=request.data)
#     if serializer.is_valid():
#         serializer.save()
#         return Response({"message": "Account created successfully."}, status=status.HTTP_201_CREATED)
#     return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# @api_view(['POST'])
# @permission_classes([AllowAny])
# def login_view(request):
#     """Authenticates user and signs them in using HttpOnly Session cookies."""
#     username = request.data.get('username')
#     password = request.data.get('password')

#     user = authenticate(request, username=username, password=password)
    
#     if user is not None:
#         auth_login(request, user) # Sets session cookie under the hood
        
#         # Determine account state/role
#         user_role = "VIEWER"
#         if hasattr(user, 'creator_profile'):
#             user_role = user.creator_profile.status # PENDING, APPROVED, REJECTED
            
#         return Response({
#             "message": "Login successful",
#             "username": user.username,
#             "role": user_role
#         }, status=status.HTTP_200_OK)
        
#     return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)

# @api_view(['POST'])
# @permission_classes([IsAuthenticated])
# def submit_creator_application(request):
#     """Allows authenticated users to submit a form-based Creator profile for approval."""
#     # Prevent submitting duplicate applications
#     if CreatorApplication.objects.filter(user=request.user).exists():
#         return Response({"error": "An application has already been registered for this account."}, status=status.HTTP_400_BAD_REQUEST)
        
#     serializer = CreatorApplicationSerializer(data=request.data)
#     if serializer.is_valid():
#         serializer.save(user=request.user, status='PENDING')
#         return Response({
#             "message": "Application submitted successfully and is awaiting administrator review.",
#             "role": "PENDING"
#         }, status=status.HTTP_201_CREATED)
        
#     return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# @api_view(['GET'])
# @permission_classes([IsAuthenticated])
# def check_auth_status(request):
#     """Frontend will run this on page load to confirm session validity and read privileges."""
#     user_role = "VIEWER"
#     if hasattr(request.user, 'creator_profile'):
#         user_role = request.user.creator_profile.status

#     return Response({
#         "authenticated": True,
#         "username": request.user.username,
#         "role": user_role
#     }, status=status.HTTP_200_OK)

# @api_view(['POST'])
# def logout_view(request):
#     """Clears session data and expunges cookies."""
#     auth_logout(request)
#     return Response({"message": "Logged out successfully"}, status=status.HTTP_200_OK)


from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.signals import user_login_failed
from django.views.decorators.csrf import ensure_csrf_cookie
from django.http import JsonResponse
from django.core.exceptions import PermissionDenied
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

def locked_out_api_response(request, *args, **kwargs):
    """Custom handler for django-axes."""
    return JsonResponse(
        {
            "error": "Maximum login attempts exceeded. Your IP address has been temporarily blocked for security reasons. Please try again in 1 hour."
        }, 
        status=429 # 429 is the standard HTTP status for "Too Many Requests"
    )

@api_view(['GET'])
@ensure_csrf_cookie
def get_csrf_token(request):
    return Response({"message": "CSRF cookie set"})

@api_view(['POST'])
@permission_classes([AllowAny])
def admin_login(request):
    """Authenticates ONLY staff/superusers using HttpOnly Session cookies."""
    username = request.data.get('username')
    password = request.data.get('password')

    try:
        user = authenticate(request, username=username, password=password)
    except PermissionDenied:
        return Response(
            {"error": "Maximum login attempts exceeded. Your IP address has been temporarily blocked for security reasons. Please try again in 1 hour."},
            status=status.HTTP_429_TOO_MANY_REQUESTS
        )
    
    if user is not None:
        # Security Check: Reject normal users, only allow Admins
        if not user.is_staff:
            return Response({"error": "Unauthorized access. Admin privileges required."}, status=status.HTTP_403_FORBIDDEN)

        auth_login(request, user)
        return Response({
            "message": "Admin login successful",
            "username": user.username,
            "is_admin": True
        }, status=status.HTTP_200_OK)
    
    user_login_failed.send(
        sender=__name__,
        credentials={'username': username},
        request=request
    )
        
    return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_auth_status(request):
    """Verifies the session cookie and ensures the user is still an admin."""
    if not request.user.is_staff:
        return Response({"authenticated": False}, status=status.HTTP_401_UNAUTHORIZED)

    return Response({
        "authenticated": True,
        "username": request.user.username,
        "is_admin": True
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
def logout_view(request):
    auth_logout(request)
    return Response({"message": "Logged out successfully"}, status=status.HTTP_200_OK)

