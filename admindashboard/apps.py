# admindashboard/apps.py

from django.apps import AppConfig


class AdmindashboardConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'admindashboard'

    def ready(self):
        import os

        # Django's dev server (runserver) spawns TWO processes:
        #   1. The reloader/watcher process  → RUN_MAIN is not set
        #   2. The actual server process     → RUN_MAIN = 'true'
        #
        # We ONLY start the scheduler in the actual server process.
        # In production (gunicorn/waitress) RUN_MAIN is never set,
        # so we also allow it there.
        #
        # This guarantees exactly ONE scheduler thread runs.

        is_reloader_process = (
            os.environ.get('RUN_MAIN') is None
            and os.environ.get('DJANGO_SETTINGS_MODULE') is not None
            # runserver sets RUN_MAIN='true' in the child — absence means reloader
            and 'runserver' in ' '.join(os.sys.argv)
        )

        if is_reloader_process:
            # This is the reloader parent — skip scheduler
            return

        from admindashboard.auto_reject import start_scheduler
        start_scheduler()