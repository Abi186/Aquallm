CREATE TABLE farms (
    farm_id SERIAL PRIMARY KEY,
    farm_name VARCHAR(100) NOT NULL,
    location VARCHAR(100),
    farm_area_acres DECIMAL(10,2),
    created_at DATE DEFAULT CURRENT_DATE
);

CREATE TABLE ponds (
    pond_id SERIAL PRIMARY KEY,
    farm_id INTEGER NOT NULL,
    pond_code VARCHAR(20) UNIQUE NOT NULL,
    area_acres DECIMAL(10,2),
    culture_type VARCHAR(50),
    status VARCHAR(30),

    CONSTRAINT fk_pond_farm
        FOREIGN KEY (farm_id)
        REFERENCES farms(farm_id)
);

CREATE TABLE stocking_records (
    stocking_id SERIAL PRIMARY KEY,
    pond_id INTEGER NOT NULL,
    stocking_date DATE NOT NULL,
    species VARCHAR(100),
    seed_count INTEGER,
    avg_seed_weight_g DECIMAL(10,3),
    stocking_density DECIMAL(10,2),

    CONSTRAINT fk_stocking_pond
        FOREIGN KEY (pond_id)
        REFERENCES ponds(pond_id)
);

CREATE TABLE feed_records (
    feed_id SERIAL PRIMARY KEY,
    pond_id INTEGER NOT NULL,
    feed_date DATE NOT NULL,
    doc INTEGER,
    feed_type VARCHAR(50),
    feed_quantity_kg DECIMAL(10,2),
    feeding_frequency INTEGER,

    CONSTRAINT fk_feed_pond
        FOREIGN KEY (pond_id)
        REFERENCES ponds(pond_id)
);

CREATE TABLE water_quality (
    water_id SERIAL PRIMARY KEY,
    pond_id INTEGER NOT NULL,
    measurement_date DATE NOT NULL,
    doc INTEGER,
    temperature_c DECIMAL(5,2),
    ph DECIMAL(4,2),
    dissolved_oxygen DECIMAL(5,2),
    salinity_ppt DECIMAL(6,2),
    ammonia_mg_l DECIMAL(6,3),

    CONSTRAINT fk_water_pond
        FOREIGN KEY (pond_id)
        REFERENCES ponds(pond_id)
);

CREATE TABLE growth_sampling (
    sampling_id SERIAL PRIMARY KEY,
    pond_id INTEGER NOT NULL,
    sampling_date DATE NOT NULL,
    doc INTEGER,
    avg_weight_g DECIMAL(10,2),
    biomass_kg DECIMAL(12,2),
    adg_g DECIMAL(8,3),
    estimated_survival_pct DECIMAL(5,2),

    CONSTRAINT fk_growth_pond
        FOREIGN KEY (pond_id)
        REFERENCES ponds(pond_id)
);

CREATE TABLE harvest_records (
    harvest_id SERIAL PRIMARY KEY,
    pond_id INTEGER NOT NULL,
    harvest_date DATE NOT NULL,
    harvest_quantity_kg DECIMAL(12,2),
    avg_weight_g DECIMAL(10,2),
    survival_pct DECIMAL(5,2),
    total_feed_kg DECIMAL(12,2),
    fcr DECIMAL(6,3),

    CONSTRAINT fk_harvest_pond
        FOREIGN KEY (pond_id)
        REFERENCES ponds(pond_id)
);

