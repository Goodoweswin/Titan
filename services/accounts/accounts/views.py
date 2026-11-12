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
        {"title": title, "form": form, "message": message, "next": safe_next(request)},
        status=status,
    )


def limited(request, action):
    return not rate_limit(request, action, request.POST.get("email", ""), limit=10)


@require_http_methods(["GET", "POST"])
def register(request):
    form = RegistrationForm(request.POST or None)
    if request.method == "POST":
        if limited(request, "register"):
            return error("rate_limited", "Try again later.", 429)
        if not form.is_valid():
            return page(request, "Create account", form, status=400)
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
            "Check your email",
            message="If this address can be registered, a verification email will arrive. You can also sign in or recover your password.",
        )
    return page(request, "Create account", form)


@require_http_methods(["GET", "POST"])
def sign_in(request):
    form = LoginForm(request.POST or None)
    if request.method == "POST":
        if limited(request, "login"):
            return error("rate_limited", "Try again later.", 429)
        if form.is_valid():
            email = form.cleaned_data["email"].strip().lower()
            user = User.objects.filter(email=email).first()
            authenticated = authenticate(
                request,
                username=user.username if user else "missing-user",
                password=form.cleaned_data["password"],
            )
            if authenticated:
                destination = safe_next(request)
                login(request, authenticated)
                request.session["auth_time"] = int(timezone.now().timestamp())
                request.session["epoch"] = settings.SESSION_EPOCH
                return redirect(destination)
        return page(
            request,
            "Sign in",
            form,
            message="Email or password is incorrect.",
            status=400,
        )
    return page(request, "Sign in", form)


@require_http_methods(["GET", "POST"])
def recover(request):
    return request_email(request, "reset")


@require_http_methods(["GET", "POST"])
def resend(request):
    return request_email(request, "verify")


def request_email(request, purpose):
    request.session["pending_next"] = safe_next(request)
    form = EmailForm(request.POST or None)
    if request.method == "POST":
        if limited(request, "email-" + purpose):
            return error("rate_limited", "Try again later.", 429)
        if not form.is_valid():
            return page(request, "Email link", form, status=400)
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
            "Check your email",
            message="If this address is eligible, an email will arrive shortly.",
        )
    return page(
        request,
        "Recover password" if purpose == "reset" else "Resend verification",
        form,
    )


def consume(request, raw, purpose):
    form = ResetForm(request.POST or None) if purpose == "reset" else None
    if request.method == "GET":
        return page(
            request, "Reset password" if purpose == "reset" else "Confirm email", form
        )
    if not rate_limit(request, "consume", limit=30):
        return error("rate_limited", "Try again later.", 429)
    if form and not form.is_valid():
        return page(request, "Reset password", form, status=400)
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
                    "Email verified" if purpose == "verify" else "Password changed",
                    message="You can now sign in and return to Titan.",
                )
    return page(
        request,
        "Link unavailable",
        message="This link has expired or has already been used. Request a new email.",
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
        "Return to Titan",
        message="Sign-in is ready. Return to Titan to start or continue account login.",
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
