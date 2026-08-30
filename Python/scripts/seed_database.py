import sys, psycopg
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.db_config import connection_string
from data_utils import load_data

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS cars (
    id SERIAL PRIMARY KEY,
    make TEXT NOT NULL,
    model TEXT NOT NULL,
    year INTEGER NOT NULL,
    engine_fuel_type TEXT NOT NULL,
    engine_hp REAL NOT NULL,
    engine_cylinders INTEGER NOT NULL,
    transmission_type TEXT NOT NULL,
    driven_wheels TEXT NOT NULL,
    number_of_doors INTEGER NOT NULL,
    market_category TEXT NOT NULL,
    vehicle_size TEXT NOT NULL,
    vehicle_style TEXT NOT NULL,
    highway_mpg INTEGER NOT NULL,
    city_mpg INTEGER NOT NULL,
    popularity INTEGER NOT NULL,
    msrp INTEGER NOT NULL
)
"""

COLUMNS = [
    "make",
    "model",
    "year",
    "engine_fuel_type",
    "engine_hp",
    "engine_cylinders",
    "transmission_type",
    "driven_wheels",
    "number_of_doors",
    "market_category",
    "vehicle_size",
    "vehicle_style",
    "highway_mpg",
    "city_mpg",
    "popularity",
    "msrp",
]


def _to_row(record):
    return (
        record["make"],
        record["model"],
        int(record["year"]),
        record["engine_fuel_type"],
        float(record["engine_hp"]),
        int(record["engine_cylinders"]),
        record["transmission_type"],
        record["driven_wheels"],
        int(record["number_of_doors"]),
        record["market_category"],
        record["vehicle_size"],
        record["vehicle_style"],
        int(record["highway_mpg"]),
        int(record["city_mpg"]),
        int(record["popularity"]),
        int(record["msrp"]),
    )


def seed():
    df = load_data()

    with psycopg.connect(connection_string()) as conn:
        with conn.cursor() as cur:
            cur.execute(CREATE_TABLE_SQL)
            cur.execute("TRUNCATE TABLE cars RESTART IDENTITY")

            copy_sql = f"COPY cars ({', '.join(COLUMNS)}) FROM STDIN"
            with cur.copy(copy_sql) as copy:
                for record in df[COLUMNS].to_dict(orient="records"):
                    copy.write_row(_to_row(record))

    print(f"Seeded {len(df)} rows into cars.")


if __name__ == "__main__":
    seed()
