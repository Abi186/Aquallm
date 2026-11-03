# AquaLLM Project Progress

## Project Title

AquaLLM – A Confidence-Aware Aquaculture Intelligence Platform

---

# Phase 1 – Data and Database Foundation

## Objective

Create a realistic aquaculture data foundation for the AquaLLM
system without requiring confidential real-world farm data.

## Technology

- PostgreSQL
- Python
- Pandas
- NumPy
- Google Colab
- VS Code
- pgAdmin

## Step 1 – Database Design

Designed eight relational tables:

1. farms
2. ponds
3. stocking_records
4. feed_records
5. water_quality
6. growth_sampling
7. harvest_records
8. users

## Step 2 – Database Relationships

The main relationship is:

farms → ponds

Each pond is associated with:

- stocking records
- feed records
- water-quality records
- growth-sampling records
- harvest records

## Step 3 – Synthetic Dataset

Because confidential real-world farm data is unavailable,
a synthetic dataset was designed.

Dataset target:

- 5 farms
- 30 ponds
- 30 stocking records
- approximately 3,000 feed records
- approximately 3,000 water-quality records
- approximately 300 growth records
- 30 harvest records

## Step 4 – Synthetic Data Generation

Python was used in Google Colab.

Libraries:

pandas
numpy
faker
psycopg2-binary

The dataset was generated with relationships between:

- DOC
- feed quantity
- water quality
- shrimp growth
- biomass
- survival
- FCR

## Step 5 – Data Validation

The generated data was checked for:

- missing values
- duplicate records
- invalid pond references
- negative biomass
- invalid ADG
- invalid survival percentages
- invalid water-quality values
- abnormal FCR values

## Step 6 – Data Export

The generated DataFrames were exported to CSV:

farms.csv
ponds.csv
stocking_records.csv
feed_records.csv
water_quality.csv
growth_sampling.csv
harvest_records.csv

## Step 7 – PostgreSQL Loading

CSV data was loaded into PostgreSQL using Python and psycopg2.

The loading order follows the foreign-key dependencies:

1. farms
2. ponds
3. stocking_records
4. feed_records
5. water_quality
6. growth_sampling
7. harvest_records

## Step 8 – SQL Validation

JOIN queries were used to verify that:

- farms connect to ponds
- ponds connect to operational records
- harvest records connect to ponds
- analytical queries return meaningful results

---

# Current Status

Phase 1: Database and data foundation – IN PROGRESS / COMPLETED AFTER VALIDATION

Database schema – Completed

Synthetic dataset generation – Completed

Dataset validation – Completed

CSV export – Completed

PostgreSQL loading – Completed

SQL analytical queries – Started

---

# Phase 2 – FastAPI Backend

Planned:

- PostgreSQL connection
- Environment configuration
- SQLAlchemy
- FastAPI
- API routes
- CRUD operations
- Analytics endpoints
- Error handling

---

# Phase 3 – React Frontend

Planned:

- Dashboard
- Farm overview
- Pond overview
- Feed analytics
- Water-quality charts
- Growth charts
- Harvest analytics

---

# Phase 4 – Natural Language to SQL

Planned:

User question
→ LLM
→ SQL generation
→ SQL validation
→ PostgreSQL
→ Result
→ Natural-language response

---

# Phase 5 – Aquaculture RAG

Planned:

PDF/DOCX
→ Text extraction
→ Chunking
→ Embeddings
→ Chroma
→ Retrieval
→ Hugging Face LLM
→ Evidence-based answer

---

# Phase 6 – Confidence and Evidence Engine

Planned:

Answer
→ Evidence validation
→ Confidence calculation
→ Supporting records
→ Source information
→ Final response

---

# Phase 7 – AI Evaluation

Planned:

- NL-to-SQL accuracy
- SQL execution accuracy
- RAG retrieval accuracy
- Answer correctness
- Confidence calibration
- Hallucination testing
- Domain terminology evaluation

---

# Phase 8 – Final Integration

Planned:

React
→ FastAPI
→ PostgreSQL
→ NL-to-SQL
→ RAG
→ Hugging Face
→ Confidence engine

Final system will provide:

- dashboards
- natural-language data queries
- aquaculture knowledge Q&A
- evidence-backed answers
- confidence indicators
- charts and analytics