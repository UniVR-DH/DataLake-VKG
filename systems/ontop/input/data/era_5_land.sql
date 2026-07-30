-- ============================================================
-- ERA5-Land point-based schema
-- ============================================================

CREATE TABLE era5_dataset (
    id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    UNIQUE (source, year, month)
);

CREATE TABLE weather_variable (
    id BIGSERIAL PRIMARY KEY,
    short_name TEXT UNIQUE NOT NULL,
    description TEXT
);

INSERT INTO weather_variable (short_name, description) VALUES
('t2m', '2m temperature'),
('tp', 'Total precipitation');

CREATE TABLE weather_point (
    id BIGSERIAL PRIMARY KEY,
    dataset_id BIGINT NOT NULL REFERENCES era5_dataset(id),
    variable_id BIGINT NOT NULL REFERENCES weather_variable(id),
    valid_time TIMESTAMPTZ NOT NULL,
    lat DOUBLE PRECISION NOT NULL,
    lon DOUBLE PRECISION NOT NULL
);

CREATE TABLE weather_point_t2m (
    point_id BIGINT PRIMARY KEY REFERENCES weather_point(id) ON DELETE CASCADE,
    value DOUBLE PRECISION NOT NULL
);

CREATE TABLE weather_point_tp (
    point_id BIGINT PRIMARY KEY REFERENCES weather_point(id) ON DELETE CASCADE,
    value DOUBLE PRECISION NOT NULL
);

CREATE INDEX weather_point_time_idx ON weather_point(valid_time);
CREATE INDEX weather_point_var_idx ON weather_point(variable_id);
CREATE INDEX weather_point_lat_lon_idx ON weather_point(lat, lon);
