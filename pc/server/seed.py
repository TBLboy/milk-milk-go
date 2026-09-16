import hashlib
import mimetypes
import os
from pathlib import Path

from app.core.config import get_settings
from app.db.models import (
    EvidenceFile,
    Material,
    MaterialImage,
    Product,
    Recipe,
    RecipeItem,
    RecipeVersion,
    RecipeVersionItem,
    User,
    initialize_database,
)
from app.db.session import SessionLocal


DEMO_MATERIALS = [
    ("MAT-00001", "SWEET-01", "精制白砂糖", "Refined White Sugar", 24),
    ("MAT-00002", "SWEET-02", "赤藓糖醇", "Erythritol", 24),
    ("MAT-00003", "DAIRY-01", "乳清粉", "Whey Powder", 18),
    ("MAT-00004", "STAB-01", "复配增稠稳定剂", "Compound Stabilizer", 18),
    ("MAT-00005", "STAB-02", "高酯果胶", "High Ester Pectin", 18),
    ("MAT-00006", "EMUL-01", "单硬脂酸甘油酯", "Glycerol Monostearate", 18),
    ("MAT-00007", "MIN-01", "碳酸钙", "Calcium Carbonate", 24),
    ("MAT-00008", "VIT-01", "维生素D3粉", "Vitamin D3 Powder", 24),
    ("MAT-00009", "CULT-01", "乳酸菌发酵剂", "Lactic Acid Bacteria Starter", 12),
    ("MAT-00010", "FLAV-01", "牛奶香精", "Milk Flavor", 18),
    ("MAT-00011", "FLAV-02", "西番莲香精", "Passion Fruit Flavor", 18),
    ("MAT-00012", "FLAV-03", "草莓香精", "Strawberry Flavor", 18),
    ("MAT-00013", "FLAV-04", "巧克力香精", "Chocolate Flavor", 18),
    ("MAT-00014", "COL-01", "可可粉", "Cocoa Powder", 18),
]

DEMO_PRODUCTS = [
    (
        "高钙牛奶 1L",
        [
            ("MAT-00003", 12.0),
            ("MAT-00007", 1.2),
            ("MAT-00008", 0.02),
            ("MAT-00004", 0.8),
            ("MAT-00010", 0.15),
        ],
    ),
    (
        "原味酸奶 100g杯",
        [
            ("MAT-00001", 55.0),
            ("MAT-00003", 8.0),
            ("MAT-00004", 1.2),
            ("MAT-00006", 0.4),
            ("MAT-00009", 0.25),
        ],
    ),
    (
        "西番莲风味酸奶 100g杯",
        [
            ("MAT-00001", 62.0),
            ("MAT-00003", 8.0),
            ("MAT-00005", 1.8),
            ("MAT-00009", 0.25),
            ("MAT-00011", 0.6),
        ],
    ),
    (
        "草莓风味酸奶 100g杯",
        [
            ("MAT-00001", 62.0),
            ("MAT-00003", 8.0),
            ("MAT-00005", 1.6),
            ("MAT-00009", 0.25),
            ("MAT-00012", 0.7),
        ],
    ),
    (
        "低糖原味酸奶 100g杯",
        [
            ("MAT-00002", 28.0),
            ("MAT-00003", 8.0),
            ("MAT-00004", 1.2),
            ("MAT-00006", 0.4),
            ("MAT-00009", 0.25),
        ],
    ),
    (
        "巧克力牛奶 250ml",
        [
            ("MAT-00001", 45.0),
            ("MAT-00014", 18.0),
            ("MAT-00004", 1.2),
            ("MAT-00013", 0.3),
        ],
    ),
]

DEMO_MATERIAL_IMAGE_FILES = {
    "MAT-00014": [
        "FILE-7f014209079f8bb72d1ffcc7",
        "FILE-de3e92b165b028854881aed2",
        "FILE-5e607996c8a06ceaca9ef951",
        "FILE-ca585337246d195956b87179",
        "FILE-92b5154561699d6f8e645d83",
        "FILE-734589df56298ab824901c0a",
        "FILE-45eeeef499a05d0f6927b4cc",
        "FILE-3a172e22eb7ab931e58104f0",
        "FILE-3b2fcd46ca0324c9fe2cd2cc",
        "FILE-1b859f40464b081cec1d9836",
    ]
}


def _upsert_materials(db) -> dict[str, Material]:
    materials: dict[str, Material] = {}
    for material_id, material_code, name_zh, name_en, shelf_life_months in DEMO_MATERIALS:
        material = db.query(Material).filter(Material.material_id == material_id).first()
        if material is None:
            material = Material(material_id=material_id)
            db.add(material)
        material.material_code = material_code
        material.name_zh = name_zh
        material.name_en = name_en
        material.shelf_life_months = shelf_life_months
        material.enabled = True
        materials[material_id] = material
    db.flush()
    return materials


