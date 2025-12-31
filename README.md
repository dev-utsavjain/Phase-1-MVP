# 1. Install dependencies
pip install -r requirements.txt

# 2. Create PostgreSQL database
createdb MVP-PHASE1

# 3. Initialize Alembic
alembic init alembic

# 4. Edit alembic.ini - set sqlalchemy.url to your DATABASE_URL

# 5. Create migration
alembic revision --autogenerate -m "Initial schema"

# 6. Run migration
alembic upgrade head

# 7. Start server
uvicorn app.main:app --reload --port 8000

