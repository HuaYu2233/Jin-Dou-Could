import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests._env import setup_env

setup_env()

from app.core.celery_app import celery_app


def test_task_modules_are_included():
    assert "app.tasks.thumbnail_tasks" in celery_app.conf.include
    assert "app.tasks.email_tasks" in celery_app.conf.include
    assert "app.tasks.alert_tasks" in celery_app.conf.include
    assert "app.tasks.backup_tasks" in celery_app.conf.include


def test_worker_registers_all_tasks():
    celery_app.loader.import_default_modules()
    registered = set(celery_app.tasks.keys())
    assert "tasks.generate_thumbnail" in registered
    assert "tasks.send_verification_email" in registered
    assert "tasks.send_alert_email" in registered
    assert "tasks.send_alert_webhook" in registered
    assert "tasks.trigger_backup" in registered
