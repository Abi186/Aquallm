# AquaLLM

## Confidence-Aware Aquaculture Intelligence Platform

AquaLLM is an AI-powered aquaculture intelligence platform that combines structured farm data, aquaculture knowledge documents, natural-language querying, and evidence-based responses.

The system allows users to interact with farm data using natural language while also asking domain-specific aquaculture questions.

---

## Project Objectives

AquaLLM aims to:

- Store structured aquaculture data in PostgreSQL
- Provide farm and pond analytics
- Allow natural-language querying of farm data
- Retrieve information from aquaculture documents using RAG
- Use Hugging Face models for language understanding
- Provide evidence-backed answers
- Display confidence levels for generated responses
- Visualize important farm metrics through dashboards

---

## Core Features

### 1. Farm Data Management

The system stores:

- Farms
- Ponds
- Stocking
- Feed
- Water quality
- Growth
- Harvest
- Users

### 2. Natural Language to SQL

Users can ask questions such as:

> Which ponds have FCR above 1.8?

The system converts the question into SQL, executes it against PostgreSQL, and presents the result.

### 3. Aquaculture Knowledge Assistant

Users can ask questions such as:

> What is FCR?

> Why does low dissolved oxygen affect shrimp growth?

The system retrieves relevant information from the aquaculture knowledge base.

### 4. Confidence and Evidence

AquaLLM provides:

- Answer
- Confidence level
- Supporting records
- Retrieved documents
- SQL query when appropriate

### 5. Analytics Dashboard

The dashboard provides:

- Farm overview
- Pond performance
- FCR
- Biomass
- ADG
- Survival
- Water-quality trends
- Feed analytics

---

# Technology Stack

## Frontend

- React
- JavaScript
- Axios
- Charting library

## Backend

- Python
- FastAPI
- SQLAlchemy
- Pydantic

## Database

- PostgreSQL

## AI

- Hugging Face
- Sentence Transformers
- RAG
- Chroma
- Natural Language to SQL

## Development

- VS Code
- Google Colab
- pgAdmin
- Git / GitHub

---

# Architecture

```text
                    AquaLLM
                       |
                  React UI
                       |
                   FastAPI
                       |
          +------------+-------------+
          |                          |
      PostgreSQL                  AI Layer
          |                          |
    Farm Data                 +------+------+
                              |             |
                           NL-to-SQL       RAG
                              |             |
                              +------+------+
                                     |
                              Hugging Face