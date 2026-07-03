<h1 align="center">PRISM - Professional Relationship Intelligence & Statistics Manager</h1>

<p align="center">
<b>Modern Alumni Intelligence Platform for Higher Education</b>
</p>

<p align="center">

![Python](https://img.shields.io/badge/Python-3.12-blue?style=for-the-badge&logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.116-success?style=for-the-badge&logo=fastapi)
![Next.js](https://img.shields.io/badge/Next.js-16-black?style=for-the-badge&logo=nextdotjs)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17-blue?style=for-the-badge&logo=postgresql)
![Supabase](https://img.shields.io/badge/Supabase-Backend-3ECF8E?style=for-the-badge&logo=supabase)
![TypeScript](https://img.shields.io/badge/TypeScript-5-blue?style=for-the-badge&logo=typescript)
![MIT License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

</p>

---

# PRISM

**PRISM (Professional Relationship Intelligence & Statistics Manager)** is a full-stack Alumni Intelligence Platform designed for higher education institutions.

Instead of functioning as an operational alumni management system, PRISM focuses on transforming fragmented alumni records into a **single source of truth** through deterministic ETL, snapshot-based analytics, and interactive executive dashboards.

The platform enables universities to understand:

- Where alumni work
- Which companies hire graduates
- Career progression & seniority
- Industry distribution
- Geographic distribution
- Graduate outcomes by study program
- Historical changes using quarterly snapshots

Built as a **portfolio-grade enterprise application** using FastAPI, Next.js, PostgreSQL, and Supabase.

---

# Why PRISM?

Traditional alumni databases primarily store information.

PRISM goes beyond storage by providing a complete analytics workflow:

- Deterministic data curation
- Snapshot-based reporting
- Interactive executive dashboards
- Quarterly alumni refresh workflow
- Role-based access control
- Complete audit logging

The platform is designed specifically for institutional analytics and strategic decision making.

---

# Features

## Analytics

- Executive KPI Dashboard
- Alumni Overview
- Career Outcomes
- Top Employers
- Industry Analytics
- Sector Distribution
- Geographic Analytics
- Graduation Trends
- Alumni Directory
- Alumni Detail Page
- Snapshot Comparison
- Global Filtering

---

## Data Curation

PRISM provides a deterministic ETL pipeline.

Features include:

- CSV Import
- XLSX Import
- Data Validation
- Program Validation
- Company Normalization
- Role Normalization
- Seniority Classification
- Duplicate Detection
- Quarterly Snapshot Commit
- Validation Workflow
- Audit Logging

---

## Security

Authentication

- Supabase Authentication
- JWT Verification

Authorization

- Database-driven RBAC
- Permission-based APIs

Roles

- Administrator
- Data Curator
- Faculty Viewer
- Read Only

---

# Architecture

```
                    CSV / XLSX
                         │
                         ▼
               Import Pipeline
                         │
                         ▼
             Validation Engine
                         │
                         ▼
          Company Normalization
                         │
                         ▼
           Role Classification
                         │
                         ▼
         Deterministic Deduplication
                         │
                         ▼
          Quarterly Snapshot Engine
                         │
                         ▼
               PostgreSQL Database
                         │
        ┌────────────────┴────────────────┐
        ▼                                 ▼
 Analytics API                    Curator API
        │
        ▼
   Next.js Dashboard
```

---

# Tech Stack

## Backend

- FastAPI
- SQLAlchemy 2.0
- Alembic
- PostgreSQL
- Supabase
- Pydantic v2
- PyJWT

---

## Frontend

- Next.js 16
- TypeScript
- Tailwind CSS
- shadcn/ui
- Apache ECharts
- React Hook Form

---

## Infrastructure

- Railway
- Vercel
- Supabase
- GitHub Actions

---

# Screenshots

> Screenshots will be added after production deployment.

| Dashboard | Directory |
|-----------|-----------|
| Coming Soon | Coming Soon |

| Companies | Career |
|-----------|---------|
| Coming Soon | Coming Soon |

| Geography | Import Pipeline |
|-----------|----------------|
| Coming Soon | Coming Soon |

---

# Project Structure

```
prism/
│
├── backend/
│   └── fastapi-app/
│       ├── app/
│       ├── migrations/
│       ├── tests/
│       └── README.md
│
├── frontend/
│   └── nextjs-app/
│       ├── app/
│       ├── components/
│       ├── hooks/
│       ├── lib/
│       └── README.md
│
├── database/
│   ├── migrations/
│   └── schema/
│
├── docs/
│   ├── architecture/
│   ├── decisions/
│   └── assets/
│
├── data/
│   └── synthetic/
│
├── scripts/
│
└── README.md
```

---

# Local Development

## Backend

```bash
cd backend/fastapi-app

uv sync

cp .env.example .env

uv run uvicorn app.main:app --reload
```

Backend

```
http://localhost:8000
```

Swagger

```
http://localhost:8000/docs
```

---

## Frontend

```bash
cd frontend/nextjs-app

pnpm install

cp .env.example .env.local

pnpm dev
```

Frontend

```
http://localhost:3000
```

---

# Environment Variables

Backend

```env
DATABASE_URL=

SUPABASE_URL=

SUPABASE_ANON_KEY=

SUPABASE_SERVICE_ROLE_KEY=

JWT_SECRET=
```

Frontend

```env
NEXT_PUBLIC_API_URL=

NEXT_PUBLIC_SUPABASE_URL=

NEXT_PUBLIC_SUPABASE_ANON_KEY=
```

---

# Testing

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

# Deployment

| Component | Platform |
|-----------|----------|
| Frontend | Vercel |
| Backend | Railway |
| Database | Supabase |
| Authentication | Supabase Auth |

---

# Documentation

Architecture documentation is available inside:

```
docs/
```

Includes:

- Architecture
- ER Diagram
- Roadmap
- Engineering Decisions
- Production Readiness
- Curator Runbook
- Deployment Guide

---

# Project Status

Current Status

✅ MVP Complete

Current Phase

**Phase 7 — Production Deployment**

Quality Gates

✅ Ruff

✅ Black

✅ MyPy Strict

✅ Pytest

✅ ESLint

✅ TypeScript

✅ Next.js Build

---

# Roadmap

- [x] Foundations
- [x] Database Design
- [x] Authentication
- [x] Authorization (RBAC)
- [x] Import Pipeline
- [x] Validation Workflow
- [x] Company Normalization
- [x] Role Classification
- [x] Deduplication
- [x] Snapshot Engine
- [x] Analytics API
- [x] Dashboard UI
- [x] Documentation
- [ ] Production Deployment
- [ ] Live Demo

---

# License

MIT License

---

# Author

**Arkan Syafiq At'taqy**

Bachelor of Science in Data Science Technology

Universitas Airlangga

Portfolio

> https://arknsa.vercel.app

GitHub

> https://github.com/arknsa