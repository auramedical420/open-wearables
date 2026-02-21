"""add_steps_daily_total_series_type

Revision ID: 13692e1b4f2e
Revises: 31c7f45b636f

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "13692e1b4f2e"
down_revision: Union[str, None] = "31c7f45b636f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO series_type_definition (id, code, unit)
        VALUES (87, 'steps_daily_total', 'count')
        ON CONFLICT (id) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM series_type_definition
        WHERE id = 87 AND code = 'steps_daily_total'
    """)
