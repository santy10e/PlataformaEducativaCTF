# CYBERLAB technical contract

## Fixed stack
Python 3.12, FastAPI, SQLAlchemy 2.x, Alembic, MySQL 8.4 (compatible with 8.0+), Node 22 LTS, React, Vite, TypeScript, Tailwind built locally, Nginx and Docker Compose. Backend dependency management uses uv.

## Data
BIGINT UNSIGNED auto-increment primary keys; public UUIDs for student-facing URLs. DATETIME(6) in UTC; school timezone defaults to America/Guayaquil. utf8mb4, utf8mb4_0900_ai_ci, InnoDB. Plural snake_case table names. created_at and updated_at; deleted_at for challenges and events.

## API and sessions
JSON API under /api/v1. Pagination uses page/page_size and returns items/total/page/page_size. Errors use {"error":{"code":"STABLE_CODE","message":"...","details":{}}}. Server-side sessions, HTTP-only cookies, Secure in production, SameSite=Lax, and CSRF header tokens for mutations. Permissions are resource.action strings enforced with require_permission. Domain events use a synchronous internal bus.

## Frontend
Feature folders, OpenAPI-generated API client, CSS variable design tokens and a local Tailwind preset. No CDN dependencies. No ad hoc hex colors in components.

## Repository commands
make up, down, test, lint, migrate, seed and reset-db.
