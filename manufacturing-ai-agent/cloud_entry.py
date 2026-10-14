"""Community Cloud entry: initialize a fresh Demo database, then run the existing UI."""
import runpy
import sys
from pathlib import Path
APP_DIR=Path(__file__).resolve().parent
# Community Cloud may run a nested entrypoint with the repository root on sys.path.
sys.path.insert(0,str(APP_DIR))
from database import DB_PATH

if not DB_PATH.exists():
    from init_db import initialize_database
    from seed_data import seed_database
    initialize_database()
    seed_database()

runpy.run_path(str(Path(__file__).with_name('streamlit_app.py')),run_name='__main__')
