"""SQLAlchemy DeclarativeBase mit konsistenten Constraint-Naming-Conventions."""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Einheitliche Namensgebung erleichtert Alembic-Autogenerate und DB-Inspection.
# Konvention: ix = Index, uq = Unique, ck = Check, fk = Foreign Key, pk = Primary Key
NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Gemeinsame Basisklasse aller ORM-Modelle in PRISMA."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
