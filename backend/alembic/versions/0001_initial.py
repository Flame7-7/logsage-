"""initial

Revision ID: 0001
Revises: 
Create Date: 2026-01-01 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enums using SQLAlchemy
    sa.Enum('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL', name='loglevel').create(op.get_bind(), checkfirst=True)
    sa.Enum('file_upload', 'websocket', 'api', 'simulated', name='logsource').create(op.get_bind(), checkfirst=True)
    sa.Enum('low', 'medium', 'high', 'critical', name='incidentseverity').create(op.get_bind(), checkfirst=True)
    sa.Enum('open', 'investigating', 'resolved', 'false_positive', name='incidentstatus').create(op.get_bind(), checkfirst=True)
    sa.Enum('firing', 'resolved', 'suppressed', name='alertstatus').create(op.get_bind(), checkfirst=True)

    op.create_table(
        'clusters',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(256), nullable=False),
        sa.Column('description', sa.Text),
        sa.Column('centroid_vector_id', sa.String(256)),
        sa.Column('log_count', sa.Integer, default=0),
        sa.Column('severity', sa.Enum('low', 'medium', 'high', 'critical', name='incidentseverity', create_type=False), nullable=False, server_default='low'),
        sa.Column('representative_messages', sa.JSON),
        sa.Column('tags', sa.JSON),
        sa.Column('first_seen', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_seen', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        'ingestion_sessions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('source', sa.Enum('file_upload', 'websocket', 'api', 'simulated', name='logsource', create_type=False), nullable=False),
        sa.Column('filename', sa.String(512)),
        sa.Column('total_lines', sa.Integer, default=0),
        sa.Column('processed_lines', sa.Integer, default=0),
        sa.Column('error_lines', sa.Integer, default=0),
        sa.Column('status', sa.String(32), default='processing'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        'incidents',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('title', sa.String(512), nullable=False),
        sa.Column('description', sa.Text),
        sa.Column('severity', sa.Enum('low', 'medium', 'high', 'critical', name='incidentseverity', create_type=False), nullable=False),
        sa.Column('status', sa.Enum('open', 'investigating', 'resolved', 'false_positive', name='incidentstatus', create_type=False), nullable=False, server_default='open'),
        sa.Column('cluster_id', sa.String(36), sa.ForeignKey('clusters.id', ondelete='SET NULL'), nullable=True),
        sa.Column('root_causes', sa.JSON),
        sa.Column('recommended_fixes', sa.JSON),
        sa.Column('timeline', sa.JSON),
        sa.Column('ai_confidence', sa.Float),
        sa.Column('ai_summary', sa.Text),
        sa.Column('affected_services', sa.JSON),
        sa.Column('log_count', sa.Integer, default=0),
        sa.Column('detected_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_incidents_status', 'incidents', ['status'])
    op.create_index('ix_incidents_severity', 'incidents', ['severity'])
    op.create_index('ix_incidents_detected_at', 'incidents', ['detected_at'])

    op.create_table(
        'alerts',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('incident_id', sa.String(36), sa.ForeignKey('incidents.id', ondelete='SET NULL'), nullable=True),
        sa.Column('alert_type', sa.String(128), nullable=False),
        sa.Column('title', sa.String(512), nullable=False),
        sa.Column('message', sa.Text, nullable=False),
        sa.Column('severity', sa.Enum('low', 'medium', 'high', 'critical', name='incidentseverity', create_type=False), nullable=False),
        sa.Column('status', sa.Enum('firing', 'resolved', 'suppressed', name='alertstatus', create_type=False), server_default='firing'),
        sa.Column('threshold_value', sa.Float),
        sa.Column('actual_value', sa.Float),
        sa.Column('alert_metadata', sa.JSON),
        sa.Column('fired_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_alerts_status', 'alerts', ['status'])
    op.create_index('ix_alerts_fired_at', 'alerts', ['fired_at'])

    op.create_table(
        'incident_summaries',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('incident_id', sa.String(36), sa.ForeignKey('incidents.id', ondelete='CASCADE'), unique=True),
        sa.Column('executive_summary', sa.Text, nullable=False),
        sa.Column('technical_details', sa.Text),
        sa.Column('impact_assessment', sa.Text),
        sa.Column('prevention_steps', sa.JSON),
        sa.Column('similar_past_incidents', sa.JSON),
        sa.Column('model_used', sa.String(128), nullable=False),
        sa.Column('token_usage', sa.Integer),
        sa.Column('generated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        'log_entries',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('session_id', sa.String(36), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('level', sa.Enum('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL', name='loglevel', create_type=False), nullable=False),
        sa.Column('source', sa.Enum('file_upload', 'websocket', 'api', 'simulated', name='logsource', create_type=False), nullable=False),
        sa.Column('service', sa.String(128)),
        sa.Column('message', sa.Text, nullable=False),
        sa.Column('raw_line', sa.Text),
        sa.Column('extra_fields', sa.JSON),
        sa.Column('is_anomaly', sa.Boolean, default=False),
        sa.Column('anomaly_score', sa.Float),
        sa.Column('cluster_id', sa.String(36), sa.ForeignKey('clusters.id', ondelete='SET NULL'), nullable=True),
        sa.Column('incident_id', sa.String(36), sa.ForeignKey('incidents.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_log_entries_timestamp', 'log_entries', ['timestamp'])
    op.create_index('ix_log_entries_level', 'log_entries', ['level'])
    op.create_index('ix_log_entries_source', 'log_entries', ['source'])
    op.create_index('ix_log_entries_session_id', 'log_entries', ['session_id'])

    op.create_table(
        'log_embeddings',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('log_entry_id', sa.String(36), sa.ForeignKey('log_entries.id', ondelete='CASCADE'), unique=True),
        sa.Column('chroma_id', sa.String(256)),
        sa.Column('model_name', sa.String(128), nullable=False),
        sa.Column('embedding_dimension', sa.Integer, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('log_embeddings')
    op.drop_table('log_entries')
    op.drop_table('incident_summaries')
    op.drop_table('alerts')
    op.drop_table('incidents')
    op.drop_table('ingestion_sessions')
    op.drop_table('clusters')