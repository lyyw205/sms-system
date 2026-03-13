"""Add reservation_sms_assignments table and short_label to message_templates

Revision ID: 004
Revises: 003
Create Date: 2026-03-11
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add short_label to message_templates
    op.add_column('message_templates', sa.Column('short_label', sa.String(10), nullable=True))

    # Create reservation_sms_assignments table
    op.create_table(
        'reservation_sms_assignments',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('reservation_id', sa.Integer(), sa.ForeignKey('reservations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('template_key', sa.String(100), nullable=False, index=True),
        sa.Column('assigned_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('assigned_by', sa.String(20), server_default='auto'),
        sa.UniqueConstraint('reservation_id', 'template_key', name='uq_res_sms_template'),
    )

    # Migrate existing sent_sms_types data to the new join table
    # Mapping: Korean display names -> template keys
    connection = op.get_bind()

    # Check if there's any data to migrate
    result = connection.execute(
        sa.text("SELECT id, sent_sms_types FROM reservations WHERE sent_sms_types IS NOT NULL AND sent_sms_types != ''")
    )

    display_to_key = {
        '객실안내': 'room_guide',
        '파티안내': 'party_guide',
        '객후': 'post_checkout',
    }

    for row in result:
        res_id = row[0]
        sent_types = row[1]
        if not sent_types:
            continue
        types_list = [t.strip() for t in sent_types.split(',') if t.strip()]
        for display_name in types_list:
            template_key = display_to_key.get(display_name, display_name)
            # INSERT OR IGNORE to handle duplicates
            try:
                connection.execute(
                    sa.text(
                        "INSERT INTO reservation_sms_assignments (reservation_id, template_key, assigned_by, sent_at) "
                        "VALUES (:res_id, :key, 'auto', CURRENT_TIMESTAMP) "
                        "ON CONFLICT (reservation_id, template_key) DO NOTHING"
                    ),
                    {"res_id": res_id, "key": template_key}
                )
            except Exception:
                pass  # Skip on conflict


def downgrade() -> None:
    op.drop_table('reservation_sms_assignments')
    op.drop_column('message_templates', 'short_label')
