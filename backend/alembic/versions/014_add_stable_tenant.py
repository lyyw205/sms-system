"""Add STABLE tenant

Revision ID: 014
"""
from alembic import op

revision = '014'
down_revision = '013'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    existing = conn.execute(
        "SELECT id FROM tenants WHERE slug = 'stable'"
    ).fetchone()
    if not existing:
        conn.execute(
            "INSERT INTO tenants (slug, name, is_active) VALUES ('stable', 'STABLE', true)"
        )


def downgrade():
    op.execute("DELETE FROM tenants WHERE slug = 'stable'")
