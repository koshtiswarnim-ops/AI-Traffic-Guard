import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.db.database import init_db, SessionLocal
from app.db.models import ViolationEvent

def test():
    print("Initializing DB...")
    init_db()
    with SessionLocal() as db:
        count = db.query(ViolationEvent).count()
        print(f"DB initialized successfully! Current events in DB: {count}")

if __name__ == "__main__":
    test()
