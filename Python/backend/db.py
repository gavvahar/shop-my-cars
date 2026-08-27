from psycopg_pool import ConnectionPool

from .db_config import connection_string

_pool = ConnectionPool(conninfo=connection_string(), open=True)
_pool.wait(timeout=30)

CARS_COLUMNS = (
    "id, make, model, year, engine_fuel_type, engine_hp, engine_cylinders, "
    "transmission_type, driven_wheels, number_of_doors, market_category, "
    "vehicle_size, vehicle_style, highway_mpg, city_mpg, popularity, msrp"
)


def get_car_count():
    with _pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM cars")
            return cur.fetchone()[0]


def get_sample_cars(limit=5):
    with _pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT {CARS_COLUMNS} FROM cars LIMIT %s", (limit,))
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]
