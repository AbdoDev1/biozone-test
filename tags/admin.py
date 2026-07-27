from django.contrib import admin

from .models import Tag, TaggedItem


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'color', 'created_at')
    search_fields = ('name',)
    list_filter = ('color',)


@admin.register(TaggedItem)
class TaggedItemAdmin(admin.ModelAdmin):
    list_display = ('tag', 'content_type', 'object_id', 'created_by', 'created_at')
    list_filter = ('content_type', 'tag')
