# France adapter

Export CSVs with `python main.py --output /path/to/new/output`.
The validator enforces the five requested submission rules.

For a real database connection, install `requirements.txt` in a virtual environment,
set `DATABASE_URL` to your connection URL, and run:

```sh
python main.py --check-db
```

Both `postgresql+psycopg://` and `postgresql://` URLs are accepted.
The command reads server metadata in a read-only transaction and reports target
columns and constraints. It does not insert data. Credentials are not embedded
in source files. Do not commit credentials.

CSV conversion remains independent of database access. Generated `load.sql` is a
separate initial-import operation; existing primary-key collisions roll back the
transaction. The path quoting supports apostrophes in directory names.
