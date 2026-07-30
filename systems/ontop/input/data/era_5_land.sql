CREATE TABLE era5_dataset (
    id              BIGSERIAL PRIMARY KEY,

    source          TEXT NOT NULL DEFAULT 'ERA5-Land',

    year            INTEGER NOT NULL,
    month           INTEGER NOT NULL,

    created_at      TIMESTAMPTZ DEFAULT now(),

    UNIQUE(source, year, month)
);


CREATE TABLE weather_variable (
    id              SERIAL PRIMARY KEY,

    short_name      TEXT NOT NULL UNIQUE,

    description     TEXT NOT NULL,

    units           TEXT
);


CREATE TABLE grid_definition (
    id                  SERIAL PRIMARY KEY,

    nx                  INTEGER NOT NULL,
    ny                  INTEGER NOT NULL,

    latitude_first      DOUBLE PRECISION,
    latitude_last       DOUBLE PRECISION,

    longitude_first     DOUBLE PRECISION,
    longitude_last      DOUBLE PRECISION,

    latitude_step       DOUBLE PRECISION,
    longitude_step      DOUBLE PRECISION
);


CREATE TABLE weather_field (
    id                  BIGSERIAL PRIMARY KEY,

    dataset_id          BIGINT NOT NULL
                        REFERENCES era5_dataset(id),

    variable_id         INTEGER NOT NULL
                        REFERENCES weather_variable(id),

    grid_id             INTEGER NOT NULL
                        REFERENCES grid_definition(id),

    valid_time          TIMESTAMPTZ NOT NULL,

    forecast_step       INTEGER,

    level_type          TEXT,

    level_value         DOUBLE PRECISION,

    values              REAL[],

    metadata            JSONB
);


CREATE INDEX weather_field_time_idx
ON weather_field(valid_time);


CREATE INDEX weather_field_variable_idx
ON weather_field(variable_id);


INSERT INTO weather_variable
(short_name, description, units)
VALUES
('d2m','2 metre dewpoint temperature','K'),
('t2m','2 metre temperature','K'),
('skt','Skin temperature','K'),
('stl1','Soil temperature level 1','K'),
('stl2','Soil temperature level 2','K'),
('stl3','Soil temperature level 3','K'),
('stl4','Soil temperature level 4','K'),
('u10','10 metre U component of wind','m/s'),
('v10','10 metre V component of wind','m/s'),
('sp','Surface pressure','Pa'),
('tp','Total precipitation','m')
ON CONFLICT DO NOTHING;