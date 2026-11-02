from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from customer.models import CustomerProfile

from .serializers import LoginSerializer, ProfileUpdateSerializer, RegistrationSerializer
from .session_utils import login_role_user, logout_role_user


def profile_payload(user, request):
    profile, _ = CustomerProfile.objects.get_or_create(user=user)
    profile_image = None
    if profile.profile_image:
        profile_image = request.build_absolute_uri(profile.profile_image.url)

    name = f"{user.first_name} {user.last_name}".strip() or user.username
    return {
        "id": user.pk,
        "name": name,
        "email": user.email,
        "phone": profile.phone_number or "",
        "role": user.role,
        "profile_image": profile_image,
        "address": profile.address,
    }


class RegisterAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    parser_classes = [JSONParser, FormParser, MultiPartParser]
    role = "customer"

    def post(self, request):
        serializer = RegistrationSerializer(
            data=request.data,
            context={"role": self.role},
        )
        if not serializer.is_valid():
            return Response(
                {"success": False, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            with transaction.atomic():
                serializer.save()
        except IntegrityError:
            return Response(
                {"success": False, "message": "Email or phone number is already registered."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {
                "success": True,
                "message": "Account created successfully",
                "role": self.role,
            },
            status=status.HTTP_201_CREATED,
        )


class RestaurantRegisterAPIView(RegisterAPIView):
    role = "restaurant_owner"


class DeliveryRegisterAPIView(RegisterAPIView):
    role = "delivery_partner"


class LoginAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    role = None

    def post(self, request):
        serializer = LoginSerializer(
            data=request.data,
            context={"request": request, "required_role": self.role},
        )
        if not serializer.is_valid():
            return Response(
                {"success": False, "errors": serializer.errors},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        user = serializer.validated_data["user"]
        role = self.role or getattr(user, "role", "customer")
        login_role_user(request, user, role)
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "success": True,
                "message": "Login successful",
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": profile_payload(user, request),
            }
        )


class RestaurantLoginAPIView(LoginAPIView):
    role = "restaurant_owner"


class CustomerLoginAPIView(LoginAPIView):
    role = "customer"


class DeliveryLoginAPIView(LoginAPIView):
    role = "delivery_partner"


class ProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get(self, request):
        return Response(profile_payload(request.user, request))

    def put(self, request):
        serializer = ProfileUpdateSerializer(
            request.user,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        user = serializer.save()
        return Response(profile_payload(user, request))

    def delete(self, request):
        user = request.user
        role = getattr(user, "role", "customer")
        username = user.username
        if user.is_superuser:
            return Response(
                {"success": False, "message": "Superuser accounts cannot be deleted."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        logout_role_user(request, role)
        auth_logout(request)
        user.delete()
        return Response(
            {"success": True, "message": f"Account '{username}' deleted successfully."},
            status=status.HTTP_200_OK,
        )


class DeleteAccountAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        return ProfileAPIView().delete(request)

    def delete(self, request):
        return ProfileAPIView().delete(request)


class LogoutAPIView(APIView):
    permission_classes = [IsAuthenticated]
    role = None

    def post(self, request):
        role = self.role or request.data.get("role") or getattr(request.user, "role", None)
        refresh_token = request.data.get("refresh")
        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                if str(token.get("user_id")) != str(request.user.pk):
                    return Response(
                        {"success": False, "message": "Invalid refresh token."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                token.blacklist()
            except TokenError:
                return Response(
                    {"success": False, "message": "Invalid refresh token."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if role:
            logout_role_user(request, role)
        else:
            auth_logout(request)
        return Response({"success": True, "message": "Logged out successfully"})


class CustomerLogoutAPIView(LogoutAPIView):
    role = "customer"


class DeliveryLogoutAPIView(LogoutAPIView):
    role = "delivery_partner"