"""add_unique_constraint_for_user_track_ratings

Revision ID: 7d4f8c9a1b2e
Revises: 93a54e5e3a3d
Create Date: 2026-03-03 20:40:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "7d4f8c9a1b2e"
down_revision: Union[str, Sequence[str], None] = "93a54e5e3a3d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Keep only the newest row for duplicate (track_id, user_id) combinations.
    op.execute(
        """
        DELETE FROM ratings
        WHERE id NOT IN (
            SELECT MAX(id)
            FROM ratings
            GROUP BY track_id, user_id
        )
        """
    )

    with op.batch_alter_table("ratings", schema=None) as batch_op:
        batch_op.create_unique_constraint(
            "uq_ratings_track_user", ["track_id", "user_id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("ratings", schema=None) as batch_op:
        batch_op.drop_constraint("uq_ratings_track_user", type_="unique")
