<div align="center">
  <img src="https://fiatools.org/logos/askfia_logo.png" alt="askFIA" width="140">

  <h1>askFIA</h1>

  <p><strong>Ask questions, get forest answers</strong></p>

  <p>
    <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-006D6D" alt="License: MIT"></a>
    <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.9+-006D6D" alt="Python 3.9+"></a>
  </p>

  <p>
    <sub>Part of the <a href="https://fiatools.org"><strong>FIAtools</strong></a> ecosystem:
    <a href="https://github.com/mihiarc/pyfia">pyFIA</a> ·
    <a href="https://github.com/mihiarc/gridfia">gridFIA</a> ·
    <a href="https://github.com/mihiarc/pyfvs">pyFVS</a> ·
    <a href="https://github.com/mihiarc/askfia">askFIA</a></sub>
  </p>
</div>

---

A conversational AI interface for forest inventory data. Ask natural language questions and get answers powered by the FIAtools ecosystem.

## What can you ask?

```
"How much timber volume is in North Carolina?"

"Compare loblolly pine biomass between Georgia and Alabama"

"What's the species diversity in Humboldt County, California?"

"Project growth for a 500 TPA loblolly stand over 30 years"

"Show me mortality trends in the Pacific Northwest"
```

## Quick Start

```bash
pip install askfia
```

```python
from askfia import AskFIA

fia = AskFIA()

# Natural language queries
answer = fia.ask("What's the total forest area in Oregon?")
print(answer)

# With context
answer = fia.ask(
    "How does this compare to Washington?",
    context=answer  # Continues the conversation
)
```

## Features

| Capability | Description |
|------------|-------------|
| **Natural language** | Ask questions in plain English |
| **Multi-tool** | Automatically routes to pyFIA, gridFIA, or pyFVS |
| **Conversational** | Follow-up questions with context |
| **Visualizations** | Generates charts and maps |
| **Reports** | Export analysis to markdown/PDF |

## Example Session

```python
>>> fia.ask("What are the top 5 species by biomass in North Carolina?")

Based on FIA data for North Carolina:

| Rank | Species | Biomass (tons) |
|------|---------|----------------|
| 1 | Loblolly Pine | 245,892,000 |
| 2 | Yellow-poplar | 89,234,000 |
| 3 | Red Maple | 67,891,000 |
| 4 | Sweetgum | 54,123,000 |
| 5 | White Oak | 48,567,000 |

>>> fia.ask("Show me where loblolly is most concentrated")

[Generates choropleth map using gridFIA data]

>>> fia.ask("What would a 30-year projection look like for a typical loblolly stand?")

[Runs pyFVS simulation and returns yield table]
```

## Architecture

```
┌─────────────┐
│   askFIA    │  Natural language interface
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Router    │  Determines which tool(s) to use
└──────┬──────┘
       │
       ├──────────────┬──────────────┐
       ▼              ▼              ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│   pyFIA     │ │  gridFIA    │ │   pyFVS     │
│  (surveys)  │ │  (spatial)  │ │  (growth)   │
└─────────────┘ └─────────────┘ └─────────────┘
```

## Configuration

```python
from askfia import AskFIA

fia = AskFIA(
    database="path/to/FIA_database.duckdb",
    zarr_cache="path/to/gridfia_cache",
    model="gpt-4",  # or claude-3, local llama, etc.
    verbose=True
)
```

## CLI Usage

```bash
# Interactive mode
askfia chat

# Single query
askfia query "Forest area in Maine"

# Generate report
askfia report "Pacific Northwest timber summary" --output report.pdf
```

## Ecosystem Integration

askFIA orchestrates the entire FIAtools suite:

```python
# This single query:
fia.ask("Compare forest carbon between 2010 and 2020 in the Southeast")

# Automatically:
# 1. Uses pyFIA to query biomass estimates for both time periods
# 2. Calculates carbon from biomass using standard conversion factors
# 3. Computes change statistics with proper variance estimation
# 4. Formats results with appropriate uncertainty bounds
```

## Coming Soon

- [ ] Voice interface
- [ ] Slack/Discord integration
- [ ] Scheduled reports
- [ ] Custom analysis templates
- [ ] Multi-state comparisons

## Citation

```bibtex
@software{askfia2025,
  title = {askFIA: Conversational AI Interface for Forest Inventory Data},
  author = {Mihiar, Christopher},
  year = {2025},
  url = {https://github.com/mihiarc/askfia}
}
```

## License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">
  <sub>Built with 🌲 by <a href="https://github.com/mihiarc">Chris Mihiar</a> · USDA Forest Service Southern Research Station</sub>
</div>
