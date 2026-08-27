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
            return [dict(zip(columns, row, strict=True)) for row in cur.fetchall()]


def search_cars(max_price=None, vehicle_style=None, fuel_type=None, limit=15):
    conditions = []
    params = []

    if max_price is not None:
        conditions.append("msrp <= %s")
        params.append(max_price)
    if vehicle_style is not None:
        conditions.append("vehicle_style ILIKE %s")
        params.append(f"%{vehicle_style}%")
    if fuel_type is not None:
        conditions.append("engine_fuel_type ILIKE %s")
        params.append(f"%{fuel_type}%")

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"SELECT {CARS_COLUMNS} FROM cars {where_clause} ORDER BY msrp ASC LIMIT %s"
    params.append(limit)

    with _pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row, strict=True)) for row in cur.fetchall()]
