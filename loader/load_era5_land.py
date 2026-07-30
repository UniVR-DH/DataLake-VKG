import argparse
import json
import numpy as np
import psycopg

from eccodes import (
    codes_grib_new_from_file,
    codes_get,
    codes_get_values,
    codes_get_array,
    codes_release
)

VARIABLES = {
    167: "t2m",
    228: "tp"
}

def get_key(gid, key, default=None):
    try:
        return codes_get(gid, key)
    except Exception:
        return default

def get_variable_id(conn, short_name):
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM weather_variable WHERE short_name=%s", (short_name,))
        row = cur.fetchone()
        if row:
            return row[0]
        raise Exception(f"Unknown variable {short_name}")

def get_dataset_id(conn):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO era5_dataset (source, year, month)
            VALUES ('ERA5-Land', 2020, 11)
            ON CONFLICT (source, year, month)
            DO UPDATE SET year=EXCLUDED.year
            RETURNING id
        """)
        return cur.fetchone()[0]

def parse_time(gid):
    year = get_key(gid, "yearOfCentury")
    month = get_key(gid, "month")
    day = get_key(gid, "day")
    hour = get_key(gid, "hour")
    century = get_key(gid, "centuryOfReferenceTimeOfData", 21)
    year = (century - 1) * 100 + year

    import datetime
    return datetime.datetime(year, month, day, hour, tzinfo=datetime.timezone.utc)

def insert_message(conn, dataset_id, gid):
    parameter = get_key(gid, "indicatorOfParameter")
    if parameter not in VARIABLES:
        return

    short_name = VARIABLES[parameter]
    variable_id = get_variable_id(conn, short_name)

    valid_time = parse_time(gid)

    # Read grid values
    values = np.array(codes_get_values(gid), dtype=np.float32)

    # Read lat/lon arrays
    lats = np.array(codes_get_array(gid, "latitudes"), dtype=np.float64)
    lons = np.array(codes_get_array(gid, "longitudes"), dtype=np.float64)

    with conn.cursor() as cur:
        for lat, lon, val in zip(lats, lons, values):

            cur.execute("""
                INSERT INTO weather_point
                (dataset_id, variable_id, valid_time, lat, lon)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (dataset_id, variable_id, valid_time, lat, lon))

            point_id = cur.fetchone()[0]

            if short_name == "t2m":
                cur.execute(
                    "INSERT INTO weather_point_t2m (point_id, value) VALUES (%s, %s)",
                    (point_id, float(val))
                )

            elif short_name == "tp":
                cur.execute(
                    "INSERT INTO weather_point_tp (point_id, value) VALUES (%s, %s)",
                    (point_id, float(val))
                )

def load_grib_file(conn, filename, dataset_id):
    print("Reading:", filename)
    count = 0

    with open(filename, "rb") as f:
        while True:
            gid = codes_grib_new_from_file(f)
            if gid is None:
                break

            try:
                insert_message(conn, dataset_id, gid)
                count += 1
                if count % 1 == 0:
                    conn.commit()
                    print(f"Committed {count} messages so far...")
            finally:
                codes_release(gid)

    conn.commit()
    print("Imported messages:", count)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("gribfile")
    parser.add_argument("--db", required=True)
    args = parser.parse_args()

    with psycopg.connect(args.db) as conn:
        dataset_id = get_dataset_id(conn)
        load_grib_file(conn, args.gribfile, dataset_id)

if __name__ == "__main__":
    main()
