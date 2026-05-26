# CatalogIQ

CatalogIQ is an enterprise-style, AI-native data catalog workspace for profiling datasets, generating metadata, identifying sensitive fields, producing governance outputs, and building reusable data product packages.

## Current capabilities

- Premium Command Center launcher
- Agentic Catalog Workspace
- CSV / Excel profiling
- AWS S3 connector starter
- Snowflake connector starter
- Field-level catalog generation
- Business glossary generation
- Data dictionary generation
- Governance review output
- Data quality rule suggestions
- Data product export package
- Local workspace asset publishing
- Local-only connector profile store

## Run

Open PowerShell and run:

cd C:\Users\mokha\catalogiq
.\.venv\Scripts\Activate.ps1
python -m app.catalogiq_command_center

Or double-click:

CatalogIQ_Command_Center_v7.cmd

## Environment variables

Copy .env.example to .env and put real values only in .env.

Never commit .env.

OPENAI_API_KEY=
AWS_PROFILE=
SNOWFLAKE_ACCOUNT=
SNOWFLAKE_USER=
SNOWFLAKE_PASSWORD=

## Connector profiles

Phase 8 adds local-only connector profile storage under:

.catalogiq_local/

This folder is ignored by Git.

Connector profiles should store reusable non-secret settings and environment variable names, not raw passwords, API keys, or access keys.

## Healthcheck

python -m app.phase8_healthcheck

## Git safety

Secrets, local data, generated exports, local profiles, and virtual environments are ignored by .gitignore.
