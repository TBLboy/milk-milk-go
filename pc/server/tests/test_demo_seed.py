import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path


def _run_seed(server_root: Path, data_dir: Path, assets_dir: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["MILK_DATA_DIR"] = str(data_dir)
    env["MILK_DEMO_ASSETS_DIR"] = str(assets_dir)
    env["PYTHONPATH"] = str(server_root)
    return subprocess.run(
        [sys.executable, str(server_root / "seed.py")],
        cwd=server_root,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def test_demo_seed_is_complete_and_idempotent(tmp_path):
    server_root = Path(__file__).resolve().parents[1]
    seed_script = (server_root / "seed.py").read_text(encoding="utf-8")
    file_ids = sorted(set(re.findall(r'"(FILE-[0-9a-f]+)"', seed_script)))
    assert len(file_ids) == 10

    assets_dir = tmp_path / "demo_assets" / "uploads"
    for file_id in file_ids:
        asset = assets_dir / file_id[:8] / f"{file_id}.jpg"
        asset.parent.mkdir(parents=True, exist_ok=True)
        asset.write_bytes(b"demo-image")

    data_dir = tmp_path / "data"
    _run_seed(server_root, data_dir, assets_dir)
    _run_seed(server_root, data_dir, assets_dir)

    connection = sqlite3.connect(data_dir / "milk_weigh.sqlite3")
    try:
        counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "materials",
                "products",
                "recipes",
                "recipe_items",
                "material_images",
                "evidence_files",
                "recipe_versions",
                "recipe_version_items",
            )
        }
    finally:
        connection.close()

    assert counts == {
        "materials": 14,
        "products": 6,
        "recipes": 6,
        "recipe_items": 29,
        "material_images": 10,
        "evidence_files": 10,
        "recipe_versions": 6,
        "recipe_version_items": 29,
    }


def test_demo_seed_defaults_to_data_dir_uploads(tmp_path):
    """未设置 MILK_DEMO_ASSETS_DIR 时，应自动从 <data_dir>/uploads 读取演示素材。"""
    server_root = Path(__file__).resolve().parents[1]
    seed_script = (server_root / "seed.py").read_text(encoding="utf-8")
    file_ids = sorted(set(re.findall(r'"(FILE-[0-9a-f]+)"', seed_script)))

    data_dir = tmp_path / "data"
    uploads_dir = data_dir / "uploads"
    for file_id in file_ids:
        asset = uploads_dir / file_id[:8] / f"{file_id}.jpg"
        asset.parent.mkdir(parents=True, exist_ok=True)
        asset.write_bytes(b"demo-image")

    env = os.environ.copy()
    env["MILK_DATA_DIR"] = str(data_dir)
    env.pop("MILK_DEMO_ASSETS_DIR", None)
    env["PYTHONPATH"] = str(server_root)
    subprocess.run(
        [sys.executable, str(server_root / "seed.py")],
        cwd=server_root,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    connection = sqlite3.connect(data_dir / "milk_weigh.sqlite3")
    try:
        images = connection.execute("SELECT COUNT(*) FROM material_images").fetchone()[0]
    finally:
        connection.close()
    assert images == 10
