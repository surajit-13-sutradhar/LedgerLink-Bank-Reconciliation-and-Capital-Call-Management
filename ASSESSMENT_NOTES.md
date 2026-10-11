i am using Django version 5.2.18 because that is the version my current version of Python 3.10 is compatible with.
REST Api: Django Rest Framework
Postgresql database adapter: psycopg 3
installations:
```powershell
pip install "Django>=5.2,<5.3" "djangorestframework>=3.16,<3.17" "psycopg[binary,pool]"
```

here are the steps done until now (will be done):
1) requirements, installations, scope decided
2) created repo, django backend, react + typescript + vite frontend
3) postgresql configuration: `migrate` applied to PostgreSQL, tables confirmed with `dbshell`
4) created datamodel and contraints. reconciliation.0001_initial applied. tested with a smoke script, not test file



## Setting up from a fresh clone

### prereq
python >= 3.10, nodejs 18 or newer, npm, Git, and a running PostgreSQL server

### backend
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env   
```