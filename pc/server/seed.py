from app.core.security import hash_password
from app.db.models import Material, Product, Recipe, RecipeItem, User, WorkOrder, WorkOrderStep, initialize_database
from app.db.session import SessionLocal

def seed():
    initialize_database()
    db = SessionLocal()
    try:
        existing_mat = db.query(Material).first()
        if not existing_mat:
            print("Seeding master data...")
            m1 = Material(material_id="MAT-00023", material_code="A1", name_zh="精制白砂糖", shelf_life_months=24, enabled=True)
            m2 = Material(material_id="MAT-00024", material_code="E2", name_zh="维生素 D3 粉", shelf_life_months=36, enabled=True)
            m3 = Material(material_id="MAT-00025", material_code="F-02", name_zh="西番莲风味香精", shelf_life_months=36, enabled=True)
            m4 = Material(material_id="MAT-00026", material_code="B7", name_zh="活性乳酸菌粉", shelf_life_months=12, enabled=True)
            db.add_all([m1, m2, m3, m4])
            db.flush()

            # Seed Product & Recipes
            p1 = Product(name="高钙纯牛奶 1L", enabled=True)
            db.add(p1)
            db.flush()
            r1 = Recipe(product_id=p1.id, version=1, enabled=True)
            db.add(r1)
            db.flush()
            db.add(RecipeItem(recipe_id=r1.id, material_id=m1.id, quantity_per_ton_kg=8.5, sort_order=1))
            db.add(RecipeItem(recipe_id=r1.id, material_id=m2.id, quantity_per_ton_kg=0.25, sort_order=2))

            p2 = Product(name="西番莲风味酸乳", enabled=True)
            db.add(p2)
            db.flush()
            r2 = Recipe(product_id=p2.id, version=1, enabled=True)
            db.add(r2)
            db.flush()
            db.add(RecipeItem(recipe_id=r2.id, material_id=m1.id, quantity_per_ton_kg=12.0, sort_order=1))
            db.add(RecipeItem(recipe_id=r2.id, material_id=m3.id, quantity_per_ton_kg=1.2, sort_order=2))
            db.add(RecipeItem(recipe_id=r2.id, material_id=m4.id, quantity_per_ton_kg=0.8, sort_order=3))

            # Seed an active work order
            admin = db.query(User).filter_by(username="admin").first()
            admin_id = admin.id if admin else 1
            wo = WorkOrder(
                order_no="WO-20260909-001",
                product_name_snapshot=p1.name,
                target_weight_kg=2000.0,
                status="in_progress",
                operator_id=admin_id,
                created_by=admin_id,
            )
            db.add(wo)
            db.flush()

            step1 = WorkOrderStep(
                work_order_id=wo.id,
                step_no=1,
                material_id_snapshot="MAT-00023",
                material_code_snapshot="A1",
                material_name_snapshot="精制白砂糖",
                required_weight_kg=17.0,
                tolerance_kg=0.17,
                status="completed",
            )
            step2 = WorkOrderStep(
                work_order_id=wo.id,
                step_no=2,
                material_id_snapshot="MAT-00024",
                material_code_snapshot="E2",
                material_name_snapshot="维生素 D3 粉",
                required_weight_kg=0.5,
                tolerance_kg=0.01,
                status="type_confirmation",
            )
            db.add_all([step1, step2])
            db.commit()
            print("Master data and demo order seeded successfully!")
        else:
            print("Database already contains data.")
    finally:
        db.close()

if __name__ == "__main__":
    seed()
