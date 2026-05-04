# ATA Workflow Manager

Internal system for TRF (Training Request Form) approvals, procurement, and project tracking.

## Tech Stack

- **Backend**: Django 4.2 + PostgreSQL
- **Frontend**: Django Templates + Alpine.js + Bootstrap 5
- **Auth**: Django built-in auth
- **Hosting**: Railway or Render

---

## Project Structure

```
ata_workflow/       # Django project settings & root URLs
users/              # Custom User model with role field
trf/                # Phase 1 — TRF approval workflow
projects/           # Phase 2 — Project milestones (stub)
procurement/        # Phase 3 — Procurement costing sheet (stub)
templates/          # Global templates (base.html, login)
static/             # Static assets (CSS)
```

---

## Setup

### 1. Clone & create virtual environment

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env — set SECRET_KEY and DATABASE_URL at minimum
```

Minimum `.env` for local dev:

```
SECRET_KEY=any-random-string
DEBUG=True
DATABASE_URL=postgres://postgres:postgres@localhost:5432/ata_workflow
```

### 4. Create the database

```bash
psql -U postgres -c "CREATE DATABASE ata_workflow;"
```

### 5. Run migrations

```bash
python manage.py migrate
```

This will:
- Create all tables
- Seed the 6 named approvers (Aidan, Trevor, Tasneem at L2; Sharona, Melisa, Andre at L3)
- Default password for all seeded approvers: `changeme123`

### 6. Create a superuser (optional)

```bash
python manage.py createsuperuser
```

### 7. Run the development server

```bash
python manage.py runserver
```

Visit: http://127.0.0.1:8000/trf/

---

## User Roles

| Role | Description |
|---|---|
| `Sales_User` | Creates and submits TRFs |
| `PC` | Procurement Coordinator |
| `PDR` | PDR role |
| `CDR` | CDR role |
| `Ops_Manager` | Operations Manager |
| `Finance` | Finance team member |
| `Director` | Director |
| `Admin` | Admin / named approver |

## Named Approvers

| Name | Email | Level |
|---|---|---|
| Aidan | aidan@ata.com | L2 |
| Trevor | trevor@ata.com | L2 |
| Tasneem | tasneem@ata.com | L2 |
| Sharona | sharona@ata.com | L3 |
| Melisa | melisa@ata.com | L3 |
| Andre | andre@ata.com | L3 |

---

## Deployment (Railway / Render)

1. Push to GitHub
2. Connect repo in Railway or Render dashboard
3. Set environment variables (DATABASE_URL, SECRET_KEY, EMAIL_*, SLACK_OPS_WEBHOOK_URL)
4. Railway/Render will run `python manage.py migrate` on deploy
