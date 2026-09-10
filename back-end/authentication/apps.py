import sqlite3

from django.apps import AppConfig
from django.db.backends.signals import connection_created



class AuthenticationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'authentication'

    def ready(self):
        connection_created.connect(_sqlite_wal)



def _sqlite_wal(sender, connection, **kwargs):
    """
    Let readers keep working while somebody is writing.

    In SQLite's default journal mode a write blocks every read for its duration, and this
    product holds a request open for the length of a streamed answer. One trader confirming
    a file was enough to stall everyone else on the box.

    WAL does not make SQLite a multi-user database - only PostgreSQL does that, and settings
    switches to it on one environment variable - but it removes the cheapest way to hit
    "database is locked" while there is still one process.
    """
    if connection.vendor != 'sqlite':
        return

    try:
        with connection.cursor() as cursor:
            cursor.execute('PRAGMA journal_mode=WAL;')
            # Wait for a writer rather than failing the moment the lock is held.
            cursor.execute('PRAGMA busy_timeout=20000;')
    except sqlite3.Error:
        # An in-memory test database refuses WAL, and that is not a reason to fail to boot.
        pass
