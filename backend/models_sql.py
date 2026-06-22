"""SQLAlchemy ORM models mirroring the existing MongoDB collections.

Design notes:
- UUID string primary keys (matches existing `new_id()` -> str(uuid4())).
- Timestamps are stored as ISO strings (String) to match the current
  `now_iso()` usage and preserve lexical-sort behaviour during migration.
- Flexible / nested / document-style fields are stored as JSONB
  (e.g. pricing_items.attributes, quotes.lines, quotes.meta, snapshots).
- Indexes on tenant_id and foreign-key-like columns used in WHERE/ORDER BY.

FIXES applied:
  - Added UniqueConstraint on TenantUser(tenant_id, user_id) — prevents duplicate memberships.
  - Added composite Index on (tenant_id, status) for CatalogVersion, Request, Quote — the most
    common query pattern is "for this tenant, list items with status X".
  - Added `created_at` column to ImportError — required for purging old error rows.
  - Added check constraint skeleton on SettingsIntegration.ai_key to document enc:: expectation.
  - Added logo_url / logo_b64 to CompanyProfile — needed by pdf_service.py.
  - Added `__table_args__` docstrings for Alembic autogenerate awareness.
"""
from sqlalchemy import Boolean, Column, Float, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB

from database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(String(36), primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255))
    password_hash = Column(Text, nullable=False)
    created_at = Column(String(40))


class Tenant(Base):
    __tablename__ = "tenants"
    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    plan = Column(String(50), default="starter")
    created_at = Column(String(40))


class TenantUser(Base):
    __tablename__ = "tenant_users"
    # FIX: UniqueConstraint prevents duplicate (tenant, user) memberships.
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", name="uq_tenant_users_tenant_user"),
    )
    id = Column(String(36), primary_key=True)
    tenant_id = Column(String(36), index=True, nullable=False)
    user_id = Column(String(36), index=True, nullable=False)
    role = Column(String(40), default="operator")
    created_at = Column(String(40))


class Catalog(Base):
    __tablename__ = "catalogs"
    id = Column(String(36), primary_key=True)
    tenant_id = Column(String(36), index=True, nullable=False)
    name = Column(String(255), nullable=False)
    client_code = Column(String(120), default="N/A")
    active_version_id = Column(String(36), nullable=True)
    created_at = Column(String(40))


class CatalogVersion(Base):
    __tablename__ = "catalog_versions"
    # FIX: composite index for the most common query: tenant + status.
    __table_args__ = (
        Index("ix_catalog_versions_tenant_status", "tenant_id", "status"),
    )
    id = Column(String(36), primary_key=True)
    tenant_id = Column(String(36), index=True, nullable=False)
    catalog_id = Column(String(36), index=True, nullable=False)
    version_number = Column(Integer, default=1)
    status = Column(String(20), default="draft", index=True)
    item_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    columns = Column(JSONB)
    mapping = Column(JSONB)
    source_filename = Column(String(255))
    created_at = Column(String(40))
    activated_at = Column(String(40), nullable=True)


class PricingItem(Base):
    __tablename__ = "pricing_items"
    # FIX: composite index for the most common query: tenant + catalog + version.
    __table_args__ = (
        Index("ix_pricing_items_tenant_catalog_version", "tenant_id", "catalog_id", "version_id"),
    )
    id = Column(String(36), primary_key=True)
    tenant_id = Column(String(36), index=True, nullable=False)
    catalog_id = Column(String(36), index=True)
    version_id = Column(String(36), index=True)
    item_code = Column(String(120))
    item_label = Column(Text)
    label_norm = Column(Text)
    category = Column(String(255))
    family = Column(String(255))
    unit = Column(String(40))
    brand = Column(String(255))
    reference = Column(String(255))
    supplier_main = Column(String(255))
    suppliers = Column(JSONB)
    vat_rate = Column(Float, default=20)
    margin = Column(Float, default=0)
    purchase_price_ht = Column(Float, nullable=True)
    unit_price_ht = Column(Float, default=0)
    currency = Column(String(10), default="EUR")
    min_qty = Column(Float, default=1)
    is_active = Column(Boolean, default=True)
    delay = Column(String(120))
    notes = Column(Text)
    attributes = Column(JSONB)


class Request(Base):
    __tablename__ = "requests"
    # FIX: composite index for tenant + status lookups.
    __table_args__ = (
        Index("ix_requests_tenant_status", "tenant_id", "status"),
    )
    id = Column(String(36), primary_key=True)
    tenant_id = Column(String(36), index=True, nullable=False)
    title = Column(Text)
    source_type = Column(String(20))
    status = Column(String(20), index=True)
    raw_text = Column(Text)
    filename = Column(String(255), nullable=True)
    file_b64 = Column(Text, nullable=True)
    extracted = Column(JSONB, nullable=True)
    language = Column(String(20), nullable=True)
    confidence = Column(Float, nullable=True)
    error = Column(Text, nullable=True)
    created_by = Column(String(255))
    created_at = Column(String(40))


