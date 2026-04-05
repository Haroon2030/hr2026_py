from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'
    label = 'core'
    verbose_name = 'النظام الأساسي'
    verbose_name_plural = 'النظام الأساسي'

    def ready(self):
        import apps.core.signals  # noqa: F401
