# AUTO REMINDER HUB PHASE 1 MVP 

# TECH STACK 
1. BACKEND - PYTHON
2. FRONTEND - REACT 
3. DB - POSTGRES

Python 3.11.9

# Download spaCy model (optional, for advanced NLP)

python -m pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1-py3-none-any.whl

## Installation & Setup Instructions

### 1. Install Dependencies
```bash
pip install -r requirements.txt



### 3. Run Migrations
```bash
alembic init alembic
alembic revision --autogenerate -m "Initial migration"
alembic upgrade head
```


### 4. Start Server
```bash
# Development
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Health check
curl http://localhost:8000/

# API docs
open http://localhost:8000/api/docs



author - Utsav Jain