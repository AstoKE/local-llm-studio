"""Bounded system and inference performance history; never stores prompt content."""
from alembic import op
import sqlalchemy as sa
revision = '0002'
down_revision = '0001'

def upgrade():
    op.create_table('system_samples', sa.Column('id', sa.Integer, primary_key=True), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False), sa.Column('payload', sa.JSON, nullable=False))
    op.create_index('ix_system_samples_created_at', 'system_samples', ['created_at'])
    op.create_table('inference_runs', sa.Column('id', sa.Integer, primary_key=True), sa.Column('job_id', sa.String(32), nullable=False, unique=True), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False), sa.Column('model', sa.String(200), nullable=False), sa.Column('source', sa.String(20), nullable=False), sa.Column('statistics', sa.JSON, nullable=False))
    op.create_index('ix_inference_runs_created_at', 'inference_runs', ['created_at'])
    op.create_index('ix_inference_runs_model', 'inference_runs', ['model'])

def downgrade():
    op.drop_table('inference_runs')
    op.drop_table('system_samples')
