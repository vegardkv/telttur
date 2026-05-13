# Instructions

## Overview

**Telttur** is a project under active development. The end goal is to create an interactive map where users can find suggestions for tenting/camping trips in Norway, scored by suitability factors like lake proximity, land cover, accessibility, and cabin density.

## Current Goal

Build a **static map** that does not rely on a back-end server. All relevant data is pre-processed and baked into the output. The generated map will be published via GitHub Pages (or similar static hosting).

## Architecture & Tools

- **Folium** and **GeoPandas** are the main workhorses for map generation. They should suffice until proven too limiting.
- **Pydantic** drives a rigorous configuration system with sensible defaults.
- The CLI entry point is `telttur` (via Click).

## Configuration

- `config.yaml` should always contain the **bare minimum** of inputs and reflect what the default setup does. Do not bloat it with redundant or optional fields.
- `config_akershus.yaml` is an intermediate scaling test to verify the pipeline works for a larger area.
- `config_innlandet.yaml` is another regional config for testing.
- Long-term plan: generate a map for the entire country.

## Development Workflow

- **Package management:** `uv`
- **Linting & formatting:** `ruff`
- **Type checking:** `ty`

### Tasks

Numbered task files live under `tasks/`. These are incremental steps toward the end goal, typically sent to an agent for implementation.

After completing a task, the implementer should **step back and review** that the overall design and architecture remain sound — that the new feature fits well within the existing framework. If it doesn't, suggest future improvements (but let the developer decide whether to implement them immediately or defer).

## Design Principles

- **Minimal interface** — expose only what's necessary.
- **DRY** — don't repeat yourself.
- **KISS** — keep it simple; avoid over-engineering.
