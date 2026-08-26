# Installed packages (via pip)
from django.apps import AppConfig

# Edx dependencies
from openedx.core.djangoapps.plugins.constants import (
    PluginSettings,
    PluginURLs,
    ProjectType,
    SettingsType,
)

class EolDiscussionConfig(AppConfig):
    name = 'eoldiscussion'
    plugin_app = {
        PluginURLs.CONFIG: {
            ProjectType.LMS: {
                PluginURLs.NAMESPACE: "eol_discussion_notification",
                PluginURLs.REGEX: r"^eol_discussion_notification/",
                PluginURLs.RELATIVE_PATH: "urls",
            }},
        PluginSettings.CONFIG: {
            ProjectType.CMS: {
                SettingsType.COMMON: {
                    PluginSettings.RELATIVE_PATH: "settings.common",
                    }
                },
            ProjectType.LMS: {
                SettingsType.COMMON: {
                    PluginSettings.RELATIVE_PATH: "settings.common"
                    },
            },
        }
    }
    
    
