#!/usr/bin/env python3
"""Verify upgrade/downgrade and ORM drift in a disposable SQLite database."""
import os
import sys
import tempfile
from pathlib import Path
root=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(root))
os.chdir(root)
with tempfile.TemporaryDirectory(prefix='studio-migration-check-') as directory:
    os.environ['STUDIO_DATABASE_URL']=f'sqlite:///{directory}/test.db'
    os.environ['STUDIO_LAN_MODE']='false'
    os.environ['STUDIO_ADMIN_PASSWORD_HASH']=''
    from alembic import command
    from alembic.config import Config
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from sqlalchemy import inspect, text
    from backend.database.session import Base, engine
    from backend.models import entities
    config=Config(str(root/'alembic.ini'))
    command.upgrade(config,'0001')
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO conversations (id,title,configuration,created_at) VALUES (1,'Migration fixture','{}',CURRENT_TIMESTAMP)"))
        connection.execute(text("INSERT INTO messages (conversation_id,role,content,statistics) VALUES (1,'user','Retain this message','{}')"))
    for revision in ['head','0001','head']:
        (command.downgrade if revision=='0001' else command.upgrade)(config,revision)
        with engine.connect() as connection:
            assert connection.execute(text('SELECT content FROM messages')).scalar_one()=='Retain this message'
    with engine.connect() as connection:
        differences=compare_metadata(MigrationContext.configure(connection),Base.metadata)
        assert not differences,f'ORM/migration drift: {differences}'
        assert connection.execute(text('PRAGMA integrity_check')).scalar_one()=='ok'
    print('PASS: migration round trip preserves chats; schema matches ORM; SQLite integrity ok')
