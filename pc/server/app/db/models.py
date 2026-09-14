import hashlib
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, selectinload


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class SchemaMeta(Base):
    __tablename__ = "schema_meta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    initialized_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(64), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="operator")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    avatar_file_id: Mapped[str | None] = mapped_column(String(64))
    phone: Mapped[str | None] = mapped_column(String(32))
    employee_no: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    must_change_password: Mapped[bool] = mapped_column(default=False, nullable=False)
    auth_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class Material(Base):
    __tablename__ = "materials"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    material_id: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    material_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name_zh: Mapped[str] = mapped_column(String(128), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(128))
    shelf_life_months: Mapped[int] = mapped_column(Integer, nullable=False)
    # Legacy schema compatibility only. Materials have no enable/disable workflow.
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    images: Mapped[list["MaterialImage"]] = relationship(back_populates="material", cascade="all, delete-orphan")


class MaterialImage(Base):
    __tablename__ = "material_images"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"), nullable=False, index=True)
    file_id: Mapped[str] = mapped_column(String(128), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    material: Mapped[Material] = relationship(back_populates="images")


class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    recipe: Mapped["Recipe | None"] = relationship(back_populates="product", uselist=False, cascade="all, delete-orphan")
    recipe_versions: Mapped[list["RecipeVersion"]] = relationship(back_populates="product", cascade="all, delete-orphan", order_by="RecipeVersion.version")
    images: Mapped[list["ProductImage"]] = relationship(back_populates="product", cascade="all, delete-orphan")


class ProductImage(Base):
    __tablename__ = "product_images"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    file_id: Mapped[str] = mapped_column(String(64), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    product: Mapped[Product] = relationship(back_populates="images")


class Recipe(Base):
    __tablename__ = "recipes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), unique=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    product: Mapped[Product] = relationship(back_populates="recipe")
    items: Mapped[list["RecipeItem"]] = relationship(back_populates="recipe", cascade="all, delete-orphan")


class RecipeItem(Base):
    __tablename__ = "recipe_items"
    __table_args__ = (UniqueConstraint("recipe_id", "material_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id"), nullable=False, index=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"), nullable=False, index=True)
    quantity_per_ton_kg: Mapped[float] = mapped_column(Float, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    recipe: Mapped[Recipe] = relationship(back_populates="items")
    material: Mapped[Material] = relationship()


class RecipeVersion(Base):
    __tablename__ = "recipe_versions"
    __table_args__ = (UniqueConstraint("product_id", "version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    product: Mapped[Product] = relationship(back_populates="recipe_versions")
    creator: Mapped[User | None] = relationship()
    items: Mapped[list["RecipeVersionItem"]] = relationship(back_populates="recipe_version", cascade="all, delete-orphan", order_by="RecipeVersionItem.sort_order")


class RecipeVersionItem(Base):
    __tablename__ = "recipe_version_items"
    __table_args__ = (UniqueConstraint("recipe_version_id", "material_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recipe_version_id: Mapped[int] = mapped_column(ForeignKey("recipe_versions.id"), nullable=False, index=True)
    material_id: Mapped[str] = mapped_column(String(32), nullable=False)
    material_code: Mapped[str] = mapped_column(String(64), nullable=False)
    material_name_zh: Mapped[str] = mapped_column(String(128), nullable=False)
    quantity_per_ton_kg: Mapped[float] = mapped_column(Float, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    recipe_version: Mapped[RecipeVersion] = relationship(back_populates="items")


class WorkOrder(Base):
    __tablename__ = "work_orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_no: Mapped[str] = mapped_column(String(40), unique=True, index=True, nullable=False)
    product_name_snapshot: Mapped[str] = mapped_column(String(128), nullable=False)
    target_weight_kg: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending_approval", nullable=False, index=True)
    operator_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    steps: Mapped[list["WorkOrderStep"]] = relationship(back_populates="work_order", cascade="all, delete-orphan", order_by="WorkOrderStep.step_no")
    requests: Mapped[list["WorkOrderRequest"]] = relationship(back_populates="work_order", cascade="all, delete-orphan", order_by="WorkOrderRequest.id")


class WorkOrderStep(Base):
    __tablename__ = "work_order_steps"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    work_order_id: Mapped[int] = mapped_column(ForeignKey("work_orders.id"), nullable=False, index=True)
    step_no: Mapped[int] = mapped_column(Integer, nullable=False)
    material_id_snapshot: Mapped[str] = mapped_column(String(32), nullable=False)
    material_code_snapshot: Mapped[str] = mapped_column(String(64), nullable=False)
    material_name_snapshot: Mapped[str] = mapped_column(String(128), nullable=False)
    required_weight_kg: Mapped[float] = mapped_column(Float, nullable=False)
    tolerance_kg: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    work_order: Mapped[WorkOrder] = relationship(back_populates="steps")
    confirmations: Mapped[list["TypeConfirmation"]] = relationship(back_populates="step", cascade="all, delete-orphan", order_by="TypeConfirmation.id")
    weighing_attempts: Mapped[list["WeighingAttempt"]] = relationship(back_populates="step", cascade="all, delete-orphan", order_by="WeighingAttempt.id")


class WorkOrderRequest(Base):
    __tablename__ = "work_order_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    work_order_id: Mapped[int] = mapped_column(ForeignKey("work_orders.id"), nullable=False, index=True)
    request_type: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    work_order: Mapped[WorkOrder] = relationship(back_populates="requests")


class EvidenceFile(Base):
    __tablename__ = "evidence_files"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    file_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str | None] = mapped_column(String(64))
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class TypeConfirmation(Base):
    __tablename__ = "type_confirmations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    work_order_step_id: Mapped[int] = mapped_column(ForeignKey("work_order_steps.id"), nullable=False, index=True)
    method: Mapped[str] = mapped_column(String(32), nullable=False)
    scanned_material_id: Mapped[str | None] = mapped_column(String(32))
    scanned_label_id: Mapped[str | None] = mapped_column(String(64))
    reason: Mapped[str | None] = mapped_column(String(500))
    evidence_file_id: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    step: Mapped[WorkOrderStep] = relationship(back_populates="confirmations")


class WeighingAttempt(Base):
    __tablename__ = "weighing_attempts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    work_order_step_id: Mapped[int] = mapped_column(ForeignKey("work_order_steps.id"), nullable=False, index=True)
    weight_kg: Mapped[float] = mapped_column(Float, nullable=False)
    weight_source: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    scale_photo_file_id: Mapped[str] = mapped_column(String(64), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    step: Mapped[WorkOrderStep] = relationship(back_populates="weighing_attempts")


class PrintBatch(Base):
    __tablename__ = "print_batches"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    material_id: Mapped[str] = mapped_column(String(32), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    printed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)


class Label(Base):
    __tablename__ = "labels"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    material_id: Mapped[str] = mapped_column(String(32), nullable=False)
    payload_json: Mapped[str] = mapped_column(String(2000), nullable=False)
    print_batch_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    printed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    result: Mapped[str] = mapped_column(String(32), default="success", nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(128))
    work_order_no: Mapped[str | None] = mapped_column(String(40), index=True)
    detail_json: Mapped[str | None] = mapped_column(String(4000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (UniqueConstraint("user_id", "endpoint", "request_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    request_id: Mapped[str] = mapped_column(String(128), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    response_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class BackupRecord(Base):
    __tablename__ = "backup_records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    trigger: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    schedule_key: Mapped[str | None] = mapped_column(String(16))
    checksum_sha256: Mapped[str | None] = mapped_column(String(64))
    app_version: Mapped[str | None] = mapped_column(String(32))
    error_message: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    value: Mapped[str] = mapped_column(String(500), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class BugReport(Base):
    __tablename__ = "bug_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    description: Mapped[str] = mapped_column(String(5000), nullable=False)
    image_file_ids_json: Mapped[str] = mapped_column(String(2000), nullable=False, default="[]")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


def initialize_database() -> None:
    from app.core.security import hash_password
    from app.db.session import SessionLocal, engine

    Base.metadata.create_all(bind=engine)
    _migrate_user_account_columns(engine)
    _migrate_evidence_file_columns(engine)
    _migrate_type_confirmation_columns(engine)
    _migrate_backup_record_columns(engine)
    _migrate_work_order_request_pending_index(engine)
    _migrate_audit_log_columns(engine)
    with SessionLocal.begin() as db:
        _backfill_recipe_versions(db)
        if db.query(SchemaMeta).count() == 0:
            db.add(SchemaMeta(version=1))
        if db.query(User).filter(User.role == "admin").count() == 0:
            db.add(User(username="admin", display_name="系统管理员", password_hash=hash_password("admin123"), role="admin", must_change_password=True))
        defaults = {
            "default_tolerance_percent": "1.0",
            "min_absolute_tolerance_grams": "5",
            "backup_enabled": "true",
            "backup_time": "02:00",
            "server_port": "8011",
            "label_size_mm": "60x40",
        }
        for key, value in defaults.items():
            if db.query(SystemSetting).filter(SystemSetting.key == key).count() == 0:
                db.add(SystemSetting(key=key, value=value))


def _migrate_user_account_columns(engine) -> None:
    with engine.begin() as connection:
        rows = connection.exec_driver_sql("PRAGMA table_info(users)").fetchall()
        columns = {row[1] for row in rows}
        if "status" not in columns:
            connection.exec_driver_sql("ALTER TABLE users ADD COLUMN status VARCHAR(32) NOT NULL DEFAULT 'active'")
        if "avatar_file_id" not in columns:
            connection.exec_driver_sql("ALTER TABLE users ADD COLUMN avatar_file_id VARCHAR(64)")
        if "phone" not in columns:
            connection.exec_driver_sql("ALTER TABLE users ADD COLUMN phone VARCHAR(32)")
        if "employee_no" not in columns:
            connection.exec_driver_sql("ALTER TABLE users ADD COLUMN employee_no VARCHAR(64)")
        if "auth_version" not in columns:
            connection.exec_driver_sql("ALTER TABLE users ADD COLUMN auth_version INTEGER NOT NULL DEFAULT 1")
        if "id_card" in columns:
            connection.exec_driver_sql("ALTER TABLE users DROP COLUMN id_card")
        connection.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_employee_no ON users (employee_no)"
        )


def _migrate_evidence_file_columns(engine) -> None:
    with engine.begin() as connection:
        rows = connection.exec_driver_sql("PRAGMA table_info(evidence_files)").fetchall()
        columns = {row[1] for row in rows}
        if "sha256" not in columns:
            connection.exec_driver_sql("ALTER TABLE evidence_files ADD COLUMN sha256 VARCHAR(64)")
        records = connection.exec_driver_sql(
            "SELECT id, stored_path FROM evidence_files WHERE sha256 IS NULL OR sha256 = ''"
        ).fetchall()
        for record_id, stored_path in records:
            path = Path(stored_path)
            if not path.is_file():
                continue
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            connection.exec_driver_sql(
                "UPDATE evidence_files SET sha256 = ? WHERE id = ?",
                (digest.hexdigest(), record_id),
            )


def _migrate_type_confirmation_columns(engine) -> None:
    with engine.begin() as connection:
        rows = connection.exec_driver_sql("PRAGMA table_info(type_confirmations)").fetchall()
        columns = {row[1] for row in rows}
        if "scanned_label_id" not in columns:
            connection.exec_driver_sql("ALTER TABLE type_confirmations ADD COLUMN scanned_label_id VARCHAR(64)")


def _migrate_backup_record_columns(engine) -> None:
    with engine.begin() as connection:
        rows = connection.exec_driver_sql("PRAGMA table_info(backup_records)").fetchall()
        columns = {row[1] for row in rows}
        if "trigger" not in columns:
            connection.exec_driver_sql("ALTER TABLE backup_records ADD COLUMN trigger VARCHAR(32) NOT NULL DEFAULT 'manual'")
        if "schedule_key" not in columns:
            connection.exec_driver_sql("ALTER TABLE backup_records ADD COLUMN schedule_key VARCHAR(16)")
        if "checksum_sha256" not in columns:
            connection.exec_driver_sql("ALTER TABLE backup_records ADD COLUMN checksum_sha256 VARCHAR(64)")
        if "app_version" not in columns:
            connection.exec_driver_sql("ALTER TABLE backup_records ADD COLUMN app_version VARCHAR(32)")


def _migrate_work_order_request_pending_index(engine) -> None:
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            UPDATE work_order_requests
            SET status = 'superseded'
            WHERE status = 'pending'
              AND id NOT IN (
                  SELECT MAX(id)
                  FROM work_order_requests
                  WHERE status = 'pending'
                  GROUP BY work_order_id
              )
            """
        )
        connection.exec_driver_sql(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_work_order_requests_pending
            ON work_order_requests (work_order_id)
            WHERE status = 'pending'
            """
        )


def _migrate_audit_log_columns(engine) -> None:
    with engine.begin() as connection:
        rows = connection.exec_driver_sql("PRAGMA table_info(audit_logs)").fetchall()
        columns = {row[1] for row in rows}
        if "result" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE audit_logs ADD COLUMN result VARCHAR(32) NOT NULL DEFAULT 'success'"
            )
        if "work_order_no" not in columns:
            connection.exec_driver_sql("ALTER TABLE audit_logs ADD COLUMN work_order_no VARCHAR(40)")
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_audit_logs_work_order_no ON audit_logs (work_order_no)"
        )
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_audit_logs_created_at ON audit_logs (created_at)"
        )
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_audit_logs_actor_id ON audit_logs (actor_id)"
        )
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_audit_logs_action ON audit_logs (action)"
        )
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_audit_logs_result ON audit_logs (result)"
        )


def _backfill_recipe_versions(db) -> None:
    recipes = db.query(Recipe).options(
        selectinload(Recipe.items).selectinload(RecipeItem.material)
    ).all()
    for recipe in recipes:
        exists = db.query(RecipeVersion.id).filter(
            RecipeVersion.product_id == recipe.product_id,
            RecipeVersion.version == recipe.version,
        ).first()
        if exists:
            continue
        db.add(
            RecipeVersion(
                product_id=recipe.product_id,
                version=recipe.version,
                created_by=None,
                items=[
                    RecipeVersionItem(
                        material_id=item.material.material_id,
                        material_code=item.material.material_code,
                        material_name_zh=item.material.name_zh,
                        quantity_per_ton_kg=item.quantity_per_ton_kg,
                        sort_order=item.sort_order,
                    )
                    for item in recipe.items
                ],
            )
        )
