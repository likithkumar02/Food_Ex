import re

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from customer.models import CustomerProfile
from delivery.models import DeliveryPartnerProfile
from restaurant.models import Restaurant


User = get_user_model()


class RegistrationSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=15)
    password = serializers.CharField(min_length=8, trim_whitespace=False)
    confirm_password = serializers.CharField(trim_whitespace=False)
    restaurant_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    restaurant_type = serializers.ChoiceField(
        choices=Restaurant.RESTAURANT_TYPE_CHOICES,
        required=False,
    )
    cuisine_type = serializers.CharField(max_length=100, required=False, allow_blank=True)
    restaurant_address = serializers.CharField(required=False, allow_blank=True)
    city = serializers.CharField(max_length=100, required=False, allow_blank=True)
    state = serializers.CharField(max_length=100, required=False, allow_blank=True)
    pincode = serializers.RegexField(regex=r"^\d{6}$", required=False)
    restaurant_phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    fssai_number = serializers.RegexField(regex=r"^\d{14}$", required=False)
    gst_number = serializers.CharField(max_length=15, required=False, allow_blank=True)
    pan_number = serializers.CharField(max_length=10, required=False, allow_blank=True)
    bank_account_number = serializers.RegexField(regex=r"^\d{9,18}$", required=False, write_only=True)
    bank_ifsc_code = serializers.RegexField(
        regex=r"^[A-Za-z]{4}0[A-Za-z0-9]{6}$",
        max_length=11,
        required=False,
    )
    account_holder_name = serializers.CharField(max_length=120, required=False, allow_blank=True)
    logo = serializers.ImageField(required=False, allow_null=True)
    cover_image = serializers.ImageField(required=False, allow_null=True)
    vehicle_type = serializers.CharField(max_length=40, required=False, allow_blank=True)
    vehicle_number = serializers.CharField(max_length=30, required=False, allow_blank=True)
    license_number = serializers.CharField(max_length=50, required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate_phone(self, value):
        value = value.strip()
        if not re.fullmatch(r"\+?[0-9]{7,15}", value):
            raise serializers.ValidationError("Enter a valid phone number.")
        if CustomerProfile.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError("An account with this phone number already exists.")
        return value

    def validate(self, attrs):
        role = self.context.get("role", "customer")
        required_fields = {
            "restaurant_owner": (
                "restaurant_name",
                "restaurant_type",
                "cuisine_type",
                "restaurant_address",
                "city",
                "state",
                "pincode",
                "restaurant_phone",
                "fssai_number",
                "bank_account_number",
                "bank_ifsc_code",
                "account_holder_name",
            ),
            "delivery_partner": (
                "vehicle_type",
                "vehicle_number",
                "license_number",
                "address",
            ),
        }.get(role, ())
        missing_fields = [
            field for field in required_fields if not attrs.get(field, "").strip()
        ]
        if missing_fields:
            raise serializers.ValidationError({
                field: "This field is required for this account type."
                for field in missing_fields
            })

        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})

        gst_number = attrs.get("gst_number", "").strip().upper()
        if gst_number and not re.fullmatch(r"\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]", gst_number):
            raise serializers.ValidationError({"gst_number": "Enter a valid GST number."})
        attrs["gst_number"] = gst_number
        pan_number = attrs.get("pan_number", "").strip().upper()
        if pan_number and not re.fullmatch(r"[A-Z]{5}\d{4}[A-Z]", pan_number):
            raise serializers.ValidationError({"pan_number": "Enter a valid PAN number."})
        attrs["pan_number"] = pan_number
        if attrs.get("bank_ifsc_code"):
            attrs["bank_ifsc_code"] = attrs["bank_ifsc_code"].strip().upper()

        name_parts = attrs["name"].strip().split(maxsplit=1)
        if not name_parts:
            raise serializers.ValidationError({"name": "Name is required."})

        candidate = User(
            username=attrs["email"],
            email=attrs["email"],
            first_name=name_parts[0],
            last_name=name_parts[1] if len(name_parts) > 1 else "",
        )
        try:
            validate_password(attrs["password"], user=candidate)
        except DjangoValidationError as error:
            raise serializers.ValidationError({"password": error.messages}) from error

        attrs["first_name"] = name_parts[0]
        attrs["last_name"] = name_parts[1] if len(name_parts) > 1 else ""
        attrs["role"] = role
        return attrs

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data["email"],
            email=validated_data["email"],
            first_name=validated_data["first_name"],
            last_name=validated_data["last_name"],
            password=validated_data["password"],
            role=validated_data["role"],
        )
        CustomerProfile.objects.create(
            user=user,
            phone_number=validated_data["phone"],
            address=validated_data.get("address", ""),
        )
        if user.role == "restaurant_owner":
            Restaurant.objects.create(
                owner=user,
                name=validated_data["restaurant_name"],
                cuisine_type=validated_data["cuisine_type"],
                restaurant_type=validated_data["restaurant_type"],
                description=validated_data.get("description", ""),
                address=validated_data["restaurant_address"],
                city=validated_data["city"],
                state=validated_data["state"],
                pincode=validated_data["pincode"],
                phone=validated_data["restaurant_phone"],
                fssai_number=validated_data["fssai_number"],
                gst_number=validated_data.get("gst_number", ""),
                pan_number=validated_data.get("pan_number", ""),
                bank_account_number=validated_data["bank_account_number"],
                bank_ifsc_code=validated_data["bank_ifsc_code"],
                account_holder_name=validated_data["account_holder_name"],
                logo=validated_data.get("logo"),
                image=validated_data.get("cover_image"),
                status="pending",
                is_active=False,
            )
        elif user.role == "delivery_partner":
            DeliveryPartnerProfile.objects.create(
                user=user,
                vehicle_type=validated_data["vehicle_type"],
                vehicle_number=validated_data["vehicle_number"],
                license_number=validated_data["license_number"],
                address=validated_data["address"],
            )
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False, write_only=True)

    def validate(self, attrs):
        user_record = User.objects.filter(email__iexact=attrs["email"].strip()).first()
        user = None
        if user_record is not None:
            user = authenticate(
                request=self.context.get("request"),
                username=user_record.get_username(),
                password=attrs["password"],
            )
        if user is None:
            raise serializers.ValidationError("Invalid email or password.")
        required_role = self.context.get("required_role")
        if required_role and user.role != required_role:
            raise serializers.ValidationError("This account cannot sign in to this portal.")
        attrs["user"] = user
        return attrs


class ProfileUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150, required=False)
    email = serializers.EmailField(required=False)
    phone = serializers.CharField(max_length=15, required=False)
    address = serializers.CharField(required=False, allow_blank=True)
    profile_image = serializers.ImageField(required=False, allow_null=True)

    def validate_email(self, value):
        value = value.strip()
        user = self.context["request"].user
        if User.objects.filter(email__iexact=value).exclude(pk=user.pk).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate_phone(self, value):
        value = value.strip()
        if not re.fullmatch(r"\+?[0-9]{7,15}", value):
            raise serializers.ValidationError("Enter a valid phone number.")
        user = self.context["request"].user
        if CustomerProfile.objects.filter(phone_number=value).exclude(user=user).exists():
            raise serializers.ValidationError("An account with this phone number already exists.")
        return value

    def validate_profile_image(self, value):
        if value and value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("Profile images must be 5 MB or smaller.")
        return value

    def update(self, user, validated_data):
        profile, _ = CustomerProfile.objects.get_or_create(user=user)
        name = validated_data.pop("name", None)
        if name is not None:
            name_parts = name.strip().split(maxsplit=1)
            user.first_name = name_parts[0] if name_parts else ""
            user.last_name = name_parts[1] if len(name_parts) > 1 else ""
            user.save(update_fields=["first_name", "last_name"])

        if "email" in validated_data:
            user.email = validated_data.pop("email")
            user.save(update_fields=["email"])

        for field in ("phone", "address", "profile_image"):
            if field in validated_data:
                model_field = "phone_number" if field == "phone" else field
                setattr(profile, model_field, validated_data[field])
        profile.save()
        return user