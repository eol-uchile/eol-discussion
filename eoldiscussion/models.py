from django.contrib.auth.models import User
from django.db import models
import datetime
from opaque_keys.edx.django.models import CourseKeyField, UsageKeyField

# Create your models here.

class EolForumNotificationsDiscussions(models.Model):
    class Meta:
        index_together = [
            ["discussion_id", "course_id"],
        ]
        unique_together = [
            ["discussion_id", "course_id"],
        ]

    discussion_id = models.CharField(blank=False, max_length=255, db_index=True)
    course_id = CourseKeyField(max_length=255)
    block_key = UsageKeyField(max_length=255, default=None)
    daily_threads = models.IntegerField(default=0)
    daily_comment = models.IntegerField(default=0)
    weekly_threads = models.IntegerField(default=0)
    weekly_comment = models.IntegerField(default=0)

    def __str__(self):
        return '%s - %s' % (self.discussion_id, self.course_id)

class EolForumNotificationsUser(models.Model):
    HOW_OFTEN_CHOICES = (("never", "never"), ("daily", "daily"), ("weekly", "weekly") )
    class Meta:
        index_together = [
            ["discussion", "user"],
        ]
        unique_together = [
            ["discussion", "user"],
        ]
    
    user = models.ForeignKey(User, db_index=True, on_delete=models.CASCADE)
    discussion = models.ForeignKey(EolForumNotificationsDiscussions, db_index=True, on_delete=models.CASCADE)
    how_often = models.TextField(choices=HOW_OFTEN_CHOICES, default='never')