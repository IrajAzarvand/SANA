# Development database reset

`scripts/reset_dev_db.sh` rebuilds the SANA **development** database from scratch.

## What it does

1. Requires an explicit `SANA_ENV=development`, `--confirm-reset`, and typed confirmation `RESET sana_db`.
2. Refuses to continue unless Django points at the local database `sana_db` and currently uses `DB_USER=sana_user`.
3. Refuses to continue while `sana-gps.service` is active.
4. Ensures the cluster-wide roles `sana_owner`, `sana_migrator`, `sana_backend`, and `sana_gps` exist. Existing passwords are not reset.
5. Drops and recreates `sana_db`, installs PostGIS, runs Django migrations, provisions GPS tables, and reapplies grants.
6. Runs `manage.py check` and offers to create a Django superuser interactively.

## Run it

From the SANA repository root, on a **development machine only**:

```bash
SANA_ENV=development bash scripts/reset_dev_db.sh --confirm-reset
```

You will be asked to type `RESET sana_db`. The GPS schema step prompts for the existing `sana_migrator` password. The superuser step prompts normally through Django. No password is written into the repository.

## Important safeguards and limitations

- **Destructive:** every row in `sana_db` is deleted. Back up anything you need first.
- Never run on the company/production server or any database containing real fleet/GPS data.
- PostgreSQL roles are cluster-wide; dropping the database does not delete them or their passwords.
- The script expects the current Django migration connection to be `sana_user`. It grants `sana_backend` data access for later migration to the runtime role, but does not change Django's `.env` or switch the live backend connection.
- The script deliberately does not stop/start services. If `sana-gps.service` is active, it exits before dropping the database.
- It assumes PostgreSQL tools and `sudo` are installed, the existing role `sana_user` is available, and the repository's current GPS SQL files match the current Django fleet tables.
- For a completely fresh PostgreSQL cluster, install PostgreSQL/PostGIS and provision the legacy `sana_user` role/password first. This script preserves existing role passwords; it does not invent or store passwords.
