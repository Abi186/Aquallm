-- ==========================================
-- AquaLLM Database Validation
-- ==========================================

-- 1. Count records
SELECT COUNT(*) AS total_farms FROM farms;

SELECT COUNT(*) AS total_ponds FROM ponds;

SELECT COUNT(*) AS total_stocking_records
FROM stocking_records;

SELECT COUNT(*) AS total_feed_records
FROM feed_records;

SELECT COUNT(*) AS total_water_records
FROM water_quality;

SELECT COUNT(*) AS total_growth_records
FROM growth_sampling;

SELECT COUNT(*) AS total_harvest_records
FROM harvest_records;


-- 2. Check ponds without farms
SELECT p.*
FROM ponds p
LEFT JOIN farms f
    ON p.farm_id = f.farm_id
WHERE f.farm_id IS NULL;


-- 3. Check feed records without ponds
SELECT fr.*
FROM feed_records fr
LEFT JOIN ponds p
    ON fr.pond_id = p.pond_id
WHERE p.pond_id IS NULL;


-- 4. Check water records without ponds
SELECT wq.*
FROM water_quality wq
LEFT JOIN ponds p
    ON wq.pond_id = p.pond_id
WHERE p.pond_id IS NULL;


-- 5. Check growth records without ponds
SELECT gs.*
FROM growth_sampling gs
LEFT JOIN ponds p
    ON gs.pond_id = p.pond_id
WHERE p.pond_id IS NULL;


-- 6. Check harvest records without ponds
SELECT h.*
FROM harvest_records h
LEFT JOIN ponds p
    ON h.pond_id = p.pond_id
WHERE p.pond_id IS NULL;