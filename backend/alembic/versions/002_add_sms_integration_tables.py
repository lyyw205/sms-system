"""Add SMS integration tables and extend Reservation model

Revision ID: 002
Revises: 001
Create Date: 2026-02-08

This migration adds:
- Extended fields to Reservation table (Naver integration, room assignment, demographics, SMS tracking)
- MessageTemplate table
- CampaignLog table
- GenderStat table
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade():
    # Extend reservations table
    op.add_column('reservations', sa.Column('naver_booking_id', sa.String(50), nullable=True))
    op.add_column('reservations', sa.Column('naver_biz_item_id', sa.String(50), nullable=True))
    op.add_column('reservations', sa.Column('visitor_name', sa.String(100), nullable=True))
    op.add_column('reservations', sa.Column('visitor_phone', sa.String(20), nullable=True))
    op.add_column('reservations', sa.Column('room_number', sa.String(20), nullable=True))
    op.add_column('reservations', sa.Column('room_password', sa.String(20), nullable=True))
    op.add_column('reservations', sa.Column('room_info', sa.String(200), nullable=True))
    op.add_column('reservations', sa.Column('gender', sa.String(10), nullable=True))
    op.add_column('reservations', sa.Column('age_group', sa.String(20), nullable=True))
    op.add_column('reservations', sa.Column('visit_count', sa.Integer, default=1))
    op.add_column('reservations', sa.Column('party_participants', sa.Integer, default=0))
    op.add_column('reservations', sa.Column('party_gender', sa.String(10), nullable=True))
    op.add_column('reservations', sa.Column('tags', sa.Text, nullable=True))
    op.add_column('reservations', sa.Column('room_sms_sent', sa.Boolean, default=False))
    op.add_column('reservations', sa.Column('party_sms_sent', sa.Boolean, default=False))
    op.add_column('reservations', sa.Column('room_sms_sent_at', sa.DateTime, nullable=True))
    op.add_column('reservations', sa.Column('party_sms_sent_at', sa.DateTime, nullable=True))
    op.add_column('reservations', sa.Column('sheets_row_number', sa.Integer, nullable=True))
    op.add_column('reservations', sa.Column('sheets_last_synced', sa.DateTime, nullable=True))
    op.add_column('reservations', sa.Column('is_multi_booking', sa.Boolean, default=False))

    # Create indexes
    op.create_index('ix_reservations_naver_booking_id', 'reservations', ['naver_booking_id'])

    # Create message_templates table
    op.create_table(
        'message_templates',
        sa.Column('id', sa.Integer, primary_key=True, index=True),
        sa.Column('key', sa.String(100), unique=True, nullable=False, index=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('variables', sa.Text, nullable=True),
        sa.Column('category', sa.String(50), nullable=True),
        sa.Column('active', sa.Boolean, default=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now())
    )

    # Create campaign_logs table
    op.create_table(
        'campaign_logs',
        sa.Column('id', sa.Integer, primary_key=True, index=True),
        sa.Column('campaign_type', sa.String(50), nullable=False),
        sa.Column('target_tag', sa.String(50), nullable=True),
        sa.Column('target_count', sa.Integer, default=0),
        sa.Column('sent_count', sa.Integer, default=0),
        sa.Column('failed_count', sa.Integer, default=0),
        sa.Column('sent_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime, nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('metadata', sa.Text, nullable=True)
    )

    # Create gender_stats table
    op.create_table(
        'gender_stats',
        sa.Column('id', sa.Integer, primary_key=True, index=True),
        sa.Column('date', sa.String(20), nullable=False, index=True),
        sa.Column('male_count', sa.Integer, default=0),
        sa.Column('female_count', sa.Integer, default=0),
        sa.Column('total_participants', sa.Integer, default=0),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now())
    )

    # Create index on date
    op.create_index('ix_gender_stats_date', 'gender_stats', ['date'])


def downgrade():
    # Drop new tables
    op.drop_table('gender_stats')
    op.drop_table('campaign_logs')
    op.drop_table('message_templates')

    # Drop indexes
    op.drop_index('ix_reservations_naver_booking_id', 'reservations')

    # Remove columns from reservations
    op.drop_column('reservations', 'is_multi_booking')
    op.drop_column('reservations', 'sheets_last_synced')
    op.drop_column('reservations', 'sheets_row_number')
    op.drop_column('reservations', 'party_sms_sent_at')
    op.drop_column('reservations', 'room_sms_sent_at')
    op.drop_column('reservations', 'party_sms_sent')
    op.drop_column('reservations', 'room_sms_sent')
    op.drop_column('reservations', 'tags')
    op.drop_column('reservations', 'party_gender')
    op.drop_column('reservations', 'party_participants')
    op.drop_column('reservations', 'visit_count')
    op.drop_column('reservations', 'age_group')
    op.drop_column('reservations', 'gender')
    op.drop_column('reservations', 'room_info')
    op.drop_column('reservations', 'room_password')
    op.drop_column('reservations', 'room_number')
    op.drop_column('reservations', 'visitor_phone')
    op.drop_column('reservations', 'visitor_name')
    op.drop_column('reservations', 'naver_biz_item_id')
    op.drop_column('reservations', 'naver_booking_id')
