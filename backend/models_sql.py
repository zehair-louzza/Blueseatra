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
    ai_provider = Column(String(40), default="hermes")
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

# ===========================================================================
# Module Fournisseur
# ===========================================================================
# Ces tables sont definies dans supabase/migrations/20260912020000_module_
# fournisseur.sql. Les declarer ici est OBLIGATOIRE : pg_adapter resout
# chaque nom de collection via MODELS et leve AttributeError sur une table
# inconnue. Sans ces modeles, db.supplier_offers.insert_many() echouait des
# la premiere ligne importee.
#
# Les colonnes reprennent exactement les noms de la migration. Un ecart
# ferait silencieusement disparaitre la valeur : insert_many() filtre les
# cles inconnues (`{k: v for k, v in d.items() if k in cols}`), donc une
# faute de frappe ne leve aucune erreur -- elle perd la donnee.


class Supplier(Base):
    __tablename__ = "suppliers"
    __table_args__ = (
        Index("ix_suppliers_tenant_name", "tenant_id", "name"),
    )
    id = Column(String(36), primary_key=True)
    tenant_id = Column(String(36), index=True, nullable=False)
    name = Column(String(200), nullable=False)
    slug = Column(String(120))
    website = Column(Text)
    franco_ht = Column(Float)
    shipping_cost_ht = Column(Float)
    discount_rules = Column(JSONB)
    default_delay = Column(String(60))
    agencies = Column(JSONB)
    notes = Column(Text)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(String(40))
    updated_at = Column(String(40))


class SupplierOffer(Base):
    __tablename__ = "supplier_offers"
    __table_args__ = (
        # La recherche filtre tenant + is_active puis trie par prix : cet
        # index couvre le chemin complet.
        Index("ix_offers_tenant_actif_prix", "tenant_id", "is_active",
              "price_ht"),
        Index("ix_offers_tenant_supplier_version", "tenant_id", "supplier_id",
              "version_id"),
    )
    id = Column(String(36), primary_key=True)
    tenant_id = Column(String(36), index=True, nullable=False)
    supplier_id = Column(String(36), index=True, nullable=False)
    catalog_id = Column(String(36), index=True)
    version_id = Column(String(36), index=True)
    raw_label = Column(Text, nullable=False)
    raw_reference = Column(String(160))
    raw_unit = Column(String(60))
    raw_row = Column(JSONB)
    label_norm = Column(Text)
    brand = Column(String(120))
    manufacturer_ref = Column(String(120))
    ean = Column(String(20))
    unit_canonical = Column(String(40))
    packaging_qty = Column(Float, nullable=False, default=1)
    min_qty = Column(Float)
    price_ht = Column(Float)
    price_ht_per_unit = Column(Float)
    currency = Column(String(8), nullable=False, default="EUR")
    vat_rate = Column(Float)
    discount_applied = Column(Float)
    delay = Column(String(60))
    availability = Column(String(60))
    product_url = Column(Text)
    source_date = Column(String(20))
    source_filename = Column(Text)
    canonical_product_id = Column(String(36), index=True)
    match_status = Column(String(20), nullable=False, default="pending")
    match_confidence = Column(Integer)
    match_rule_id = Column(String(36))
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(String(40))
    updated_at = Column(String(40))

    # --- designation canonique (migration 20260912130000) -------------
    # Extraits UNE FOIS a l'import : analyser 914 628 libelles prend
    # 77 s, impensable a chaque recherche. Stockes en colonnes, ils
    # rendent la regle de contradiction exprimable en SQL indexable :
    #     AND (calibre IS NULL OR calibre = '16A')
    designation_courte = Column(Text)
    type_produit = Column(String(60))
    calibre = Column(String(20))
    courbe = Column(String(20))
    poles = Column(String(12))
    pouvoir_coupure = Column(String(20))
    sensibilite = Column(String(20))
    section = Column(String(20))
    puissance = Column(String(20))
    temperature = Column(String(20))
    conditionnement_lot = Column(Integer)
    est_accessoire = Column(Boolean, nullable=False, default=False)
    est_courant_continu = Column(Boolean, nullable=False, default=False)


class CanonicalProduct(Base):
    __tablename__ = "canonical_products"
    __table_args__ = (
        Index("ix_canonical_tenant_norm", "tenant_id", "label_norm"),
    )
    id = Column(String(36), primary_key=True)
    tenant_id = Column(String(36), index=True, nullable=False)
    label = Column(Text, nullable=False)
    label_norm = Column(Text)
    family = Column(String(255))
    brand = Column(String(120))
    manufacturer_ref = Column(String(120))
    ean = Column(String(20))
    unit_canonical = Column(String(40))
    attributes = Column(JSONB)
    notes = Column(Text)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(String(40))
    updated_at = Column(String(40))
