#!/usr/bin/env python3
"""Run from repository root with .venv/bin/python scripts/password_hash.py."""
import getpass
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from backend.services.auth import hash_password
password=getpass.getpass('Administrator password (12+ characters): ')
if password!=getpass.getpass('Repeat password: '):
    raise SystemExit('Passwords do not match.')
print('STUDIO_ADMIN_PASSWORD_HASH='+hash_password(password))
