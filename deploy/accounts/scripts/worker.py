"""One bounded, non-overlapping dispatcher; no exception bodies or mail in logs."""

import os
import time
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django

django.setup()
from django.core.management import call_command  # noqa: E402
from django.db import close_old_connections  # noqa: E402

while True:
    try:
        call_command("dispatch_mail", limit=5, verbosity=0)
        Path("/tmp/worker-alive").touch()
    except Exception:
        print("accounts_worker batch_failed", flush=True)
    finally:
        close_old_connections()
    time.sleep(30)
