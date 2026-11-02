import re

from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator

from .models import Restaurant


MAX_RESTAURANT_IMAGE_SIZE = 5 * 1024 * 1024


def validate_restaurant_image_size(upload):
    if upload.size > MAX_RESTAURANT_IMAGE_SIZE:
        raise ValidationError("Images must be 5 MB or smaller.")


class RestaurantRegistrationForm(forms.Form):
    restaurant_name = forms.CharField(max_length=200, label="Restaurant name")
    restaurant_type = forms.ChoiceField(
        choices=Restaurant.RESTAURANT_TYPE_CHOICES,
        label="Restaurant type",
    )
    cuisine_type = forms.CharField(max_length=100, label="Cuisine type")
    restaurant_address = forms.CharField(
        max_length=255,
        widget=forms.Textarea(attrs={"rows": 2}),
        label="Restaurant address",
    )
    city = forms.CharField(max_length=100)
    state = forms.CharField(max_length=100)
    pincode = forms.RegexField(regex=r"^\d{6}$", max_length=6, min_length=6)
    latitude = forms.DecimalField(max_digits=9, decimal_places=6, required=False, widget=forms.HiddenInput())
    longitude = forms.DecimalField(max_digits=9, decimal_places=6, required=False, widget=forms.HiddenInput())
    restaurant_phone = forms.RegexField(
        regex=r"^\+?[0-9]{7,15}$",
        max_length=16,
        label="Restaurant phone",
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    fssai_number = forms.RegexField(
        regex=r"^\d{14}$",
        max_length=14,
        label="FSSAI number",
    )
    gst_number = forms.CharField(max_length=15, required=False, label="GST number (optional)")
    pan_number = forms.CharField(max_length=10, required=False, label="PAN number (optional)")
    bank_account_number = forms.RegexField(
        regex=r"^\d{9,18}$",
        max_length=18,
        label="Bank account number",
    )
    bank_ifsc_code = forms.RegexField(
        regex=r"^[A-Za-z]{4}0[A-Za-z0-9]{6}$",
        max_length=11,
        label="IFSC code",
    )
    account_holder_name = forms.CharField(max_length=120, label="Account holder name")
    logo = forms.ImageField(
        required=False,
        validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"]), validate_restaurant_image_size],
    )
    cover_image = forms.ImageField(
        required=False,
        validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"]), validate_restaurant_image_size],
        label="Restaurant cover image",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = (
                "form-select" if isinstance(field, forms.ChoiceField) else "form-control"
            )

    def clean_fssai_number(self):
        return self.cleaned_data["fssai_number"].strip()

    def clean_gst_number(self):
        value = self.cleaned_data["gst_number"].strip().upper()
        if value and not re.fullmatch(r"\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]", value):
            raise ValidationError("Enter a valid GST number.")
        return value

    def clean_pan_number(self):
        value = self.cleaned_data["pan_number"].strip().upper()
        if value and not re.fullmatch(r"[A-Z]{5}\d{4}[A-Z]", value):
            raise ValidationError("Enter a valid PAN number.")
        return value

    def clean_bank_ifsc_code(self):
        return self.cleaned_data["bank_ifsc_code"].strip().upper()


class RestaurantProfileForm(forms.ModelForm):
    image = forms.ImageField(
        required=False,
        validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"]), validate_restaurant_image_size],
        label="Restaurant cover image",
    )
    logo = forms.ImageField(
        required=False,
        validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"]), validate_restaurant_image_size],
        label="Restaurant logo",
    )

    class Meta:
        model = Restaurant
        fields = (
            "name",
            "restaurant_type",
            "cuisine_type",
            "description",
            "address",
            "city",
            "state",
            "pincode",
            "phone",
            "fssai_number",
            "gst_number",
            "pan_number",
            "bank_ifsc_code",
            "account_holder_name",
            "opening_time",
            "closing_time",
            "is_open",
            "logo",
            "image",
        )
        labels = {"name": "Restaurant name", "phone": "Restaurant phone"}
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "opening_time": forms.TimeInput(attrs={"type": "time"}),
            "closing_time": forms.TimeInput(attrs={"type": "time"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field, forms.BooleanField):
                css_class = "form-check-input"
            elif isinstance(field, forms.ChoiceField):
                css_class = "form-select"
            else:
                css_class = "form-control"
            field.widget.attrs["class"] = css_class

    def clean_pincode(self):
        value = self.cleaned_data["pincode"].strip()
        if value and not re.fullmatch(r"\d{6}", value):
            raise ValidationError("Enter a six-digit pincode.")
        return value

    def clean_fssai_number(self):
        value = self.cleaned_data["fssai_number"].strip()
        if value and not re.fullmatch(r"\d{14}", value):
            raise ValidationError("Enter a 14-digit FSSAI number.")
        return value

    def clean_gst_number(self):
        value = self.cleaned_data["gst_number"].strip().upper()
        if value and not re.fullmatch(r"\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]", value):
            raise ValidationError("Enter a valid GST number.")
        return value

    def clean_pan_number(self):
        value = self.cleaned_data["pan_number"].strip().upper()
        if value and not re.fullmatch(r"[A-Z]{5}\d{4}[A-Z]", value):
            raise ValidationError("Enter a valid PAN number.")
        return value


class RestaurantOwnerAccountForm(forms.Form):
    # Owner personal fields
    first_name = forms.CharField(max_length=30, required=False, label="First Name")
    last_name = forms.CharField(max_length=30, required=False, label="Last Name")
    email = forms.EmailField(required=True, label="Email Address")
    mobile_number = forms.CharField(
        max_length=16,
        required=False,
        label="Owner Mobile Number",
        help_text="Primary phone number for SMS and account notifications.",
    )

    # Restaurant details
    restaurant_name = forms.CharField(max_length=200, label="Restaurant Name")
    restaurant_type = forms.ChoiceField(
        choices=Restaurant.RESTAURANT_TYPE_CHOICES,
        label="Restaurant Type",
    )
    cuisine_type = forms.CharField(max_length=100, label="Cuisine Type")
    phone = forms.CharField(max_length=20, label="Restaurant Contact Phone")
    address = forms.CharField(
        max_length=255,
        widget=forms.Textarea(attrs={"rows": 2}),
        label="Business Address",
    )
    city = forms.CharField(max_length=100, label="City")
    state = forms.CharField(max_length=100, label="State")
    pincode = forms.CharField(max_length=12, label="Pincode")
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Restaurant Description",
    )
    image = forms.ImageField(
        required=False,
        validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"]), validate_restaurant_image_size],
        label="Restaurant Cover Image",
    )
    logo = forms.ImageField(
        required=False,
        validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"]), validate_restaurant_image_size],
        label="Restaurant Logo",
    )

    def __init__(self, *args, user=None, restaurant=None, **kwargs):
        self.user = user
        self.restaurant = restaurant
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field, forms.ChoiceField):
                field.widget.attrs["class"] = "form-select"
            else:
                field.widget.attrs["class"] = "form-control"

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        from accounts.models import User
        query = User.objects.filter(email__iexact=email)
        if self.user:
            query = query.exclude(pk=self.user.pk)
        if query.exists():
            raise ValidationError("An account with this email address already exists.")
        return email

    def clean_mobile_number(self):
        val = self.cleaned_data.get("mobile_number", "").strip()
        if val:
            if not re.fullmatch(r"^\+?[0-9]{7,15}$", val):
                raise ValidationError("Enter a valid mobile number (7 to 15 digits).")
            from customer.models import CustomerProfile
            query = CustomerProfile.objects.filter(phone_number=val)
            if self.user:
                query = query.exclude(user=self.user)
            if query.exists():
                raise ValidationError("This mobile number is already in use by another account.")
        return val

    def clean_pincode(self):
        val = self.cleaned_data.get("pincode", "").strip()
        if val and not re.fullmatch(r"^\d{6}$", val):
            raise ValidationError("Enter a valid 6-digit pincode.")
        return val