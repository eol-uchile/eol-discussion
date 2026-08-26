# Installed packages (via pip)
from django.contrib import admin

# Internal project dependencies
from eoldiscussion.models import EolDiscussionXBlockNotificationUser, EolDiscussionXBlockNotification

class EolDiscussionXBlockNotificationAdmin(admin.ModelAdmin):
    list_display = ('discussion_id', 'course_id', 'daily_threads', 'daily_comment', 'weekly_threads', 'weekly_comment')
    search_fields = ['discussion_id', 'course_id', 'daily_threads', 'daily_comment', 'weekly_threads', 'weekly_comment']

class EolDiscussionXBlockNotificationUserAdmin(admin.ModelAdmin):
    raw_id_fields = ('user', 'discussion_notification')
    list_display = ('user', 'discussion_notification', 'how_often')
    search_fields = ['user__username', 'discussion_notification__course_id', 'how_often']

admin.site.register(EolDiscussionXBlockNotification, EolDiscussionXBlockNotificationAdmin)
admin.site.register(EolDiscussionXBlockNotificationUser, EolDiscussionXBlockNotificationUserAdmin)
