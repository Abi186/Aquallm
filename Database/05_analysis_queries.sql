-- ==========================================
-- AquaLLM Analytical Queries
-- ==========================================


-- 1. Show all farms and their ponds

SELECT
    f.farm_name,
    f.location,
    p.pond_code,
    p.area_acres
FROM farms f
JOIN ponds p
    ON f.farm_id = p.farm_id
ORDER BY f.farm_id, p.pond_code;


-- 2. Average FCR by farm

SELECT
    f.farm_name,
    ROUND(AVG(h.fcr), 2) AS average_fcr
FROM farms f
JOIN ponds p
    ON f.farm_id = p.farm_id
JOIN harvest_records h
    ON p.pond_id = h.pond_id
GROUP BY f.farm_name
ORDER BY average_fcr;


-- 3. Highest FCR ponds

SELECT
    p.pond_code,
    h.fcr
FROM ponds p
JOIN harvest_records h
    ON p.pond_id = h.pond_id
ORDER BY h.fcr DESC;


-- 4. Highest biomass ponds

SELECT
    p.pond_code,
    g.biomass_kg
FROM ponds p
JOIN growth_sampling g
    ON p.pond_id = g.pond_id
WHERE g.doc = 100
ORDER BY g.biomass_kg DESC;


-- 5. Average water quality by pond

SELECT
    p.pond_code,
    ROUND(AVG(w.dissolved_oxygen), 2) AS avg_do,
    ROUND(AVG(w.ph), 2) AS avg_ph,
    ROUND(AVG(w.temperature_c), 2) AS avg_temperature
FROM ponds p
JOIN water_quality w
    ON p.pond_id = w.pond_id
GROUP BY p.pond_code
ORDER BY p.pond_code;


-- 6. Ponds with low dissolved oxygen

SELECT
    p.pond_code,
    w.measurement_date,
    w.dissolved_oxygen
FROM ponds p
JOIN water_quality w
    ON p.pond_id = w.pond_id
WHERE w.dissolved_oxygen < 4
ORDER BY w.dissolved_oxygen;


-- 7. Ponds with poor survival

SELECT
    p.pond_code,
    h.survival_pct
FROM ponds p
JOIN harvest_records h
    ON p.pond_id = h.pond_id
WHERE h.survival_pct < 70
ORDER BY h.survival_pct;


-- 8. Total harvest by farm

SELECT
    f.farm_name,
    SUM(h.harvest_quantity_kg) AS total_harvest_kg
FROM farms f
JOIN ponds p
    ON f.farm_id = p.farm_id
JOIN harvest_records h
    ON p.pond_id = h.pond_id
GROUP BY f.farm_name
ORDER BY total_harvest_kg DESC;