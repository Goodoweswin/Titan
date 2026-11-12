from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import AdminPasswordChangeForm
from django.db import transaction
from django.utils import timezone

from .models import DeviceSession, User


class CurrentUserPasswordChangeForm(AdminPasswordChangeForm):
    def save(self, commit=True):
        # Django's dedicated admin password view bypasses ModelAdmin.save_model.
        # Reload under the same user-first lock as recovery and token issuance.
        with transaction.atomic():
            self.user = User.objects.select_for_update().get(pk=self.user.pk)
            user = super().save(commit=False)
            if commit:
                user.save(update_fields=["password"])
            return user


@admin.register(User)
class AccountAdmin(UserAdmin):
    list_display = ("email", "name", "is_active", "verified_at", "admin_provisioned", "date_joined")
    search_fields = ("email", "name")
    fieldsets = UserAdmin.fieldsets + (("Titan", {"fields": ("name", "verified_at", "admin_provisioned")}),)
    readonly_fields = ("verified_at", "admin_provisioned", "last_login", "date_joined")
    change_password_form = CurrentUserPasswordChangeForm
    actions = None

    def get_readonly_fields(self, request, obj=None):
        return self.readonly_fields + (("email", "username") if obj else ())

    def save_model(self, request, obj, form, change):
        with transaction.atomic():
            if change:
                if form is None:
                    raise ValueError(
                        "Account changes require validated form change metadata."
                    )
                current = User.objects.select_for_update().get(pk=obj.pk)
                # Only form-declared edits can overwrite the locked state. Password,
                # auth_version, verification and login metadata never come from this
                # form; in particular, unchanged old is_active must not re-enable.
                editable = {
                    "name",
                    "first_name",
                    "last_name",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                }
                changed = set(form.changed_data) & editable
                for name in changed:
                    setattr(current, name, getattr(obj, name))
                if changed:
                    current.save(update_fields=changed)
                # Keep the object used by admin/form logging and save_related current.
                obj.refresh_from_db()
            else:
                super().save_model(request, obj, form, change)
            if not obj.is_active:
                DeviceSession.objects.filter(user=obj, revoked_at__isnull=True).update(
                    revoked_at=timezone.now()
                )

    def save_related(self, request, form, formsets, change):
        if not change:
            return super().save_related(request, form, formsets, change)
        # ModelForm.save_m2m otherwise rewrites even unchanged old groups/permissions.
        # The standard admin change view retains the user row lock until this ends.
        original_data = form.cleaned_data
        unchanged = {field.name for field in User._meta.many_to_many} - set(
            form.changed_data
        )
        form.cleaned_data = {
            key: value for key, value in original_data.items() if key not in unchanged
        }
        try:
            return super().save_related(request, form, formsets, change)
        finally:
            form.cleaned_data = original_data
