"""Verification (Task 3): confirm a live connection to the existing
ask-my-cars Postgres instance returns real rows.

Run directly: python Python/scripts/spike_db_connection.py
"""

import os, psycopg

conninfo = psycopg.conninfo.make_conninfo(
    dbname=os.environ["POSTGRES_DB"],
    user=os.environ["POSTGRES_USER"],
    password=os.environ["POSTGRES_PASSWORD"],
    host=os.environ.get("POSTGRES_HOST", "localhost"),
    port=os.environ.get("POSTGRES_PORT", "5432"),
)


def main():
    with psycopg.connect(conninfo) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM cars")
            count = cur.fetchone()[0]
            print(f"cars table row count: {count}")

            cur.execute("SELECT make, model, year, msrp FROM cars LIMIT 3")
            print("\nSample rows:")
            for row in cur.fetchall():
                print(row)


if __name__ == "__main__":
    main()
