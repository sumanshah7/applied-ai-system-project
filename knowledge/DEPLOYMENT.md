# Deployment Guide

This document describes how the sample application is deployed and operated in
production. It is stored in a separate `knowledge/` source to demonstrate
DocuBot retrieving across multiple documentation folders.

## Deploying the Application

The application is deployed as a container. Build the image with `make build`
and push it to the registry using `make release`. The production process is
started with `gunicorn app:app --workers 4`.

Deployments are gated behind a health check. The orchestrator will not route
traffic to a new container until the `/health` endpoint returns HTTP 200.

## Environment and Secrets

Production secrets are injected at deploy time and are never committed to the
repository. The deploy pipeline requires these variables to be present:

- `DATABASE_URL`
- `AUTH_SECRET_KEY`
- `SENTRY_DSN` (optional, enables error reporting)

If a required secret is missing, the deploy step fails fast before any traffic
is shifted.

## Rate Limiting

Public endpoints are protected by a rate limiter. By default each client IP is
allowed 100 requests per minute. When the limit is exceeded the API returns an
HTTP 429 response with a `Retry-After` header.

## Rollback

If a deploy causes elevated error rates, roll back with `make rollback`, which
re-points traffic to the previous healthy container image.
