from django.contrib import admin

from .models import ActivityLog


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ('event', 'content_type', 'object_id', 'created_by', 'created_at')
    list_filter = ('event', 'content_type')
    search_fields = ('note', 'changes_summary')
    readonly_fields = [f.name for f in ActivityLog._meta.fields]
    ordering = ('-created_at',)

    def has_add_permission(self, request):
        # السجل بيتكتب من الكود بس (log_activity) — مفيش إدخال يدوي من admin.
        return False
