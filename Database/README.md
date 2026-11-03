# AquaLLM Database

This folder contains the PostgreSQL database scripts used by AquaLLM.

## Files

01_create_database.sql
Creates the AquaLLM database.

02_create_tables.sql
Creates the eight relational tables.

03_insert_sample_data.sql
Contains optional SQL-based sample data insertion.

04_validation_queries.sql
Contains database integrity and validation queries.

05_analysis_queries.sql
Contains analytical queries used for testing and future NL-to-SQL development.

## Tables

1. farms
2. ponds
3. stocking_records
4. feed_records
5. water_quality
6. growth_sampling
7. harvest_records
8. users

## Relationships

farms
  |
  └── ponds
        |
        ├── stocking_records
        ├── feed_records
        ├── water_quality
        ├── growth_sampling
        └── harvest_records

users is independent and will be used for authentication.