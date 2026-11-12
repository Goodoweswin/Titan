from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.db import transaction
from django.utils import timezone

from .models import DeviceSession, User


@admin.register(User)
class AccountAdmin(UserAdmin):
    list_display = ("email", "name", "is_active", "verified_at", "date_joined")
    search_fields = ("email", "name")
    fieldsets = UserAdmin.fieldsets + (("Titan", {"fields": ("name", "verified_at")}),)
    readonly_fields = ("verified_at",)
    actions = None

    def get_readonly_fields(self, request, obj=None):
        return self.readonly_fields + (("email", "username") if obj else ())

    def save_model(self, request, obj, form, change):
        with transaction.atomic():
            if change:
                User.objects.select_for_update().get(pk=obj.pk)
            super().save_model(request, obj, form, change)
            if not obj.is_active:
                DeviceSession.objects.filter(user=obj, revoked_at__isnull=True).update(
                    revoked_at=timezone.now()
                )
