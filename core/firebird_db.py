# core/firebird_db.py
import os
from contextlib import contextmanager
import fdb

CHARSET = os.getenv("FIREBIRD_CHARSET", "UTF8")

# (Opcional) ajuda a achar o fbclient.dll no Windows 3.8+ se você informar a pasta no .env
client_dir = os.getenv("FIREBIRD_CLIENT_DIR")
if client_dir:
    try:
        os.add_dll_directory(client_dir)
    except Exception:
        pass

def get_dsn():
    dsn = os.getenv("FIREBIRD_DSN")
    if not dsn:
        raise RuntimeError("FIREBIRD_DSN não configurado")
    return dsn

@contextmanager
def fb_connect():
    con = fdb.connect(
        dsn=get_dsn(),
        user=os.getenv("FIREBIRD_USER", "SYSDBA"),
        password=os.getenv("FIREBIRD_PASSWORD", "masterkey"),
        charset=CHARSET,
    )
    try:
        yield con
    finally:
        try: con.close()
        except Exception: pass
