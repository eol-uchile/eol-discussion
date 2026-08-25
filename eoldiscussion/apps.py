from django.apps import AppConfig

from openedx.core.djangoapps.plugins.constants import (
    PluginSettings,
    PluginURLs,
    ProjectType,
    SettingsType,
)


class EolDiscussionConfig(AppConfig):
    name = 'eoldiscussion'
    plugin_app = {
        PluginSettings.CONFIG: {
            ProjectType.CMS: {
                SettingsType.COMMON: {
                    PluginSettings.RELATIVE_PATH: "settings.common",
                    PluginURLs.RELATIVE_PATH: "urls"
                    }
                    
                },
            ProjectType.LMS: {
                SettingsType.COMMON: {
                    PluginSettings.RELATIVE_PATH: "settings.common"}
                    },
        },
    }
