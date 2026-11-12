import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models, transaction
from django.utils.crypto import salted_hmac


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=60)
    verified_at = models.DateTimeField(null=True, blank=True)
    admin_provisioned = models.BooleanField(default=False)
    auth_version = models.UUIDField(default=uuid.uuid4, editable=False)

    def save(self, *args, **kwargs):
        self.email = self.email.strip().lower()
        fields = kwargs.get("update_fields")
        if self._state.adding:
            return super().save(*args, **kwargs)
        # Serialize trust changes with issuance/reset. A stale full save must not
        # restore the credential version from before revocation and reapproval.
        with transaction.atomic():
            current = (
                type(self).objects.select_for_update().filter(pk=self.pk)
                .values("is_active", "admin_provisioned", "auth_version").first()
            )
            if current:
                disabled = (
                    current["is_active"] and not self.is_active
                    and (fields is None or "is_active" in fields)
                )
                approval_changed = (
                    current["admin_provisioned"] != self.admin_provisioned
                    and (fields is None or "admin_provisioned" in fields)
                )
                self.auth_version = current["auth_version"]
                if disabled or approval_changed:
                    self.auth_version = uuid.uuid4()
                    if fields is not None:
                        kwargs["update_fields"] = set(fields) | {"auth_version"}
            return super().save(*args, **kwargs)

    def _get_session_auth_hash(self, secret=None):
        # Disabling or changing approval permanently changes both
        # browser and desktop credential fingerprints, even after re-enabling.
        return salted_hmac(
            "accounts.User.session_auth_hash",
            f"{self.password}:{self.auth_version}",
            secret=secret,
            algorithm="sha256",
        ).hexdigest()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                models.functions.Lower("email"), name="accounts_email_ci_unique"
            )
        ]


class DeviceSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now_add=True)
    auth_time = models.DateTimeField()
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    epoch = models.CharField(max_length=128)
    credential = models.CharField(max_length=128)
    label = models.CharField(max_length=80, default="Titan Desktop")
    platform = models.CharField(max_length=32, default="desktop")


class TokenBinding(models.Model):
    digest = models.CharField(max_length=64, primary_key=True)
    session = models.ForeignKey(DeviceSession, on_delete=models.CASCADE)
    kind = models.CharField(max_length=8)
    consumed_at = models.DateTimeField(null=True)


class GrantContext(models.Model):
    digest = models.CharField(max_length=64, primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    auth_time = models.DateTimeField()
    epoch = models.CharField(max_length=128)
    credential = models.CharField(max_length=128)
    label = models.CharField(max_length=80, default="Titan Desktop")
    platform = models.CharField(max_length=32, default="desktop")
    created_at = models.DateTimeField(auto_now_add=True)


class OneTimeToken(models.Model):
    digest = models.CharField(max_length=64, primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    purpose = models.CharField(max_length=8)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True)
    epoch = models.CharField(max_length=128)
    credential = models.CharField(max_length=128)


class RateLimit(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    started_at = models.DateTimeField()
    count = models.PositiveIntegerField(default=0)


class MailOutbox(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.EmailField()
    subject = models.CharField(max_length=160)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    available_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    attempts = models.PositiveIntegerField(default=0)
    sent_at = models.DateTimeField(null=True)
