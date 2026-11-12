"""Transactional mail outbox. Raw links exist only in pending, access-controlled bodies."""

import secrets
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from .models import MailOutbox, OneTimeToken
from .security import digest


def enqueue_link(user, purpose):
    raw = secrets.token_urlsafe(32)
    expires = timezone.now() + timedelta(minutes=30 if purpose == "reset" else 60)
    OneTimeToken.objects.create(
        digest=digest(raw),
        user=user,
        purpose=purpose,
        expires_at=expires,
        epoch=settings.SESSION_EPOCH,
        credential=user.get_session_auth_hash(),
    )
    route = "reset" if purpose == "reset" else "verify"
    MailOutbox.objects.create(
        recipient=user.email,
        subject="Titan: "
        + ("重设密码" if purpose == "reset" else "验证邮箱"),
        body=f"请打开以下链接继续：\n{settings.ISSUER}/{route}/{raw}\n\n如果并非你本人发起，请忽略此邮件。",
        available_at=timezone.now(),
        expires_at=expires,
    )


def dispatch_batch(limit=10):
    if not 1 <= limit <= 50:
        raise ValueError("Batch limit must be 1–50")
    delivered = 0
    for _ in range(limit):
        with transaction.atomic():
            now = timezone.now()
            row = (
                MailOutbox.objects.select_for_update(skip_locked=True)
                .filter(
                    sent_at__isnull=True,
                    available_at__lte=now,
                    expires_at__gt=now,
                    attempts__lt=5,
                )
                .order_by("created_at")
                .first()
            )
            if row is None:
                break
            row.attempts += 1
            try:
                sent = send_mail(
                    row.subject,
                    row.body,
                    settings.DEFAULT_FROM_EMAIL,
                    [row.recipient],
                    fail_silently=False,
                )
                if sent != 1:
                    raise RuntimeError("Mail adapter did not accept message")
            except Exception:
                # Provider exceptions can contain recipients/credentials; never log their text.
                row.available_at = now + timedelta(
                    seconds=min(3600, 60 * 2**row.attempts)
                )
            else:
                row.sent_at = now
                row.body = ""
                delivered += 1
            row.save()
    MailOutbox.objects.filter(expires_at__lte=timezone.now()).exclude(body="").update(
        body=""
    )
    return delivered
