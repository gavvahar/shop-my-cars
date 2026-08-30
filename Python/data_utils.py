from pathlib import Path

import pandas as pd

COLUMN_RENAME_MAP = {
    "Make": "make",
    "Model": "model",
    "Year": "year",
    "Engine Fuel Type": "engine_fuel_type",
    "Engine HP": "engine_hp",
    "Engine Cylinders": "engine_cylinders",
    "Transmission Type": "transmission_type",
    "Driven_Wheels": "driven_wheels",
    "Number of Doors": "number_of_doors",
    "Market Category": "market_category",
    "Vehicle Size": "vehicle_size",
    "Vehicle Style": "vehicle_style",
    "highway MPG": "highway_mpg",
    "city mpg": "city_mpg",
    "Popularity": "popularity",
    "MSRP": "msrp",
}

# Small null counts in core spec/filter columns. Dropped rather than
# imputed: fabricating HP/cylinder/door/fuel-type values for real car
# models would misrepresent actual specs.
REQUIRED_COLUMNS = ["Engine HP", "Engine Cylinders", "Number of Doors", "Engine Fuel Type"]

# Generous ceiling for data-entry errors, not legitimate outliers -- even the
# best hybrids in this dataset's model-year range top out well under 100
# highway MPG, so anything above that is safely error territory.
MPG_UPPER_BOUND = 100

DEFAULT_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "cars.csv"


def load_data(path=DEFAULT_DATA_PATH):
    df = pd.read_csv(path)
    df = df.dropna(subset=REQUIRED_COLUMNS)
    # Market Category is heavily null; dropping would lose too much data, so
    # null becomes its own explicit category instead.
    df["Market Category"] = df["Market Category"].fillna("Not Specified")
    df = df[(df["highway MPG"] <= MPG_UPPER_BOUND) & (df["city mpg"] <= MPG_UPPER_BOUND)]
    df = df.rename(columns=COLUMN_RENAME_MAP)
    return df.reset_index(drop=True)
