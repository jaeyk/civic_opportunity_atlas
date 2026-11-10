# MapAgora Community Tool

A static web tool, in development, that meets people where they are. It helps residents, organizers, universities, state and local governments, and foundations:

1. **Learn** how civic opportunity is structured in their county and ZIP code: what kinds of opportunity exist (membership, volunteering, public events, civic and political action), to what extent, and which kinds of organizations provide them.
2. **Compare** with similar places, through plain-language observations that state how confident the data lets us be.
3. **Start conversations**: printable profiles and discussion guides built from each place's own findings.

It is built on the MapAgora datasets from the [SNF Agora Institute](https://snfagora.jhu.edu/) at Johns Hopkins University.

> The earlier Quarto/R teaching dashboard and the Flask "Civic Quest" prototype are preserved on the `archive/quarto-dashboard` branch (tag `quarto-dashboard-final`).

## Repository layout

| Path | Contents |
|------|----------|
| `raw_data/` | County-level MapAgora data, county classifications (USDA RUCC), county/state boundaries |
| `raw_data/mapagora_full/` | Organization- and ZIP-level MapAgora data. Not in git; run `./get_full_data.sh` |
| `data/derived/` | Derived files from the prototype: county lookup, centroids, GeoJSON, Civic Quest JSON |
| `pipeline/` | Python data pipeline: opportunity × organization-type counts, smoothed rates, peer places, clusters |
| `data/processed/` | Pipeline output (parquet). Not in git; run `python -m pipeline.build` |
| `tests/` | Pipeline tests |
| `misc/` | Source paper: Kim, de Vries & Han (2025), *Scientific Data* |

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
./get_full_data.sh                      # org- and ZIP-level data (~55 MB)
.venv/bin/python -m pipeline.build      # writes data/processed/ (~1 min)
.venv/bin/python -m pytest tests
```

## Data

- **Full data:** [Harvard Dataverse, doi:10.7910/DVN/IRCA7C](https://doi.org/10.7910/DVN/IRCA7C) (CC0)
- **Data paper:** Kim, J.Y., de Vries, M., & Han, H. (2025). [MapAgora, civic opportunity datasets for the study of American local politics and public policy](https://www.nature.com/articles/s41597-025-05353-6). *Scientific Data* 12:1162.
- **Empirical paper:** de Vries, M., Kim, J.Y., & Han, H. (2024). [The unequal landscape of civic opportunity in America](https://doi.org/10.1038/s41562-023-01743-1). *Nature Human Behaviour* 8, 256–263.

Organization records are de-identified. There are no names, EINs or street addresses; the finest location is the ZIP code.

## Team

[Jae Yeon Kim](https://jaeyk.github.io/) & [Milan de Vries](https://snfagora.jhu.edu/person/milan-de-vries/)
