# AquaLLM

## Confidence-Aware Aquaculture Intelligence Platform

AquaLLM is an AI-powered aquaculture intelligence platform that combines structured farm data, natural-language querying, and large language models to provide data-driven answers and insights.

The system allows users to interact with farm data using natural language and ask domain-specific aquaculture questions through an AI-powered assistant.

---

## Project Objectives

AquaLLM aims to:

- Store structured aquaculture data in PostgreSQL.
- Provide farm and pond analytics.
- Allow natural-language querying of farm data.
- Use Large Language Models (LLMs) to understand user questions and generate responses.
- Connect AI responses with structured farm data.
- Provide evidence-based answers using available database records.
- Display confidence levels for generated responses.
- Visualize important farm metrics through interactive dashboards.

---

## Core Features

### 1. Farm Data Management

The system stores and manages:

- Farms
- Ponds
- Stocking
- Feed
- Water quality
- Growth
- Harvest
- Users

### 2. Natural Language to SQL

Users can ask questions in simple English, such as:

> Which ponds have FCR above 1.8?

The system processes the question, generates an appropriate SQL query, executes it against PostgreSQL, and presents the results in a user-friendly format.

### 3. Aquaculture AI Assistant

Users can ask domain-specific questions such as:

> What is FCR?

> Why does low dissolved oxygen affect shrimp growth?

The system uses the Ollama-powered language model to understand questions and generate relevant aquaculture-related responses.

### 4. Confidence and Evidence

AquaLLM provides:

- AI-generated answers
- Confidence levels
- Supporting database records
- SQL query details when appropriate

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

### 6. Seven-Day Feed Prediction

The system uses machine learning to predict shrimp feed requirements for the next seven days, helping farmers plan feeding activities and manage feed efficiently.

---

# Technology Stack

## Frontend
- React
- JavaScript
- Axios
- Recharts

## Backend
- Python
- FastAPI
- SQLAlchemy
- Pydantic

## Database
- PostgreSQL

## AI and Machine Learning
- Ollama
- Qwen 2.5 7B
- Natural Language to SQL
- Random Forest
- XGBoost

## Development Tools
- VS Code
- Google Colab
- pgAdmin
- Git
- GitHub

---

## Project Goal

The main goal of AquaLLM is to simplify shrimp farm data management and make aquaculture information easier to access through natural-language interaction, AI-powered assistance, analytics, and machine learning-based feed prediction.
