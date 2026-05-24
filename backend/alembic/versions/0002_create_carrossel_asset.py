"""create carrossel asset table

Revision ID: 0002_create_carrossel_asset
Revises: 0001_create_mvp_tables
Create Date: 2026-05-24
"""
from alembic import op

revision = "0002_create_carrossel_asset"
down_revision = "0001_create_mvp_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE IF NOT EXISTS carrossel_asset (
        id BIGSERIAL PRIMARY KEY,
        carrossel_id BIGINT NOT NULL REFERENCES carrossel(id) ON DELETE CASCADE,
        tipo VARCHAR(50) NOT NULL DEFAULT 'background',
        status VARCHAR(50) NOT NULL DEFAULT 'ATIVO',
        prompt TEXT,
        revised_prompt TEXT,
        asset_path TEXT,
        asset_url TEXT,
        modelo VARCHAR(100),
        provider_response JSONB,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_carrossel_asset_id ON carrossel_asset (id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_carrossel_asset_carrossel_id ON carrossel_asset (carrossel_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS carrossel_asset")
