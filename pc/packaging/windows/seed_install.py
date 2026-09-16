import os
import sys
from pathlib import Path


install_root = Path(__file__).resolve().parents[1]
program_data = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData"))
config_dir = program_data / "MilkWeigh" / "config"
data_dir = program_data / "MilkWeigh" / "data"

config_dir.mkdir(parents=True, exist_ok=True)
data_dir.mkdir(parents=True, exist_ok=True)
os.chdir(config_dir)
os.environ["MILK_DATA_DIR"] = str(data_dir)
os.environ["MILK_DEMO_ASSETS_DIR"] = str(install_root / "server" / "demo_assets" / "uploads")
sys.path.insert(0, str(install_root / "server"))

from seed import seed


if __name__ == "__main__":
    seed()
