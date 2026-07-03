# Role → Permission Matrix

**Status:** Authoritative — produced by Phase 1 / P1.12.
**Decisions:** D-026 (RBAC), D-036 (least-privilege), D-043 (Supabase UUID sync point).
**Seed script:** `scripts/imports/seed_rbac.py` (this document and that script must remain in sync).
**Phase 2 note:** This matrix is the contract consumed by Phase 2 JWT/RBAC enforcement. Do not modify either this document or the seed script without updating both.

---

## Roles

| Role | Description |
|---|---|
| **Admin** | Full access; manages users, audit log, and all data operations. |
| **Data Curator** | Manages alumni/career/company data and runs import pipeline; cannot manage users or view audit log. |
| **Faculty Viewer** | Read-only view of validated alumni, career, company data, and analytics; cannot write or import. |
| **Read Only** | Same read scope as Faculty Viewer; intended for external stakeholders with minimal access. |

---

## Permissions

| Permission | Description |
|---|---|
| `alumni:read` | View validated alumni records |
| `alumni:write` | Create/update alumni records |
| `alumni:validate` | Approve or reject pending alumni |
| `alumni:delete` | Delete or permanently reject alumni (Admin only) |
| `career:read` | View career records |
| `career:write` | Create/update career records |
| `company:read` | View company and alias data |
| `company:write` | Create/update company records and aliases |
| `import:run` | Execute import pipeline |
| `dedup:review` | Action items on deduplication queue |
| `snapshot:manage` | Open/finalize a refresh snapshot |
| `audit:read` | View audit log entries |
| `user:manage` | Provision or deactivate application users |
| `analytics:read` | Access aggregation and dashboard endpoints |

---

## Assignment Matrix

`✓` = granted · `—` = not granted

| Permission | Admin | Data Curator | Faculty Viewer | Read Only |
|---|:---:|:---:|:---:|:---:|
| `alumni:read` | ✓ | ✓ | ✓ | ✓ |
| `alumni:write` | ✓ | ✓ | — | — |
| `alumni:validate` | ✓ | ✓ | — | — |
| `alumni:delete` | ✓ | — | — | — |
| `career:read` | ✓ | ✓ | ✓ | ✓ |
| `career:write` | ✓ | ✓ | — | — |
| `company:read` | ✓ | ✓ | ✓ | ✓ |
| `company:write` | ✓ | ✓ | — | — |
| `import:run` | ✓ | ✓ | — | — |
| `dedup:review` | ✓ | ✓ | — | — |
| `snapshot:manage` | ✓ | ✓ | — | — |
| `audit:read` | ✓ | — | — | — |
| `user:manage` | ✓ | — | — | — |
| `analytics:read` | ✓ | ✓ | ✓ | ✓ |

**Totals:** Admin 14 / Data Curator 11 / Faculty Viewer 4 / Read Only 4

---

## Design Rationale

- **Least-privilege (D-036):** Faculty Viewer and Read Only are identical in this Phase 1 seed. The distinction is kept for forward compatibility — Phase 5/6 may introduce scoped analytics or filtered record sets per role.
- **`alumni:delete` Admin-only:** Deletion of alumni is irreversible and audit-critical. Curators can reject (`alumni:validate`) without deleting.
- **`audit:read` Admin-only:** Audit logs contain change history for all records; restricting view to Admin prevents curators from reading each other's edits.
- **`user:manage` Admin-only:** Provisioning/deactivating users is an administrative operation (D-026). Phase 2 wires this to Supabase Auth (D-043).
- **No `analytics:write`:** Analytics outputs are derived from data; there is no concept of writing analytics (all writes go through `alumni:write`, `career:write`, etc.).
