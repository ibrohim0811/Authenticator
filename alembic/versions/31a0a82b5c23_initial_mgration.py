from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '31a0a82b5c23'  # faylingizdagi revision ID
down_revision = None
branch_labels = None
depends_on = None

# ENUM tipini e'lon qilamiz
user_role_enum = postgresql.ENUM('admin', 'user', 'moderator', name='userrole')


def upgrade() -> None:
    # 1. ENUM tipini yaratamiz
    user_role_enum.create(op.get_bind(), checkfirst=True)

    # 2. Ustunni vaqtincha nullable=True qilib qo'shamiz
    op.add_column('users', sa.Column('role', user_role_enum, nullable=True))

    # 3. Bazadagi barcha eski userlarga 'user' qiymatini berib chiqamiz
    op.execute("UPDATE users SET role = 'user' WHERE role IS NULL")

    # 4. Endi ustunni NOT NULL qilamiz
    op.alter_column('users', 'role', nullable=False)


def downgrade() -> None:
    op.drop_column('users', 'role')
    user_role_enum.drop(op.get_bind(), checkfirst=True)