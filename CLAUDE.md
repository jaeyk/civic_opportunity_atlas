# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MapAgora Teaching Dashboard - An interactive Quarto website for learning about and exploring civic opportunity data across U.S. counties. Built with R, Leaflet.js, DataTables, and Plotly. Part of the "Mapping the Modern Agora" research project at Johns Hopkins University's SNF Agora Institute.

Live site: https://snfagora.github.io/agora_dashboard/

## Build and Development Commands

```bash
# Render the Quarto project (outputs to _site/)
quarto render

# Deploy to GitHub Pages (renders, copies to docs/, commits, pushes)
bash deploy_dashboard.sh

# Preview locally during development
quarto preview
```

Automated deployment runs via GitHub Actions on push to main.

## R Package Dependencies

The project uses `pacman` for package management. Key packages:
- **Visualization**: leaflet, leaflet.extras, DT, viridis, RColorBrewer, plotly
- **Data wrangling**: tidyverse, glue, scales, jsonlite
- **Geospatial**: sf, tigris
- **Utilities**: here, htmlwidgets, htmltools

System dependencies (for sf/geospatial): libgdal, libgeos, libproj, libudunits2

## Architecture

**Data flow**: CSV files in `raw_data/` → R processing in `.qmd` files → Quarto renders to HTML in `_site/` → copied to `docs/` for GitHub Pages

**Page Structure** (navigation order):
- `index.qmd`: Home page with project overview
- `learn.qmd`: Comprehensive methodology explanation (data sources, collection, limitations)
- `where_to_start.qmd`: Learning objectives and guided exploration steps
- `map.qmd`: Interactive Leaflet map with annotation and comparison features
- `table.qmd`: Interactive DataTables with bookmark functionality
- `compare.qmd`: Dedicated comparison page for states and counties
- `about.qmd`: Credits and contact

**Key data files**:
- `raw_data/cnty_counts_cov.csv`: County-level civic indicators
- `raw_data/cnty_civic_org_type.csv`: Organization type frequencies
- `raw_data/counties.rds`: County shapefiles for mapping
- `misc/Kim_et_al-2025-Scientific_Data.pdf`: Source paper for methodology

## Teaching Tool Features

**Map Features** (`map.qmd`):
- County click → sidebar display with civic metrics and demographic bars
- Annotation panel: Users can add notes per county (saved to localStorage)
- Comparison mode: Toggle to select up to 3 counties for side-by-side comparison
- Layer switching: "Civic Opportunity Counts" vs "Primary Organization Type"
- Search: Find counties by name

**Table Features** (`table.qmd`):
- Bookmark counties with star icons (saved to localStorage)
- Filter to show only bookmarked counties
- Export visible data as CSV
- Column visibility toggle

**Compare Page** (`compare.qmd`):
- State-level comparison table with bar chart visualization
- County comparison tool with state filter
- Quick compare: Select two counties for side-by-side metric cards
- Uses Plotly for interactive charts

## JavaScript State Management

Both map and table use localStorage for persistence:
- `mapAnnotations`: County notes `{fips: {note, timestamp}}`
- `mapComparisonState`: Comparison mode state `{enabled, counties: []}`
- `tableBookmarks`: Array of bookmarked FIPS codes

## Key Patterns

**Map interaction**: `htmlwidgets::onRender()` injects JavaScript that intercepts Leaflet popup clicks and redirects content to a sidebar div. The `layerId` parameter on `addPolygons()` provides the FIPS code for each county.

**Table callbacks**: DataTables `drawCallback` reinitializes bookmark buttons after each table redraw (pagination, filtering).

**Responsive design**: CSS flexbox layouts with media queries at 768px breakpoint for mobile.
