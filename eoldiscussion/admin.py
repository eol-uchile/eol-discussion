# Installed packages (via pip)
from django.contrib import admin

# Internal project dependencies
from eoldiscussion.models import EolForumNotificationsUser, EolForumNotificationsDiscussions

class EolForumNotificationsDiscussionsAdmin(admin.ModelAdmin):
    list_display = ('discussion_id', 'course_id', 'daily_threads', 'daily_comment', 'weekly_threads', 'weekly_comment')
    search_fields = ['discussion_id', 'course_id', 'daily_threads', 'daily_comment', 'weekly_threads', 'weekly_comment']

class EolForumNotificationsUserAdmin(admin.ModelAdmin):
    raw_id_fields = ('user', 'discussion')
    list_display = ('user', 'discussion', 'how_often')
    search_fields = ['user__username', 'discussion__course_id', 'how_often']

admin.site.register(EolForumNotificationsDiscussions, EolForumNotificationsDiscussionsAdmin)
admin.site.register(EolForumNotificationsUser, EolForumNotificationsUserAdmin)
