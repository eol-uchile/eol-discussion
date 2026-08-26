# Installed packages (via pip)
from django.conf.urls import url
from django.contrib.auth.decorators import login_required

# Internal project dependencies
from eoldiscussion.views import save_notification, save_notification_get, save_notification_post

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
