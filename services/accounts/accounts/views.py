import uuid

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.hashers import make_password
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .forms import EmailForm, LoginForm, RegistrationForm, ResetForm
from .mail import enqueue_link
from .models import DeviceSession, OneTimeToken, User
from .policy import account_eligible
from .security import digest, error, rate_limit


def safe_next(request):
    value = (
        request.POST.get("next")
        or request.GET.get("next")
        or request.session.get("pending_next", "")
    )
    return (
        value
        if value.startswith("/o/authorize/?")
        and "\\" not in value
        and len(value) <= 4096
        else "/complete"
    )


def page(request, title, form=None, message="", status=200):
    return render(
        request,
        "accounts/form.html",
        {
            "title": title, "form": form, "message": message, "next": safe_next(request),
            "managed": settings.ACCOUNT_MODE == "managed",
        },
        status=status,
    )


def limited(request, action):
    return not rate_limit(request, action, request.POST.get("email", ""), limit=10)


@require_http_methods(["GET", "POST"])
def register(request):
    if settings.ACCOUNT_MODE == "managed":
        return managed_unavailable(request)
    form = RegistrationForm(request.POST or None)
    if request.method == "POST":
        if limited(request, "register"):
            return error("rate_limited", "操作过于频繁，请稍后重试。", 429)
        if not form.is_valid():
            return page(request, "注册账户", form, status=400)
        data = form.cleaned_data
        password_hash = make_password(
            data["password"]
        )  # same expensive work for duplicate registrations
        with transaction.atomic():
            try:
                with transaction.atomic():
                    user = User.objects.create(
                        username=str(uuid.uuid4()),
                        email=data["email"],
                        name=data["name"],
                        password=password_hash,
                    )
            except IntegrityError:
                user = None
            if user:
                enqueue_link(user, "verify")
        request.session["pending_next"] = safe_next(request)
        return page(
            request,
            "请查收邮件",
            message="如果此邮箱可以注册，你将收到验证邮件。你也可以登录或找回密码。",
        )
    return page(request, "注册账户", form)


@require_http_methods(["GET", "POST"])
def sign_in(request):
    form = LoginForm(request.POST or None)
    if request.method == "POST":
        if limited(request, "login"):
            return error("rate_limited", "操作过于频繁，请稍后重试。", 429)
        if form.is_valid():
            email = form.cleaned_data["email"].strip().lower()
            user = User.objects.filter(email=email).first()
            authenticated = authenticate(
                request,
                username=user.username if user else "missing-user",
                password=form.cleaned_data["password"],
            )
            if authenticated and (
                settings.ACCOUNT_MODE != "managed" or account_eligible(authenticated)
            ):
                destination = safe_next(request)
                login(request, authenticated)
                request.session["auth_time"] = int(timezone.now().timestamp())
                request.session["epoch"] = settings.SESSION_EPOCH
                return redirect(destination)
        return page(
            request,
            "登录",
            form,
            message="邮箱或密码不正确。",
            status=400,
        )
    return page(request, "登录", form)


@require_http_methods(["GET", "POST"])
def recover(request):
    return request_email(request, "reset")


@require_http_methods(["GET", "POST"])
def resend(request):
    return request_email(request, "verify")


def managed_unavailable(request):
    return page(
        request, "请联系管理员", message="账号由管理员开通；密码问题请联系管理员。", status=403
    )


def request_email(request, purpose):
    if settings.ACCOUNT_MODE == "managed":
        return managed_unavailable(request)
    request.session["pending_next"] = safe_next(request)
    form = EmailForm(request.POST or None)
    if request.method == "POST":
        if limited(request, "email-" + purpose):
            return error("rate_limited", "操作过于频繁，请稍后重试。", 429)
        if not form.is_valid():
            return page(request, "发送邮件链接", form, status=400)
        with transaction.atomic():
            user = (
                User.objects.select_for_update()
                .filter(
                    email=form.cleaned_data["email"].strip().lower(), is_active=True
                )
                .first()
            )
            if user and (purpose == "reset" or not user.verified_at):
                enqueue_link(user, purpose)
        return page(
            request,
            "请查收邮件",
            message="如果此邮箱符合条件，你将收到一封邮件，请稍后查收。",
        )
    return page(
        request,
        "找回密码" if purpose == "reset" else "重新发送验证邮件",
        form,
    )


def consume(request, raw, purpose):
    if settings.ACCOUNT_MODE == "managed":
        return managed_unavailable(request)
    form = ResetForm(request.POST or None) if purpose == "reset" else None
    if request.method == "GET":
        return page(
            request, "重设密码" if purpose == "reset" else "确认邮箱", form
        )
    if not rate_limit(request, "consume", limit=30):
        return error("rate_limited", "操作过于频繁，请稍后重试。", 429)
    if form and not form.is_valid():
        return page(request, "重设密码", form, status=400)
    reference = OneTimeToken.objects.filter(pk=digest(raw), purpose=purpose).first()
    if reference:
        with transaction.atomic():
            user = User.objects.select_for_update().get(pk=reference.user_id)
            link = OneTimeToken.objects.select_for_update().get(pk=reference.pk)
            now = timezone.now()
            if (
                user.is_active
                and link.consumed_at is None
                and link.expires_at > now
                and link.epoch == settings.SESSION_EPOCH
                and link.credential == user.get_session_auth_hash()
            ):
                if purpose == "verify":
                    user.verified_at = now
                    user.save(update_fields=["verified_at"])
                else:
                    user.set_password(form.cleaned_data["password"])
                    user.save(update_fields=["password"])
                    DeviceSession.objects.filter(
                        user=user, revoked_at__isnull=True
                    ).update(revoked_at=now)
                    continuation = safe_next(request)
                    logout(request)
                    request.session["pending_next"] = continuation
                OneTimeToken.objects.filter(
                    user=user, purpose=purpose, consumed_at__isnull=True
                ).update(consumed_at=now)
                return page(
                    request,
                    "邮箱已验证" if purpose == "verify" else "密码已更新",
                    message="现在可以登录并返回 Titan。",
                )
    return page(
        request,
        "链接不可用",
        message="此链接已过期或已使用，请重新申请邮件。",
        status=400,
    )


@require_http_methods(["GET", "POST"])
def verify(request, raw):
    return consume(request, raw, "verify")


@require_http_methods(["GET", "POST"])
def reset(request, raw):
    return consume(request, raw, "reset")


@require_http_methods(["POST"])
def sign_out(request):
    logout(request)
    return redirect("/login")


@require_http_methods(["GET"])
def complete(request):
    return page(
        request,
        "返回 Titan",
        message="浏览器登录已完成。请返回 Titan，继续或重新发起账户登录。",
    )


@require_http_methods(["GET"])
def health_live(request):
    return JsonResponse({"status": "ok"})


@require_http_methods(["GET"])
def health_ready(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError:
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})
