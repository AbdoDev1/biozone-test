from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'recipient', 'kind', 'is_read', 'created_at')
    list_filter = ('kind', 'is_read')
    search_fields = ('title', 'message', 'recipient__username')
    date_hierarchy = 'created_at'
