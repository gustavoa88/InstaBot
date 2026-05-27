"""create mvp tables

Revision ID: 0001_create_mvp_tables
Revises:
Create Date: 2026-05-24
"""
from alembic import op

revision = "0001_create_mvp_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE IF NOT EXISTS carrossel (
        id BIGSERIAL PRIMARY KEY,
        titulo VARCHAR(200),
        ideia_original TEXT NOT NULL,
        status VARCHAR(50) NOT NULL DEFAULT 'RASCUNHO',
        tema VARCHAR(100),
        tom VARCHAR(100),
        publico_alvo VARCHAR(150),
        quantidade_slides INT DEFAULT 7,
        legenda TEXT,
        hashtags TEXT[],
        prompt_config JSONB,
        ia_resultado JSONB,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    )
    """)
    op.execute("ALTER TABLE carrossel ADD COLUMN IF NOT EXISTS quantidade_slides INT DEFAULT 7")
    op.execute("ALTER TABLE carrossel ADD COLUMN IF NOT EXISTS legenda TEXT")
    op.execute("ALTER TABLE carrossel ADD COLUMN IF NOT EXISTS hashtags TEXT[]")
    op.execute("ALTER TABLE carrossel ADD COLUMN IF NOT EXISTS prompt_config JSONB")
    op.execute("ALTER TABLE carrossel ADD COLUMN IF NOT EXISTS ia_resultado JSONB")
    op.execute("ALTER TABLE carrossel ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW()")
    op.execute("ALTER TABLE carrossel ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()")
    op.execute("ALTER TABLE carrossel ALTER COLUMN status SET DEFAULT 'RASCUNHO'")
    op.execute("CREATE INDEX IF NOT EXISTS ix_carrossel_id ON carrossel (id)")

    op.execute("""
    CREATE TABLE IF NOT EXISTS carrossel_slide (
        id BIGSERIAL PRIMARY KEY,
        carrossel_id BIGINT NOT NULL REFERENCES carrossel(id) ON DELETE CASCADE,
        numero_slide INT NOT NULL,
        titulo TEXT,
        texto_principal TEXT,
        texto_secundario TEXT,
        observacao_visual TEXT,
        imagem_path TEXT,
        imagem_url TEXT,
        layout_config JSONB,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_carrossel_slide_id ON carrossel_slide (id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_carrossel_slide_carrossel_id ON carrossel_slide (carrossel_id)")

    op.execute("""
    CREATE TABLE IF NOT EXISTS log_execucao (
        id BIGSERIAL PRIMARY KEY,
        carrossel_id BIGINT,
        etapa VARCHAR(100),
        status VARCHAR(50),
        mensagem TEXT,
        detalhes JSONB,
        created_at TIMESTAMP DEFAULT NOW()
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_log_execucao_id ON log_execucao (id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_log_execucao_carrossel_id ON log_execucao (carrossel_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS log_execucao")
    op.execute("DROP TABLE IF EXISTS carrossel_slide")
    op.execute("DROP TABLE IF EXISTS carrossel")
