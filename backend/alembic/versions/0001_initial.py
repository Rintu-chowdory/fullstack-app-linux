"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-26
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(50), nullable=False, unique=True, index=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), server_default="admin"),
    )
    op.create_table(
        "student_submissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("institute", sa.String(120), nullable=False),
        sa.Column("batch", sa.String(120), nullable=False),
        sa.Column("course_name", sa.String(120), nullable=False),
        sa.Column("module", sa.String(120), nullable=False),
        sa.Column("email", sa.String(120), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "students",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("institute", sa.String(120), nullable=False),
        sa.Column("batch", sa.String(120), nullable=False),
        sa.Column("course_name", sa.String(120), nullable=False),
        sa.Column("module", sa.String(120), nullable=False),
        sa.Column("email", sa.String(120), nullable=False, unique=True, index=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("profile_image_path", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("students")
    op.drop_table("student_submissions")
    op.drop_table("users")