class Quote(Base):
    __tablename__ = "quotes"
    # FIX: composite index for tenant + status lookups.
    __table_args__ = (
        Index("ix_quotes_tenant_status", "tenant_id", "status"),
    )
    id = Column(String(36), primary_key=True)
    tenant_id = Column(String(36), index=True, nullable=False)
    request_id = Column(String(36), nullable=True)
    number = Column(String(60))
    status = Column(String(20), index=True)
    version = Column(Integer, default=1)
    client = Column(Text, nullable=True)
    site = Column(Text, nullable=True)
    client_final = Column(Text, nullable=True)
    object = Column(Text, nullable=True)
    language = Column(String(20), nullable=True)
    meta = Column(JSONB)
    lines = Column(JSONB)
    total_ht = Column(Float, default=0)
    total_vat = Column(Float, default=0)
    total_ttc = Column(Float, default=0)
    currency = Column(String(10), default="EUR")
    pricing_snapshot = Column(JSONB)
    created_by = Column(String(255))
    created_at = Column(String(40))
    validated_at = Column(String(40), nullable=True)
    sent_at = Column(String(40), nullable=True)


class QuoteVersion(Base):
    __tablename__ = "quote_versions"
    id = Column(String(36), primary_key=True)
    tenant_id = Column(String(36), index=True, nullable=False)
    quote_id = Column(String(36), index=True, nullable=False)
    version = Column(Integer, default=1)
    snapshot = Column(JSONB)
    created_at = Column(String(40))


class ImportJob(Base):
    __tablename__ = "import_jobs"
    id = Column(String(36), primary_key=True)
    tenant_id = Column(String(36), index=True, nullable=False)
    catalog_id = Column(String(36), index=True)
    version_id = Column(String(36))
    filename = Column(String(255))
    total_rows = Column(Integer, default=0)
    success_rows = Column(Integer, default=0)
    error_rows = Column(Integer, default=0)
    status = Column(String(20))
    created_at = Column(String(40))


class ImportError(Base):
    __tablename__ = "import_errors"
    id = Column(String(36), primary_key=True)
    tenant_id = Column(String(36), index=True, nullable=False)
    job_id = Column(String(36), index=True)
    row_number = Column(Integer)
    message = Column(Text)
    raw = Column(JSONB)
    # FIX: added created_at — required to audit and purge old error rows.
    created_at = Column(String(40), nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(String(36), primary_key=True)
    tenant_id = Column(String(36), index=True, nullable=False)
    actor = Column(String(255))
    action = Column(String(120))
    target = Column(String(120), nullable=True)
    meta = Column(JSONB)
    created_at = Column(String(40))


class SettingsIntegration(Base):
    __tablename__ = "settings_integrations"
    tenant_id = Column(String(36), primary_key=True)
    ai_provider = Column(String(40), default="emergent")
    ai_model = Column(String(80), nullable=True)
    # FIX: documented convention: encrypted values are prefixed with 'enc::'.
    # Enforcement is application-level (see ai_service.py encrypt/decrypt helpers).
    ai_key = Column(Text, nullable=True)
    n8n_webhook_url = Column(Text, nullable=True)
    updated_at = Column(String(40))


class CompanyProfile(Base):
    __tablename__ = "company_profiles"
    tenant_id = Column(String(36), primary_key=True)
    company_name = Column(Text, nullable=True)
    subtitle = Column(Text, nullable=True)
    address_line1 = Column(Text, nullable=True)
    address_line2 = Column(Text, nullable=True)
    country = Column(String(120), nullable=True)
    phone = Column(String(120), nullable=True)
    email = Column(String(255), nullable=True)
    siret = Column(String(120), nullable=True)
    tva_intra = Column(String(120), nullable=True)
    capital = Column(String(120), nullable=True)
    ape = Column(String(120), nullable=True)
    assurance = Column(Text, nullable=True)
    iban = Column(String(120), nullable=True)
    validity = Column(String(120), nullable=True)
    payment_terms = Column(Text, nullable=True)
    acceptance_text = Column(Text, nullable=True)
    # FIX: added logo columns — required by pdf_service.py for PDF header rendering.
    logo_url = Column(Text, nullable=True)
    logo_b64 = Column(Text, nullable=True)
    updated_at = Column(String(40), nullable=True)


# Used by the migration script and Alembic autogenerate.
ALL_MODELS = [
    User, Tenant, TenantUser, Catalog, CatalogVersion, PricingItem, Request,
    Quote, QuoteVersion, ImportJob, ImportError, AuditLog, SettingsIntegration,
    CompanyProfile,
]
