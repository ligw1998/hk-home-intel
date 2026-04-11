# Optional Docker Support

Docker is not required for local Phase 0 development.

Recommended default workflow:

- API and worker run directly from the `py311` conda environment
- Web app runs from the local Node runtime
- Database defaults to SQLite for the bootstrap stage

If Docker is installed later, keep it narrow:

- use it for PostgreSQL/PostGIS only
- keep API and web in local dev mode unless containerization becomes useful

See `compose.optional.yml` for a minimal future baseline.

