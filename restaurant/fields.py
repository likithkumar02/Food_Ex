import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models


class EncryptedCharField(models.CharField):
    prefix = "fernet:v1:"

    def _cipher(self):
        secret = getattr(settings, "BANK_DATA_ENCRYPTION_KEY", settings.SECRET_KEY)
        key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
        return Fernet(key)

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if not value:
            return value
        token = self._cipher().encrypt(value.encode("utf-8")).decode("ascii")
        return f"{self.prefix}{token}"

    def from_db_value(self, value, expression, connection):
        if not value or not value.startswith(self.prefix):
            return value
        token = value[len(self.prefix):].encode("ascii")
        try:
            return self._cipher().decrypt(token).decode("utf-8")
        except InvalidToken as error:
            raise ValueError("Unable to decrypt the stored bank account number.") from error