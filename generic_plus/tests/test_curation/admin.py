from django import forms
from django.contrib import admin
from django.db import models

from .models import Group, Item


class ItemInline(admin.StackedInline):

    model = Item
    fieldsets = (
        (None, {'fields': (
            'position', 'content_object', 'name',
        )}),
    )
    min_num = 1
    extra = 0
    formfield_overrides = {
        models.PositiveSmallIntegerField: {"widget": forms.HiddenInput()}
    }


class GroupAdmin(admin.ModelAdmin):

    inlines = [ItemInline]
    fieldsets = (
        (None, {'fields': ('name',)}),
    )


admin.site.register(Group, GroupAdmin)
