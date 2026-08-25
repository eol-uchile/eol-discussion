# eol-discussion
Eol discussion xblock to add new parameters in original edx discussion,  xblock to grade work in discussion and notifications
This XBlock allow to grade the participation in the forum according to the student.


![Coverage Status](/coverage-badge.svg)

![https://github.com/eol-uchile/eol-discussion/actions](https://github.com/eol-uchile/eol-discussion/workflows/Python%20application/badge.svg)


# Install App
```
docker-compose exec cms pip install -e /openedx/requirements/eoldiscussion && docker-compose exec lms pip install -e /openedx/requirements/eoldiscussion
```

# Configuration

Edit *production.py* in *lms and cms settings* and set the limit_thread, this parameter configures the maximum number of publications that are obtained from a discussion.

    EOLGRADEFORUM_LIMIT_THREADS = 5000
    CORS_ALLOW_CREDENTIALS = True
    CORS_ORIGIN_WHITELIST = ['studio.domain.com']
    CORS_ALLOW_HEADERS = corsheaders_default_headers + (
        'use-jwt-cookie',
    )

# Commands

    > docker-compose exec lms python manage.py lms --settings=prod.production discussion_notification daily
    > docker-compose exec lms python manage.py lms --settings=prod.production discussion_notification weekly


# Install

- Edit the following file and add following code _/openedx/edx-platform/lms/djangoapps/discussion/signals/handlers.py_

        @receiver(signals.comment_created)
        def send_discussion_email_notification(sender, user, post, **kwargs):
            with transaction.atomic():
                try:
                    from eol_forum_notifications.models import EolForumNotificationsDiscussions
                    discussion = EolForumNotificationsDiscussions.objects.get(discussion_id=post.thread.commentable_id, course_id=post.thread.course_id)
                    discussion.daily_comment += 1
                    discussion.weekly_comment += 1
                    discussion.save()
                except Exception as e:
                    log.info("EolForumNotifications - Error to increment comment count. discussion_id: {}, course: {}, error: {}".format(
                        post.thread.commentable_id,
                        post.thread.course_id,
                        str(e)))
           
                return

        @receiver(signals.thread_created)
        def eol_thread_created(sender, user, post, **kwargs):
            with transaction.atomic():
                try:
                    from eol_forum_notifications.models import EolForumNotificationsDiscussions
                    discussion = EolForumNotificationsDiscussions.objects.get(discussion_id=post.commentable_id, course_id=post.course_id)
                    discussion.daily_threads += 1
                    discussion.weekly_threads += 1
                    discussion.save()
                except Exception as e:
                    log.info("EolForumNotifications - Error to increment comment count. discussion_id: {}, course: {}, error: {}".format(
                        post.commentable_id,
                        post.course_id,
                        str(e)))
            return

## TESTS
**Prepare tests:**

- Install **act** following the instructions in [https://nektosact.com/installation/index.html](https://nektosact.com/installation/index.html)

**Run tests:**
- In a terminal at the root of the project
    ```
    act -W .github/workflows/pythonapp.yml
    ```
