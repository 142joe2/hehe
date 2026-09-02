import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class CoreSystemConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core_system'

    def ready(self):
        pass
