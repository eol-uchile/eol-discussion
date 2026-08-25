from django.contrib import admin
from .models import EolForumNotificationsUser, EolForumNotificationsDiscussions
# Register your models here.

class EolForumNotificationsDiscussionsAdmin(admin.ModelAdmin):
    list_display = ('discussion_id', 'course_id', 'daily_threads', 'daily_comment', 'weekly_threads', 'weekly_comment')
    search_fields = ['discussion_id', 'course_id', 'daily_threads', 'daily_comment', 'weekly_threads', 'weekly_comment']

class EolForumNotificationsUserAdmin(admin.ModelAdmin):
    raw_id_fields = ('user', 'discussion')
    list_display = ('user', 'discussion', 'how_often')
    search_fields = ['user__username', 'discussion__course_id', 'how_often']

admin.site.register(EolForumNotificationsDiscussions, EolForumNotificationsDiscussionsAdmin)
admin.site.register(EolForumNotificationsUser, EolForumNotificationsUserAdmin)