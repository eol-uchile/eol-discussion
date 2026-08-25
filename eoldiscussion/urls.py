

from django.conf.urls import url
from django.conf import settings

from .views import save_notification, save_notification_get, save_notification_post

from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt

urlpatterns = (
    url(
        r'^save/',
        login_required(save_notification),
        name='save',
    ),
    url(
        r'^get_save/',
        login_required(save_notification_get),
        name='save_get',
    ),
    url(
        r'^post_save/',
        login_required(save_notification_post),
        name='save_post',
    ),
)
