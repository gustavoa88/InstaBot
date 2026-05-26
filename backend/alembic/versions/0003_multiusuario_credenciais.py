"""multiusuario credenciais

Revision ID: 0003_multiusuario_credenciais
Revises: 0002_create_carrossel_asset
Create Date: 2026-05-25
"""
import os

from alembic import op

revision = "0003_multiusuario_credenciais"
down_revision = "0002_create_carrossel_asset"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE IF NOT EXISTS usuario (
        id BIGSERIAL PRIMARY KEY,
        email VARCHAR(255) NOT NULL UNIQUE,
        nome VARCHAR(150) NOT NULL,
        senha_hash TEXT NOT NULL,
        is_admin BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_usuario_id ON usuario (id)")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_usuario_email ON usuario (email)")

    op.execute("""
    CREATE TABLE IF NOT EXISTS usuario_configuracao (
        usuario_id BIGINT PRIMARY KEY REFERENCES usuario(id) ON DELETE CASCADE,
        openai_api_key_encrypted TEXT,
        instagram_access_token_encrypted TEXT,
        instagram_user_id_encrypted TEXT,
        facebook_page_id_encrypted TEXT,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    )
    """)

    admin_email = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "admin@example.com").strip().lower()
    op.execute(f"""
    INSERT INTO usuario (email, nome, senha_hash, is_admin)
    SELECT '{admin_email}', 'Admin', 'bootstrap-password-not-initialized', TRUE
    WHERE NOT EXISTS (SELECT 1 FROM usuario WHERE email = '{admin_email}')
    """)

    op.execute("ALTER TABLE carrossel ADD COLUMN IF NOT EXISTS usuario_id BIGINT")
    op.execute(f"""
    UPDATE carrossel
    SET usuario_id = (SELECT id FROM usuario WHERE email = '{admin_email}' ORDER BY id ASC LIMIT 1)
    WHERE usuario_id IS NULL
    """)
    op.execute("ALTER TABLE carrossel ALTER COLUMN usuario_id SET NOT NULL")
    op.execute("""
    ALTER TABLE carrossel
    ADD CONSTRAINT fk_carrossel_usuario
    FOREIGN KEY (usuario_id) REFERENCES usuario(id) ON DELETE CASCADE
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_carrossel_usuario_id ON carrossel (usuario_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_carrossel_usuario_id")
    op.execute("ALTER TABLE carrossel DROP CONSTRAINT IF EXISTS fk_carrossel_usuario")
    op.execute("ALTER TABLE carrossel DROP COLUMN IF EXISTS usuario_id")
    op.execute("DROP TABLE IF EXISTS usuario_configuracao")
    op.execute("DROP TABLE IF EXISTS usuario")
