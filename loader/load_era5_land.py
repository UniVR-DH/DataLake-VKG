import argparse
import json
import tempfile
import zipfile
import os
import shutil

import numpy as np
import psycopg

from eccodes import (
    codes_grib_new_from_file,
    codes_get,
    codes_get_values,
    codes_release
)


VARIABLES = {
    168: "d2m",   # 2m dewpoint temperature
    167: "t2m",   # 2m temperature
    235: "skt",   # skin temperature
    139: "stl1",  # soil temperature level 1
    170: "stl2",
    183: "stl3",
    236: "stl4",
    165: "u10",
    166: "v10",
    134: "sp",
    228: "tp"
}


def get_key(gid, key, default=None):
    try:
        return codes_get(gid, key)
    except Exception:
        return default


def get_variable_id(conn, short_name):

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id
            FROM weather_variable
            WHERE short_name = %s
            """,
            (short_name,)
        )
        row = cur.fetchone()

        if row:
            return row[0]

        raise Exception(
            f"Unknown variable {short_name}"
        )


def get_grid_id(conn, gid):

    nx = get_key(gid, "Ni")
    ny = get_key(gid, "Nj")

    lat1 = get_key(
        gid,
        "latitudeOfFirstGridPointInDegrees"
    )

    lat2 = get_key(
        gid,
        "latitudeOfLastGridPointInDegrees"
    )

    lon1 = get_key(
        gid,
        "longitudeOfFirstGridPointInDegrees"
    )

    lon2 = get_key(
        gid,
        "longitudeOfLastGridPointInDegrees"
    )

    with conn.cursor() as cur:

        cur.execute(
            """
            SELECT id
            FROM grid_definition
            WHERE nx=%s
            AND ny=%s
            AND latitude_first=%s
            AND longitude_first=%s
            LIMIT 1
            """,
            (
                nx,
                ny,
                lat1,
                lon1
            )
        )

        row = cur.fetchone()

        if row:
            return row[0]


        cur.execute(
            """
            INSERT INTO grid_definition
            (
                nx,
                ny,
                latitude_first,
                latitude_last,
                longitude_first,
                longitude_last,
                latitude_step,
                longitude_step
            )
            VALUES
            (%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
            """,
            (
                nx,
                ny,
                lat1,
                lat2,
                lon1,
                lon2,
                abs(lat1-lat2)/(ny-1),
                abs(lon1-lon2)/(nx-1)
            )
        )

        return cur.fetchone()[0]


def get_dataset_id(conn):

    with conn.cursor() as cur:

        cur.execute(
            """
            INSERT INTO era5_dataset
            (
                source,
                year,
                month
            )
            VALUES
            (
                'ERA5-Land',
                2020,
                11
            )
            ON CONFLICT(source,year,month)
            DO UPDATE SET year=EXCLUDED.year
            RETURNING id
            """
        )

        return cur.fetchone()[0]


def parse_time(gid):

    year = get_key(gid, "yearOfCentury")
    month = get_key(gid, "month")
    day = get_key(gid, "day")
    hour = get_key(gid, "hour")

    century = get_key(
        gid,
        "centuryOfReferenceTimeOfData",
        21
    )

    year = (century - 1) * 100 + year

    import datetime

    return datetime.datetime(
        year,
        month,
        day,
        hour,
        tzinfo=datetime.timezone.utc
    )


def insert_message(conn, dataset_id, gid):

    parameter = get_key(
        gid,
        "indicatorOfParameter"
    )

    if parameter not in VARIABLES:
        return


    short_name = VARIABLES[parameter]


    variable_id = get_variable_id(
        conn,
        short_name
    )


    grid_id = get_grid_id(
        conn,
        gid
    )


    values = np.array(
        codes_get_values(gid),
        dtype=np.float32
    )


    valid_time = parse_time(gid)


    step = get_key(
        gid,
        "P1",
        0
    )


    metadata = {
        "edition":
            get_key(gid,"editionNumber"),

        "parameter":
            parameter,

        "centre":
            get_key(gid,"centre"),

        "gridType":
            get_key(gid,"gridType")
    }


    with conn.cursor() as cur:

        cur.execute(
            """
            INSERT INTO weather_field
            (
                dataset_id,
                variable_id,
                grid_id,
                valid_time,
                forecast_step,
                level_type,
                level_value,
                values,
                metadata
            )
            VALUES
            (
                %s,%s,%s,%s,
                %s,%s,%s,%s,%s
            )
            """,
            (
                dataset_id,
                variable_id,
                grid_id,
                valid_time,
                step,
                get_key(
                    gid,
                    "indicatorOfTypeOfLevel"
                ),
                get_key(
                    gid,
                    "level"
                ),
                values.tobytes(),
                json.dumps(metadata)
            )
        )


def load_grib_file(conn, filename, dataset_id):

    print("Reading:", filename)

    with open(filename, "rb") as f:

        count = 0

        while True:

            gid = codes_grib_new_from_file(f)

            if gid is None:
                break

            try:
                insert_message(conn, dataset_id, gid)
                count += 1
                if count % 50 == 0:
                    conn.commit()
                    print(f"Committed {count} messages so far...")
            finally:
                codes_release(gid)
    conn.commit()
    print("Imported messages:", count)


def load_zip(zip_path, db):

    with psycopg.connect(db) as conn:

        dataset_id = get_dataset_id(
            conn
        )


        with zipfile.ZipFile(zip_path) as archive:

            for item in archive.infolist():

                if item.filename.endswith(
                    (
                        ".grib",
                        ".grb",
                        ".grib1"
                    )
                ):

                    print(
                        "Extracting:",
                        item.filename
                    )

                    with tempfile.NamedTemporaryFile(delete=False) as tmp:
                        with archive.open(item) as source:
                            shutil.copyfileobj(source, tmp, length=1024 * 1024)  # 1MB chunks
                        tmp_path = tmp.name


                    try:

                        load_grib_file(
                            conn,
                            tmp_path,
                            dataset_id
                        )

                        conn.commit()


                    finally:

                        os.remove(
                            tmp_path
                        )


if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "zipfile"
    )

    parser.add_argument(
        "--db",
        required=True
    )

    args = parser.parse_args()


    load_zip(
        args.zipfile,
        args.db
    )