<p align="center">
  <img src="docs/assets/banner.png" width="100%">
</p>

<h1 align="center">
PRISM
</h1>

<p align="center">

Professional Relationship Intelligence & Statistics Manager

</p>

<p align="center">

Modern Alumni Intelligence Platform

</p>

<p align="center">

FastAPI • Next.js • PostgreSQL • Supabase

</p>

# PRISM

> **Professional Relationship Intelligence & Statistics Manager**

A modern Alumni Intelligence Platform for higher education institutions that transforms fragmented alumni records into a single source of truth through deterministic ETL, snapshot-based analytics, and interactive executive dashboards.

Built as a portfolio-grade full-stack application using FastAPI, Next.js, PostgreSQL, and Supabase.

---

## Features

### Analytics

- Executive dashboard with alumni KPIs
- Career outcomes by study program
- Company and employer analytics
- Industry & sector distribution
- Geographic distribution
- Graduation year trends
- Snapshot comparison (Quarterly)

### Data Curation

- CSV/XLSX import
- Deterministic validation pipeline
- Company normalization
- Role normalization
- Seniority classification
- Two-stage deduplication
- Quarterly snapshot commit
- Validation workflow
- Full audit logging

### Security

- Supabase Authentication
- Database-driven RBAC
- JWT verification
- Permission-based API authorization

---

## Tech Stack

### Backend

- FastAPI
- SQLAlchemy
- Alembic
- PostgreSQL
- Supabase

### Frontend

- Next.js
- TypeScript
- TailwindCSS
- shadcn/ui
- Apache ECharts

### Infrastructure

- Railway
- Vercel
- GitHub Actions

---

## Project Structure

```
prism/
├── backend/
│   └── fastapi-app/
├── frontend/
│   └── nextjs-app/
├── database/
├── docs/
├── scripts/
└── README.md
```

---

## Architecture

```
                 CSV / XLSX
                      │
                      ▼
             Import Pipeline
                      │
          Validation & Normalization
                      │
               Deduplication
                      │
            Snapshot Generation
                      │
                PostgreSQL
                      │
          FastAPI Analytics API
                      │
              Next.js Dashboard
```

---

## Requirements

### Backend

- Python 3.12+
- PostgreSQL
- uv

### Frontend

- Node.js 22+
- pnpm

---

## Local Development

### Backend

```bash
cd backend/fastapi-app

uv sync

cp .env.example .env

uv run uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend/nextjs-app

pnpm install

cp .env.example .env.local

pnpm dev
```

---

## Deployment

| Component | Platform |
|----------|----------|
| Frontend | Vercel |
| Backend | Railway |
| Database | Supabase |
| Authentication | Supabase Auth |

---

## Testing

Backend

- Ruff
- Black
- MyPy (Strict)
- Pytest

Frontend

- ESLint
- TypeScript
- Vitest
- Next.js Production Build

---

## Project Status

Current Status

✅ MVP Complete

Current Phase

Phase 7 — Production Deployment

---

## Roadmap

- [x] Foundations
- [x] Database Schema
- [x] Authentication
- [x] RBAC
- [x] Import Pipeline
- [x] Validation
- [x] Deduplication
- [x] Snapshot Analytics
- [x] Dashboard
- [x] Documentation
- [ ] Production Deployment
- [ ] Live Demo

---

## License

MIT