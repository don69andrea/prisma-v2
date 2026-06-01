"""seed full stock catalog (parity local <-> deployed)

Ergänzt die via 0009b geseedeten 5 Basis-Stocks um die restlichen 8 Ticker
des StubFundamentalsProvider-Katalogs, sodass lokale und deployte DB denselben
13-Stock-Katalog haben (Proof-of-Concept-Konsistenz). Idempotent — läuft bei
jedem Deploy (backend-start.sh: `alembic upgrade head`) und regeneriert den
Katalog auch nach einem Free-Tier-DB-Reset.

Country bewusst 'USA' (wie die 5 Basis-Stocks aus 0009b) für einheitliche
Factsheet-Darstellung.

Revision ID: 0012
Revises: 0011
Create Date: 2026-06-01
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO stocks (id, ticker, name, isin, sector, country, currency)
        VALUES
          ('66666666-6666-6666-6666-666666666666', 'AMD',  'Advanced Micro Devices Inc.', 'US0079031078', 'Technology',    'USA', 'USD'),
          ('77777777-7777-7777-7777-777777777777', 'CRM',  'Salesforce Inc.',             'US79466L3024', 'Technology',    'USA', 'USD'),
          ('88888888-8888-8888-8888-888888888888', 'INTC', 'Intel Corp.',                 'US4581401001', 'Technology',    'USA', 'USD'),
          ('99999999-9999-9999-9999-999999999999', 'JPM',  'JPMorgan Chase & Co.',        'US46625H1005', 'Financial',     'USA', 'USD'),
          ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'META', 'Meta Platforms Inc.',         'US30303M1027', 'Communication', 'USA', 'USD'),
          ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'NFLX', 'Netflix Inc.',                'US64110L1061', 'Communication', 'USA', 'USD'),
          ('cccccccc-cccc-cccc-cccc-cccccccccccc', 'NVDA', 'NVIDIA Corp.',                'US67066G1040', 'Technology',    'USA', 'USD'),
          ('dddddddd-dddd-dddd-dddd-dddddddddddd', 'ORCL', 'Oracle Corp.',                'US68389X1054', 'Technology',    'USA', 'USD')
        ON CONFLICT (ticker) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM stocks
        WHERE ticker IN ('AMD', 'CRM', 'INTC', 'JPM', 'META', 'NFLX', 'NVDA', 'ORCL')
          AND id IN (
            '66666666-6666-6666-6666-666666666666',
            '77777777-7777-7777-7777-777777777777',
            '88888888-8888-8888-8888-888888888888',
            '99999999-9999-9999-9999-999999999999',
            'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
            'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
            'cccccccc-cccc-cccc-cccc-cccccccccccc',
            'dddddddd-dddd-dddd-dddd-dddddddddddd'
          )
    """)
