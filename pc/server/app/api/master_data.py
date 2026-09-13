from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.auth import current_user, require_admin
from app.db.models import Material, MaterialImage, Product, ProductImage, Recipe, RecipeItem, RecipeVersion, RecipeVersionItem, User
from app.db.session import get_db
from app.services.audit import write_audit
from app.services.product_excel import (
    ProductExcelFormatError,
    build_product_recipe_export,
    build_product_recipe_template,
    parse_product_recipe_workbook,
)

router = APIRouter(prefix="/master-data", tags=["master-data"])


class MaterialInput(BaseModel):
    material_code: str = Field(min_length=1, max_length=64)
    name_zh: str = Field(min_length=1, max_length=128)
    name_en: str | None = Field(default=None, max_length=128)
    shelf_life_months: int = Field(ge=0, le=600)
    image_file_ids: list[str] = Field(default_factory=list, max_length=20)


class ProductItemInput(BaseModel):
    material_id: str = Field(min_length=1, max_length=32)
    quantity_per_ton_kg: float = Field(gt=0, le=10000)


class ProductInput(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    items: list[ProductItemInput] = Field(min_length=1, max_length=100)
    image_file_id: str | None = Field(default=None, max_length=64)


class ProductActiveRequest(BaseModel):
    is_active: bool


def material_view(material: Material) -> dict:
    return {
        "material_id": material.material_id,
        "material_code": material.material_code,
        "name_zh": material.name_zh,
        "name_en": material.name_en,
        "shelf_life_months": material.shelf_life_months,
        "images": [{"file_id": image.file_id, "sort_order": image.sort_order} for image in sorted(material.images, key=lambda item: item.sort_order)],
    }


def product_view(product: Product) -> dict:
    recipe = product.recipe
    images = sorted(product.images, key=lambda item: item.sort_order)
    return {
        "id": product.id,
        "name": product.name,
        "enabled": product.enabled,
        "image_file_id": images[0].file_id if images else None,
        "recipe_version": recipe.version if recipe else None,
        "recipe_enabled": recipe.enabled if recipe else None,
        "items": [{
            "material_id": item.material.material_id,
            "material_code": item.material.material_code,
            "name_zh": item.material.name_zh,
            "quantity_per_ton_kg": item.quantity_per_ton_kg,
            "sort_order": item.sort_order,
        } for item in sorted(recipe.items, key=lambda value: value.sort_order)] if recipe else [],
    }


def material_audit_view(material: Material) -> dict:
    return {
        "material_id": material.material_id,
        "material_code": material.material_code,
        "name_zh": material.name_zh,
        "name_en": material.name_en,
        "shelf_life_months": material.shelf_life_months,
        "image_file_ids": [image.file_id for image in sorted(material.images, key=lambda item: item.sort_order)],
    }


def product_audit_view(product: Product) -> dict:
    recipe = product.recipe
    return {
        "product_id": product.id,
        "name": product.name,
        "enabled": product.enabled,
        "recipe_version": recipe.version if recipe else None,
        "image_file_id": sorted(product.images, key=lambda item: item.sort_order)[0].file_id if product.images else None,
        "items": [
            {
                "material_id": item.material.material_id,
                "quantity_per_ton_kg": item.quantity_per_ton_kg,
                "sort_order": item.sort_order,
            }
            for item in sorted(recipe.items, key=lambda value: value.sort_order)
        ] if recipe else [],
    }


def recipe_version_view(version: RecipeVersion, current_version: int) -> dict:
    return {
        "version": version.version,
        "is_current": version.version == current_version,
        "created_at": version.created_at,
        "created_by": {
            "id": version.creator.id,
            "username": version.creator.username,
            "display_name": version.creator.display_name,
        } if version.creator else None,
        "items": [{
            "material_id": item.material_id,
            "material_code": item.material_code,
            "name_zh": item.material_name_zh,
            "quantity_per_ton_kg": item.quantity_per_ton_kg,
            "sort_order": item.sort_order,
        } for item in sorted(version.items, key=lambda value: value.sort_order)],
    }


def _recipe_items_identity(recipe: Recipe) -> list[tuple[str, float, int]]:
    return [
        (item.material.material_id, float(item.quantity_per_ton_kg), item.sort_order)
        for item in sorted(recipe.items, key=lambda value: value.sort_order)
    ]


def _input_items_identity(body: ProductInput) -> list[tuple[str, float, int]]:
    return [
        (item.material_id, float(item.quantity_per_ton_kg), index)
        for index, item in enumerate(body.items)
    ]


def _snapshot_recipe_version(db: Session, recipe: Recipe, created_by: int | None) -> None:
    exists = db.scalar(
        select(RecipeVersion.id).where(
            RecipeVersion.product_id == recipe.product_id,
            RecipeVersion.version == recipe.version,
        )
    )
    if exists is not None:
        return
    db.add(
        RecipeVersion(
            product_id=recipe.product_id,
            version=recipe.version,
            created_by=created_by,
            items=[
                RecipeVersionItem(
                    material_id=item.material.material_id,
                    material_code=item.material.material_code,
                    material_name_zh=item.material.name_zh,
                    quantity_per_ton_kg=item.quantity_per_ton_kg,
                    sort_order=item.sort_order,
                )
                for item in sorted(recipe.items, key=lambda value: value.sort_order)
            ],
        )
    )


@router.get("/materials")
def list_materials(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[dict]:
    materials = db.scalars(select(Material).options(selectinload(Material.images)).order_by(Material.material_code)).all()
    return [material_view(item) for item in materials]


@router.post("/materials", status_code=status.HTTP_201_CREATED)
def create_material(body: MaterialInput, user: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    if db.scalar(select(Material).where(Material.material_code == body.material_code)):
        raise HTTPException(status_code=409, detail={"code": "MATERIAL_CODE_EXISTS", "message": "辅料代号已存在"})
    material = Material(material_id=f"MAT-{db.query(Material).count() + 1:05d}", material_code=body.material_code, name_zh=body.name_zh, name_en=body.name_en, shelf_life_months=body.shelf_life_months)
    material.images = [MaterialImage(file_id=file_id, sort_order=index) for index, file_id in enumerate(body.image_file_ids)]
    db.add(material)
    db.flush()
    write_audit(
        db,
        actor_id=user.id,
        action="material.created",
        resource_type="material",
        resource_id=material.material_id,
        detail={"after": material_audit_view(material)},
    )
    db.commit()
    db.refresh(material)
    return material_view(material)


@router.put("/materials/{material_id}", status_code=status.HTTP_200_OK)
def update_material(material_id: str, body: MaterialInput, user: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    material = db.scalar(select(Material).options(selectinload(Material.images)).where(Material.material_id == material_id))
    if material is None:
        raise HTTPException(status_code=404, detail={"code": "MATERIAL_NOT_FOUND", "message": "辅料不存在"})
    if db.scalar(select(Material).where(Material.material_code == body.material_code, Material.material_id != material_id)):
        raise HTTPException(status_code=409, detail={"code": "MATERIAL_CODE_EXISTS", "message": "辅料代号已存在"})
    before = material_audit_view(material)
    material.material_code = body.material_code
    material.name_zh = body.name_zh
    material.name_en = body.name_en
    material.shelf_life_months = body.shelf_life_months
    material.images.clear()
    db.flush()
    material.images = [MaterialImage(file_id=file_id, sort_order=index) for index, file_id in enumerate(body.image_file_ids)]
    db.add(material)
    db.flush()
    write_audit(
        db,
        actor_id=user.id,
        action="material.updated",
        resource_type="material",
        resource_id=material.material_id,
        detail={"before": before, "after": material_audit_view(material)},
    )
    db.commit()
    db.refresh(material)
    return material_view(material)


@router.delete("/materials/{material_id}", status_code=status.HTTP_200_OK)
def delete_material(material_id: str, user: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    material = db.scalar(select(Material).where(Material.material_id == material_id))
    if material is None:
        raise HTTPException(status_code=404, detail={"code": "MATERIAL_NOT_FOUND", "message": "辅料不存在"})
    if db.scalar(select(RecipeItem.id).where(RecipeItem.material_id == material.id)):
        raise HTTPException(status_code=409, detail={"code": "MATERIAL_IN_USE", "message": "辅料已被产品配方引用，不能删除；请先编辑配方移除该辅料"})
    snapshot = {
        "material_id": material.material_id,
        "material_code": material.material_code,
        "name_zh": material.name_zh,
    }
    db.delete(material)
    write_audit(
        db,
        actor_id=user.id,
        action="material.deleted",
        resource_type="material",
        resource_id=material_id,
        detail={"before": snapshot},
    )
    db.commit()
    return {"deleted": True, "material_id": material_id}


@router.get("/products")
def list_products(_: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    products = db.scalars(select(Product).options(selectinload(Product.images), selectinload(Product.recipe).selectinload(Recipe.items).selectinload(RecipeItem.material)).order_by(Product.name)).all()
    return [product_view(item) for item in products]


@router.get("/products/import-template")
def download_product_recipe_template(_: User = Depends(require_admin)) -> StreamingResponse:
    return StreamingResponse(
        build_product_recipe_template(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=products-recipes-template.xlsx"},
    )


@router.get("/products/export")
def export_product_recipes(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> StreamingResponse:
    products = db.scalars(
        select(Product)
        .options(selectinload(Product.recipe).selectinload(Recipe.items).selectinload(RecipeItem.material))
        .order_by(Product.name)
    ).all()
    return StreamingResponse(
        build_product_recipe_export(products),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=products-recipes-export.xlsx"},
    )


async def _parse_product_recipe_upload(db: Session, file: UploadFile):
    content = await file.read()
    material_codes = set(db.scalars(select(Material.material_code)).all())
    product_names = set(db.scalars(select(Product.name)).all())
    try:
        return parse_product_recipe_workbook(
            content,
            existing_material_codes=material_codes,
            existing_product_names=product_names,
        )
    except ProductExcelFormatError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "PRODUCT_RECIPE_EXCEL_INVALID", "message": str(exc)},
        ) from exc


@router.post("/products/import-validate")
async def validate_product_recipe_excel(
    file: UploadFile = File(...),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    result = await _parse_product_recipe_upload(db, file)
    return {
        "valid_product_count": len(result.valid_products),
        "valid_row_count": len(result.valid_rows),
        "error_count": len(result.errors),
        "valid_products": [
            {
                "product_name": product.product_name,
                "item_count": len(product.rows),
                "items": [
                    {
                        "row": row.row_no,
                        "material_code": row.material_code,
                        "quantity_per_ton_kg": row.quantity_per_ton_kg,
                    }
                    for row in product.rows
                ],
            }
            for product in result.valid_products
        ],
        "errors": list(result.errors),
    }


@router.post("/products/import")
async def import_product_recipe_excel(
    file: UploadFile = File(...),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    result = await _parse_product_recipe_upload(db, file)
    material_codes = [
        row.material_code
        for product in result.valid_products
        for row in product.rows
    ]
    materials = {
        material.material_code: material
        for material in db.scalars(select(Material).where(Material.material_code.in_(
            material_codes
        ))).all()
    } if material_codes else {}

    imported_names: list[str] = []
    imported_rows = 0
    for parsed_product in result.valid_products:
        product = Product(name=parsed_product.product_name)
        product.recipe = Recipe(
            items=[
                RecipeItem(
                    material=materials[row.material_code],
                    quantity_per_ton_kg=row.quantity_per_ton_kg,
                    sort_order=index,
                )
                for index, row in enumerate(parsed_product.rows)
            ]
        )
        db.add(product)
        db.flush()
        _snapshot_recipe_version(db, product.recipe, user.id)
        imported_names.append(product.name)
        imported_rows += len(parsed_product.rows)

    write_audit(
        db,
        actor_id=user.id,
        action="product.excel_imported",
        resource_type="product",
        result="success" if imported_names else "rejected",
        detail={
            "imported_products": imported_names,
            "imported_product_count": len(imported_names),
            "imported_row_count": imported_rows,
            "error_count": len(result.errors),
        },
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail={"code": "PRODUCT_IMPORT_CONFLICT", "message": "导入过程中产品名称发生变化，请重新校验后重试"},
        ) from exc

    return {
        "imported_product_count": len(imported_names),
        "imported_row_count": imported_rows,
        "error_count": len(result.errors),
        "imported_products": imported_names,
        "errors": list(result.errors),
    }


@router.post("/products", status_code=status.HTTP_201_CREATED)
def create_product(body: ProductInput, user: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    if db.scalar(select(Product).where(Product.name == body.name)):
        raise HTTPException(status_code=409, detail={"code": "PRODUCT_EXISTS", "message": "产品名称已存在"})
    materials = _resolve_recipe_materials(db, body)
    product = Product(name=body.name)
    product.recipe = Recipe(items=[RecipeItem(material=materials[item.material_id], quantity_per_ton_kg=item.quantity_per_ton_kg, sort_order=index) for index, item in enumerate(body.items)])
    if body.image_file_id:
        product.images = [ProductImage(file_id=body.image_file_id, sort_order=0)]
    db.add(product)
    db.flush()
    _snapshot_recipe_version(db, product.recipe, user.id)
    write_audit(
        db,
        actor_id=user.id,
        action="product.created",
        resource_type="product",
        resource_id=product.id,
        detail={"after": product_audit_view(product)},
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "RECIPE_VERSION_CONFLICT", "message": "配方版本已发生变化，请刷新后重试"}) from exc
    db.refresh(product)
    return product_view(product)


@router.put("/products/{product_id}", status_code=status.HTTP_200_OK)
def update_product(product_id: int, body: ProductInput, user: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    product = db.scalar(select(Product).options(selectinload(Product.recipe).selectinload(Recipe.items), selectinload(Product.images)).where(Product.id == product_id))
    if product is None:
        raise HTTPException(status_code=404, detail={"code": "PRODUCT_NOT_FOUND", "message": "产品不存在"})
    if db.scalar(select(Product).where(Product.name == body.name, Product.id != product_id)):
        raise HTTPException(status_code=409, detail={"code": "PRODUCT_EXISTS", "message": "产品名称已存在"})
    before = product_audit_view(product)
    materials = _resolve_recipe_materials(db, body)
    product.name = body.name
    recipe = product.recipe
    items_changed = recipe is None or _recipe_items_identity(recipe) != _input_items_identity(body)
    if recipe is None:
        recipe = Recipe(version=1)
        product.recipe = recipe
    else:
        _snapshot_recipe_version(db, recipe, None)
        if items_changed:
            recipe.version = (recipe.version or 1) + 1
    if items_changed:
        recipe.items.clear()
        db.flush()
        recipe.items = [RecipeItem(material=materials[item.material_id], quantity_per_ton_kg=item.quantity_per_ton_kg, sort_order=index) for index, item in enumerate(body.items)]
    product.images.clear()
    if body.image_file_id:
        product.images = [ProductImage(file_id=body.image_file_id, sort_order=0)]
    db.add(product)
    db.flush()
    if items_changed:
        _snapshot_recipe_version(db, recipe, user.id)
    write_audit(
        db,
        actor_id=user.id,
        action="product.updated",
        resource_type="product",
        resource_id=product.id,
        detail={"before": before, "after": product_audit_view(product), "recipe_items_changed": items_changed},
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "RECIPE_VERSION_CONFLICT", "message": "配方版本已发生变化，请刷新后重试"}) from exc
    db.refresh(product)
    return product_view(product)


@router.get("/products/{product_id}/recipe-versions")
def list_recipe_versions(product_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[dict]:
    product = db.scalar(
        select(Product)
        .options(selectinload(Product.recipe))
        .where(Product.id == product_id)
    )
    if product is None:
        raise HTTPException(status_code=404, detail={"code": "PRODUCT_NOT_FOUND", "message": "产品不存在"})
    current_version = product.recipe.version if product.recipe else 0
    versions = db.scalars(
        select(RecipeVersion)
        .options(
            selectinload(RecipeVersion.creator),
            selectinload(RecipeVersion.items),
        )
        .where(RecipeVersion.product_id == product_id)
        .order_by(RecipeVersion.version.desc())
    ).all()
    return [recipe_version_view(version, current_version) for version in versions]


@router.patch("/products/{product_id}/active", status_code=status.HTTP_200_OK)
def set_product_active(product_id: int, body: ProductActiveRequest, user: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    product = db.scalar(select(Product).options(selectinload(Product.recipe)).where(Product.id == product_id))
    if product is None:
        raise HTTPException(status_code=404, detail={"code": "PRODUCT_NOT_FOUND", "message": "产品不存在"})
    product.enabled = body.is_active
    if product.recipe:
        product.recipe.enabled = body.is_active
    write_audit(
        db,
        actor_id=user.id,
        action="product.activation_changed",
        resource_type="product",
        resource_id=product.id,
        detail={"product_name": product.name, "is_active": body.is_active},
    )
    db.commit()
    db.refresh(product)
    return product_view(product)


@router.delete("/products/{product_id}", status_code=status.HTTP_200_OK)
def delete_product(product_id: int, user: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    product = db.scalar(select(Product).where(Product.id == product_id))
    if product is None:
        raise HTTPException(status_code=404, detail={"code": "PRODUCT_NOT_FOUND", "message": "产品不存在"})
    snapshot = {"id": product.id, "name": product.name}
    db.delete(product)
    write_audit(
        db,
        actor_id=user.id,
        action="product.deleted",
        resource_type="product",
        resource_id=product_id,
        detail={"before": snapshot},
    )
    db.commit()
    return {"deleted": True, "id": product_id}


def _resolve_recipe_materials(db: Session, body: ProductInput) -> dict[str, Material]:
    material_ids = [item.material_id for item in body.items]
    if len(set(material_ids)) != len(material_ids):
        raise HTTPException(status_code=422, detail={"code": "DUPLICATE_RECIPE_MATERIAL", "message": "配方中不能重复添加同一辅料"})
    materials = {item.material_id: item for item in db.scalars(select(Material).where(Material.material_id.in_(material_ids))).all()}
    missing_ids = [material_id for material_id in material_ids if material_id not in materials]
    if missing_ids:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "MATERIAL_NOT_FOUND",
                "message": "配方包含不存在的辅料，请检查后重试",
                "material_ids": missing_ids,
            },
        )
    return materials
