"""Add wechat open platform fields for website app login

Revision ID: 94ea6e9efc65
Revises: ba124bb415d6
Create Date: 2026-08-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers
revision: str = '94ea6e9efc65'
down_revision: Union[str, Sequence[str], None] = 'ba124bb415d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('user', sa.Column('wechat_unionid', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.add_column('user', sa.Column('wechat_openid', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.add_column('user', sa.Column('wechat_nickname', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.add_column('user', sa.Column('wechat_avatar_url', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.add_column('user', sa.Column('wechat_last_login_at', sqlmodel.sql.sqltypes.AutoString(), nullable=True))

    op.create_index(op.f('ix_user_wechat_unionid'), 'user', ['wechat_unionid'], unique=True)
    op.create_index(op.f('ix_user_wechat_openid'), 'user', ['wechat_openid'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_user_wechat_openid'), table_name='user')
    op.drop_index(op.f('ix_user_wechat_unionid'), table_name='user')
    op.drop_column('user', 'wechat_last_login_at')
    op.drop_column('user', 'wechat_avatar_url')
    op.drop_column('user', 'wechat_nickname')
    op.drop_column('user', 'wechat_openid')
    op.drop_column('user', 'wechat_unionid')
