"""seed SMI-20 Swiss stocks

PR #219 fuegt Ticker-Validierung gegen SwissStockRepository in
/portfolio/rebalance hinzu (W-9 Fix). SwissStockRepository.get_by_ticker()
sucht in der stocks-Tabelle nach ticker == X AND exchange IS NOT NULL.

Die bisherigen Seed-Migrationen (0009b, 0012) befuellen die stocks-Tabelle
ausschliesslich mit 13 US-Tech-Tickern ohne exchange-Wert. Schweizer
SMI-Ticker (NESN, NOVN, ROG, ...) existierten bislang nur, wenn jemand
manuell scripts/seed_smi_universe.py ausgefuehrt hat — das passiert in CI
nie und auch nicht automatisch bei einem frischen Deploy. Dadurch schlug
u.a. frontend/e2e/07-portfolio.spec.ts mit HTTP 422 "Unbekannte Ticker"
fehl, weil NESN/NOVN/ROG/ABBN in der CI-Datenbank schlicht nicht existierten.

Diese Migration seedet die SMI-20-Konstituenten (Stand Juni 2026, identische
Stammdaten wie scripts/seed_smi_universe.py) direkt in die stocks-Tabelle
inkl. exchange='XSWX', country='CH', currency='CHF', sodass
SwissStockRepository.get_by_ticker() sie ab `alembic upgrade head` ohne
manuellen Zusatzschritt findet. Idempotent via ON CONFLICT (ticker) DO NOTHING
(laeuft wie 0012 bei jedem Deploy via backend-start.sh: `alembic upgrade head`).

Revision ID: 0026
Revises: 0025
Create Date: 2026-06-16
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO stocks (id, ticker, name, isin, sector, country, currency, exchange)
        VALUES
          ('a1000001-0000-0000-0000-000000000001', 'NESN', 'Nestlé SA',                          'CH0038863350', 'Consumer Staples', 'CH', 'CHF', 'XSWX'),
          ('a1000001-0000-0000-0000-000000000002', 'NOVN', 'Novartis AG',                         'CH0012005267', 'Healthcare',        'CH', 'CHF', 'XSWX'),
          ('a1000001-0000-0000-0000-000000000003', 'ROG',  'Roche Holding AG',                    'CH0012032048', 'Healthcare',        'CH', 'CHF', 'XSWX'),
          ('a1000001-0000-0000-0000-000000000004', 'ABBN', 'ABB Ltd',                             'CH0012221716', 'Industrials',       'CH', 'CHF', 'XSWX'),
          ('a1000001-0000-0000-0000-000000000005', 'ZURN', 'Zurich Insurance Group AG',           'CH0011075394', 'Financials',        'CH', 'CHF', 'XSWX'),
          ('a1000001-0000-0000-0000-000000000006', 'UBSG', 'UBS Group AG',                        'CH0244767585', 'Financials',        'CH', 'CHF', 'XSWX'),
          ('a1000001-0000-0000-0000-000000000007', 'UHR',  'The Swatch Group AG',                 'CH0012255151', 'Consumer Disc.',    'CH', 'CHF', 'XSWX'),
          ('a1000001-0000-0000-0000-000000000008', 'GEBN', 'Geberit AG',                          'CH0030170408', 'Industrials',       'CH', 'CHF', 'XSWX'),
          ('a1000001-0000-0000-0000-000000000009', 'GIVN', 'Givaudan SA',                         'CH0010645932', 'Materials',         'CH', 'CHF', 'XSWX'),
          ('a1000001-0000-0000-0000-000000000010', 'LONN', 'Lonza Group AG',                      'CH0013841017', 'Healthcare',        'CH', 'CHF', 'XSWX'),
          ('a1000001-0000-0000-0000-000000000011', 'SREN', 'Swiss Re AG',                         'CH0126881561', 'Financials',        'CH', 'CHF', 'XSWX'),
          ('a1000001-0000-0000-0000-000000000012', 'SGKN', 'SGS SA',                              'CH0002497458', 'Industrials',       'CH', 'CHF', 'XSWX'),
          ('a1000001-0000-0000-0000-000000000013', 'SLHN', 'Swiss Life Holding AG',               'CH0014852781', 'Financials',        'CH', 'CHF', 'XSWX'),
          ('a1000001-0000-0000-0000-000000000014', 'SCMN', 'Swisscom AG',                         'CH0008742519', 'Communication',     'CH', 'CHF', 'XSWX'),
          ('a1000001-0000-0000-0000-000000000015', 'SIKA', 'Sika AG',                             'CH0418792922', 'Materials',         'CH', 'CHF', 'XSWX'),
          ('a1000001-0000-0000-0000-000000000016', 'HOLN', 'Holcim AG',                           'CH0012214059', 'Materials',         'CH', 'CHF', 'XSWX'),
          ('a1000001-0000-0000-0000-000000000017', 'PGHN', 'Partners Group Holding AG',           'CH0024608827', 'Financials',        'CH', 'CHF', 'XSWX'),
          ('a1000001-0000-0000-0000-000000000018', 'KNIN', 'Kühne + Nagel International AG',      'CH0025238863', 'Industrials',       'CH', 'CHF', 'XSWX'),
          ('a1000001-0000-0000-0000-000000000019', 'CFR',  'Compagnie Financière Richemont SA',   'CH0210483332', 'Consumer Disc.',    'CH', 'CHF', 'XSWX'),
          ('a1000001-0000-0000-0000-000000000020', 'STMN', 'Straumann Holding AG',                'CH0012280076', 'Healthcare',        'CH', 'CHF', 'XSWX')
        ON CONFLICT (ticker) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM stocks
        WHERE ticker IN (
            'NESN', 'NOVN', 'ROG', 'ABBN', 'ZURN', 'UBSG', 'UHR', 'GEBN', 'GIVN', 'LONN',
            'SREN', 'SGKN', 'SLHN', 'SCMN', 'SIKA', 'HOLN', 'PGHN', 'KNIN', 'CFR', 'STMN'
          )
          AND id IN (
            'a1000001-0000-0000-0000-000000000001',
            'a1000001-0000-0000-0000-000000000002',
            'a1000001-0000-0000-0000-000000000003',
            'a1000001-0000-0000-0000-000000000004',
            'a1000001-0000-0000-0000-000000000005',
            'a1000001-0000-0000-0000-000000000006',
            'a1000001-0000-0000-0000-000000000007',
            'a1000001-0000-0000-0000-000000000008',
            'a1000001-0000-0000-0000-000000000009',
            'a1000001-0000-0000-0000-000000000010',
            'a1000001-0000-0000-0000-000000000011',
            'a1000001-0000-0000-0000-000000000012',
            'a1000001-0000-0000-0000-000000000013',
            'a1000001-0000-0000-0000-000000000014',
            'a1000001-0000-0000-0000-000000000015',
            'a1000001-0000-0000-0000-000000000016',
            'a1000001-0000-0000-0000-000000000017',
            'a1000001-0000-0000-0000-000000000018',
            'a1000001-0000-0000-0000-000000000019',
            'a1000001-0000-0000-0000-000000000020'
          )
    """)
