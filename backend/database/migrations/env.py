from alembic import context
from backend.database.session import Base, engine
from backend.models import entities
context.configure(connection=engine.connect(), target_metadata=Base.metadata, render_as_batch=True)
with context.begin_transaction():
    context.run_migrations()
