"""add foreshadow category and links

Revision ID: add_fs_cat_links
Revises: 
Create Date: 2026-05-16
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_fs_cat_links'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('foreshadows', sa.Column('foreshadow_category', sa.String(20), nullable=False, server_default='chapter'))
    op.create_table(
        'foreshadow_links',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('project_id', sa.String(36), sa.ForeignKey('projects.id'), nullable=False, index=True),
        sa.Column('source_id', sa.String(36), sa.ForeignKey('foreshadows.id'), nullable=False, index=True),
        sa.Column('target_id', sa.String(36), sa.ForeignKey('foreshadows.id'), nullable=False, index=True),
        sa.Column('link_type', sa.String(20), nullable=False),
        sa.Column('strength', sa.Float, server_default='0.5'),
        sa.Column('description', sa.Text, server_default=''),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_foreshadow_links_project', 'foreshadow_links', ['project_id'])
    op.create_index('ix_foreshadow_links_source', 'foreshadow_links', ['source_id'])
    op.create_index('ix_foreshadow_links_target', 'foreshadow_links', ['target_id'])


def downgrade():
    op.drop_table('foreshadow_links')
    op.drop_column('foreshadows', 'foreshadow_category')
