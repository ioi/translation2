from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django import forms
from django.http.response import HttpResponseRedirect
from django.urls.base import reverse
from django.utils.html import mark_safe
from import_export.admin import ImportExportMixin, ImportExportModelAdmin
from import_export.resources import ModelResource
from import_export.fields import Field
from import_export.widgets import ForeignKeyWidget
import import_export.tmp_storages
from trans.utils.notification import reset_notification_cache
from .models import *
from django.shortcuts import render

class UserCreationForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('username',)

    def save(self, commit=True):
        # Save the provided password in hashed format
        user = super(UserCreationForm, self).save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user


class CustomUserResource(ModelResource):
    raw_password = Field('raw_password')

    class Meta:
        model = User
        fields = ('username', 'country', 'language', 'raw_password', 'is_onsite', 'is_translating')
        import_id_fields = ('username',)

class ContestantInline(admin.TabularInline):
    model = Contestant

@admin.register(User)
class CustomUserAdmin(ImportExportMixin, UserAdmin):
    # The forms to add and change user instances
    add_form = UserCreationForm
    resource_class = CustomUserResource
    list_display = ("username", "translate_versions", "country", "language", 'is_onsite', 'is_translating')
    ordering = ("username",)

    tmp_storage_class = import_export.tmp_storages.MediaStorage

    fieldsets = (
        (None, {'fields': ('username', 'text_font_base64', 'text_font_name', 'password', 'language', 'country', 'is_onsite', 'is_translating')}),
        )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password', 'language', 'country', 'is_onsite', 'is_translating', 'is_superuser', 'is_staff', 'is_active')}
            ),
        )

    filter_horizontal = ()

    inlines = (ContestantInline, )

    def translate_versions(self, obj):
        return mark_safe('<a href="%s">%s</a>' % (reverse('user_trans', kwargs={'username': obj.username}), 'Translations'))



class LanguageResource(ModelResource):
    class Meta:
        model = Language
        fields = ('code', 'name', 'rtl',)
        import_id_fields = ('code',)


@admin.register(Language)
class LanguageAdmin(ImportExportModelAdmin):
    resource_class = LanguageResource
    list_display = ['code', 'name', 'direction']
    ordering = ['code']

    tmp_storage_class = import_export.tmp_storages.MediaStorage

@admin.register(UserContest)
class UserContestAdmin(admin.ModelAdmin):
    list_display = [
        'user',
        'contest',
        'frozen',
        'sealed',
        'note',
    ]
    ordering = ['contest', 'user']

class CountryResource(ModelResource):
    class Meta:
        model = Country
        fields = ('code', 'code2', 'name')
        import_id_fields = ('code',)

@admin.register(Country)
class CountryAdmin(ImportExportModelAdmin):
    resource_class = CountryResource
    list_display = ['code', 'code2', 'name']
    ordering = ['code']

    tmp_storage_class = import_export.tmp_storages.MediaStorage

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'description', 'create_time']
    ordering = ['create_time']

class ContestantResource(ModelResource):
    user = Field(
        column_name='user',
        attribute='user',
        widget=ForeignKeyWidget(User, 'username'),
    )

    class Meta:
        model = Contestant
        fields = ('code', 'name', 'on_site', 'user')
        import_id_fields = ('code',)

@admin.register(Contestant)
class ContestantAdmin(ImportExportModelAdmin):
    resource_class = ContestantResource
    list_display = ['code', 'name', 'on_site', 'user']
    ordering = ['code']

    tmp_storage_class = import_export.tmp_storages.MediaStorage


@admin.register(ContestantContest)
class ContestantContestAdmin(admin.ModelAdmin):
    list_display = ['ident', 'translation_by_user']
    list_select_related = ['contestant', 'contest']
    ordering = ['contest__title', 'contestant__code']

    @admin.display(description='Ident')
    def ident(self, obj):
        site = ' (remote)' if not obj.contestant.on_site else ""
        return f'{obj.contest.title}: {obj.contestant.code}{site}'


admin.site.register(Attachment)
admin.site.register(Contest)
admin.site.register(FlatPage)
admin.site.register(Task)
admin.site.register(Translation, ordering=['task__name', 'user__username'])
admin.site.register(Version)
