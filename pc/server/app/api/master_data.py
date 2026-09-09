from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.auth import require_admin
from app.db.models import Material, MaterialImage, Product, Recipe, RecipeItem, User
from app.db.session import get_db

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


def material_view(material: Material) -> dict:
    return {
        "material_id": material.material_id,
        "material_code": material.material_code,
        "name_zh": material.name_zh,
        "name_en": material.name_en,
        "shelf_life_months": material.shelf_life_months,
        "enabled": material.enabled,
        "images": [{"file_id": image.file_id, "sort_order": image.sort_order} for image in sorted(material.images, key=lambda item: item.sort_order)],
    }


def product_view(product: Product) -> dict:
    recipe = product.recipe
    return {
        "id": product.id,
        "name": product.name,
        "enabled": product.enabled,
        "recipe_version": recipe.version if recipe else None,
        "items": [{
            "material_id": item.material.material_id,
            "material_code": item.material.material_code,
            "name_zh": item.material.name_zh,
            "quantity_per_ton_kg": item.quantity_per_ton_kg,
            "sort_order": item.sort_order,
        } for item in sorted(recipe.items, key=lambda value: value.sort_order)] if recipe else [],
    }


@router.get("/materials")
def list_materials(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[dict]:
    materials = db.scalars(select(Material).options(selectinload(Material.images)).order_by(Material.material_code)).all()
    return [material_view(item) for item in materials]


@router.post("/materials", status_code=status.HTTP_201_CREATED)
def create_material(body: MaterialInput, _: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    if db.scalar(select(Material).where(Material.material_code == body.material_code)):
        raise HTTPException(status_code=409, detail={"code": "MATERIAL_CODE_EXISTS", "message": "辅料代号已存在"})
    material = Material(material_id=f"MAT-{db.query(Material).count() + 1:05d}", material_code=body.material_code, name_zh=body.name_zh, name_en=body.name_en, shelf_life_months=body.shelf_life_months)
    material.images = [MaterialImage(file_id=file_id, sort_order=index) for index, file_id in enumerate(body.image_file_ids)]
    db.add(material)
    db.commit()
    db.refresh(material)
    return material_view(material)


@router.patch("/materials/{material_id}/disable")
def disable_material(material_id: str, _: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    material = db.scalar(select(Material).where(Material.material_id == material_id))
    if material is None:
        raise HTTPException(status_code=404, detail={"code": "MATERIAL_NOT_FOUND", "message": "辅料不存在"})
    material.enabled = False
    db.commit()
    return material_view(material)


@router.get("/products")
def list_products(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[dict]:
    products = db.scalars(select(Product).options(selectinload(Product.recipe).selectinload(Recipe.items).selectinload(RecipeItem.material)).order_by(Product.name)).all()
    return [product_view(item) for item in products]


@router.post("/products", status_code=status.HTTP_201_CREATED)
def create_product(body: ProductInput, _: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    if db.scalar(select(Product).where(Product.name == body.name)):
        raise HTTPException(status_code=409, detail={"code": "PRODUCT_EXISTS", "message": "产品名称已存在"})
    material_ids = [item.material_id for item in body.items]
    if len(set(material_ids)) != len(material_ids):
        raise HTTPException(status_code=422, detail={"code": "DUPLICATE_RECIPE_MATERIAL", "message": "配方中不能重复添加同一辅料"})
    materials = {item.material_id: item for item in db.scalars(select(Material).where(Material.material_id.in_(material_ids))).all()}
    if len(materials) != len(material_ids) or any(not materials[key].enabled for key in material_ids):
        raise HTTPException(status_code=422, detail={"code": "MATERIAL_NOT_AVAILABLE", "message": "配方只能引用已存在且启用的辅料"})
    product = Product(name=body.name)
    product.recipe = Recipe(items=[RecipeItem(material=materials[item.material_id], quantity_per_ton_kg=item.quantity_per_ton_kg, sort_order=index) for index, item in enumerate(body.items)])
    db.add(product)
    db.commit()
    db.refresh(product)
    return product_view(product)
