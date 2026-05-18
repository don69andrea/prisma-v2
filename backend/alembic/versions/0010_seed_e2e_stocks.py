"""seed E2E test stocks

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-17
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO stocks (id, ticker, name, isin, sector, country, currency)
        VALUES
          ('11111111-1111-1111-1111-111111111111', 'AAPL',  'Apple Inc.',        'US0378331005', 'Technology',        'USA', 'USD'),
          ('22222222-2222-2222-2222-222222222222', 'GOOGL', 'Alphabet Inc.',     'US02079K3059', 'Technology',        'USA', 'USD'),
          ('33333333-3333-3333-3333-333333333333', 'MSFT',  'Microsoft Corp.',   'US5949181045', 'Technology',        'USA', 'USD'),
          ('44444444-4444-4444-4444-444444444444', 'AMZN',  'Amazon.com Inc.',   'US0231351067', 'Consumer Cyclical', 'USA', 'USD'),
          ('55555555-5555-5555-5555-555555555555', 'TSLA',  'Tesla Inc.',        'US88160R1014', 'Automotive',        'USA', 'USD')
        ON CONFLICT (ticker) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM stocks
        WHERE ticker IN ('AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA')
          AND id IN (
            '11111111-1111-1111-1111-111111111111',
            '22222222-2222-2222-2222-222222222222',
            '33333333-3333-3333-3333-333333333333',
            '44444444-4444-4444-4444-444444444444',
            '55555555-5555-5555-5555-555555555555'
          )
    """)