def _recipe_items_match(recipe: Recipe, expected: list[tuple[str, float]]) -> bool:
    actual = sorted(recipe.items, key=lambda item: item.sort_order)
    if len(actual) != len(expected):
        return False
    for item, (material_id, quantity) in zip(actual, expected, strict=True):
        if item.material.material_id != material_id or item.quantity_per_ton_kg != quantity:
            return False
    return True


def _replace_recipe_items(
    db,
    recipe: Recipe,
    product: Product,
    expected: list[tuple[str, float]],
    materials: dict[str, Material],
    admin_id: int,
    is_new_recipe: bool,
) -> bool:
    if _recipe_items_match(recipe, expected):
        return False

    if is_new_recipe:
        recipe.version = 1
    else:
        latest = (
            db.query(RecipeVersion.version)
            .filter(RecipeVersion.product_id == product.id)
            .order_by(RecipeVersion.version.desc())
            .first()
        )
        recipe.version = (latest[0] if latest else recipe.version) + 1

    recipe.items.clear()
    recipe.items.extend(
        RecipeItem(
            material_id=materials[material_id].id,
            quantity_per_ton_kg=quantity,
            sort_order=index,
        )
        for index, (material_id, quantity) in enumerate(expected)
    )
    db.flush()
    db.add(
        RecipeVersion(
            product_id=product.id,
            version=recipe.version,
            created_by=admin_id,
            items=[
                RecipeVersionItem(
                    material_id=materials[material_id].material_id,
                    material_code=materials[material_id].material_code,
                    material_name_zh=materials[material_id].name_zh,
                    quantity_per_ton_kg=quantity,
                    sort_order=index,
                )
                for index, (material_id, quantity) in enumerate(expected)
            ],
        )
    )
    return True


def _upsert_products(db, materials: dict[str, Material], admin_id: int) -> int:
    changed_recipes = 0
    for product_name, expected in DEMO_PRODUCTS:
        product = db.query(Product).filter(Product.name == product_name).first()
        if product is None:
            product = Product(name=product_name)
            db.add(product)
            db.flush()
        product.enabled = True

        recipe = product.recipe
        is_new_recipe = recipe is None
        if recipe is None:
            recipe = Recipe(product_id=product.id, version=1)
            db.add(recipe)
            db.flush()
        recipe.enabled = True
        if _replace_recipe_items(
            db,
            recipe,
            product,
            expected,
            materials,
            admin_id,
            is_new_recipe,
        ):
            changed_recipes += 1
    return changed_recipes


def _source_asset(asset_root: Path, file_id: str) -> Path:
    directory = asset_root / file_id[:8]
    matches = sorted(directory.glob(f"{file_id}.*"))
    if len(matches) != 1:
        raise FileNotFoundError(f"演示图片缺失或重复：{file_id}")
    return matches[0]


def _upsert_material_images(
    db,
    materials: dict[str, Material],
    admin_id: int,
) -> int:
    if not DEMO_MATERIAL_IMAGE_FILES:
        return 0

    asset_root = Path(
        os.environ.get(
            "MILK_DEMO_ASSETS_DIR",
            str(Path(__file__).resolve().parent / "demo_assets" / "uploads"),
        )
    )
    uploads_root = get_settings().data_dir / "uploads"
    changed = 0

    for material_id, file_ids in DEMO_MATERIAL_IMAGE_FILES.items():
        material = materials[material_id]
        existing_images = {image.file_id: image for image in material.images}
        for sort_order, file_id in enumerate(file_ids):
            source = _source_asset(asset_root, file_id)
            target = uploads_root / file_id[:8] / source.name
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists() or target.read_bytes() != source.read_bytes():
                target.write_bytes(source.read_bytes())

            content = target.read_bytes()
            evidence = db.query(EvidenceFile).filter(EvidenceFile.file_id == file_id).first()
            if evidence is None:
                evidence = EvidenceFile(file_id=file_id, uploaded_by=admin_id)
                db.add(evidence)
            evidence.original_name = f"{material.name_zh}包装图-{sort_order + 1}{source.suffix}"
            evidence.stored_path = str(target)
            evidence.content_type = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
            evidence.size_bytes = len(content)
            evidence.sha256 = hashlib.sha256(content).hexdigest()

            image = existing_images.get(file_id)
            if image is None:
                image = MaterialImage(material_id=material.id, file_id=file_id)
                db.add(image)
            image.sort_order = sort_order
            changed += 1
    return changed


def seed() -> None:
    initialize_database()
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.role == "admin").order_by(User.id).first()
        if admin is None:
            raise RuntimeError("管理员账号初始化失败，无法写入演示主数据。")

        materials = _upsert_materials(db)
        changed_recipes = _upsert_products(db, materials, admin.id)
        changed_images = _upsert_material_images(db, materials, admin.id)
        db.commit()

        print(
            "Demo master data synchronized: "
            f"{len(DEMO_MATERIALS)} materials, "
            f"{len(DEMO_PRODUCTS)} recipes, "
            f"{changed_recipes} changed recipes, "
            f"{changed_images} material images."
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
