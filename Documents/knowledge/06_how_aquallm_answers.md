# How AquaLLM Answers Questions

This document explains the difference between actual data, predictions and general guidelines in AquaLLM.

## Actual data

Actual values come from the farm PostgreSQL database: stocking, feed, water quality, growth sampling and harvest records of each pond. When a question is about a specific pond, such as the latest ABW or DO of a pond code like F01-P03, the answer uses the value stored in the database. If the record does not exist, AquaLLM says the record was not found. It does not guess.

## Predictions

Predictions are estimates made by a model, for example the recommended feed quantity for the coming days. They are not recorded facts. Prediction results are always estimates and depend on the quality and recency of the data used.

## General guidelines

General guideline values (for example, a preferred DO level or a typical FCR range) come from this knowledge base. They describe typical good practice for shrimp farming and are not the values of any pond. When both exist, AquaLLM keeps them separate: actual value from the database, and the general guideline from the knowledge base.

## Pond codes

Ponds are identified by a code such as F01-P03, where F01 is the farm and P03 is the pond number in that farm. A short code like P03 may match ponds in several farms, so the complete pond code is required.

## Units

ABW and ADG are in grams (g and g/day). Biomass and feed are in kilograms (kg). DO, ammonia and similar water values are in mg/L. Temperature is in degrees Celsius.
