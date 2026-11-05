"""Initial local persistence schema."""
from alembic import op
import sqlalchemy as sa
revision = '0001'
down_revision = None

def upgrade():
    op.create_table('conversations', sa.Column('id', sa.Integer, primary_key=True), sa.Column('title', sa.String(200), nullable=False), sa.Column('model', sa.String(200)), sa.Column('configuration', sa.JSON, nullable=False), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_table('messages', sa.Column('id', sa.Integer, primary_key=True), sa.Column('conversation_id', sa.Integer, sa.ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False), sa.Column('role', sa.String(20), nullable=False), sa.Column('content', sa.Text, nullable=False), sa.Column('statistics', sa.JSON, nullable=False))
    op.create_table('records', sa.Column('id', sa.Integer, primary_key=True), sa.Column('kind', sa.String(50), nullable=False), sa.Column('name', sa.String(200), nullable=False), sa.Column('payload', sa.JSON, nullable=False), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_records_kind', 'records', ['kind'])

def downgrade():
    for table in ['records', 'messages', 'conversations']:
        op.drop_table(table)
