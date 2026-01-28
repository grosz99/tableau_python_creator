# Tableau Python Creator - Skills Documentation

This document provides comprehensive documentation for the Tableau workbook generation skills developed in this project. These can be used as reference for building future Tableau automation tools.

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Skill: DatasourceBuilder](#skill-datasourcebuilder)
4. [Skill: CalculatedField](#skill-calculatedfield)
5. [Skill: WorksheetBuilder](#skill-worksheetbuilder)
6. [Skill: DashboardBuilder](#skill-dashboardbuilder)
7. [Skill: TWBX Packaging](#skill-twbx-packaging)
8. [Common Patterns](#common-patterns)
9. [Troubleshooting](#troubleshooting)

---

## Overview

The Tableau Python Creator library generates Tableau Workbook (TWBX) files programmatically using Python. It produces valid Tableau XML that can be opened in Tableau Desktop.

### Key Capabilities
- Generate multi-worksheet dashboards
- Create calculated fields with Tableau formulas
- Configure geographic roles for mapping
- Support multiple visualization types (bar, scatter, map, KPI, sparkline)
- Package as TWBX with embedded Hyper data extracts

### Dependencies
```bash
pip install pandas pantab
```

---

## Architecture

### File Structure
```
tableau_python_creator/
├── builders/
│   ├── __init__.py
│   ├── datasource_builder.py   # DatasourceBuilder, CalculatedField
│   ├── worksheet_builder.py    # WorksheetBuilder, mark types
│   └── dashboard_builder.py    # DashboardBuilder, zone layouts
├── superstore_dashboard_generator.py  # Example usage
├── Sample - Superstore.csv
└── SKILLS_DOCUMENTATION.md
```

### TWB XML Structure
```xml
<?xml version='1.0' encoding='utf-8' ?>
<workbook version='18.1'>
  <preferences>...</preferences>
  <datasources>
    <datasource name='federated.xxx'>
      <connection class='hyper' dbname='Data/Extract.hyper'>
        <relation name='Extract' table='[public].[Extract]' />
      </connection>
      <column ... />  <!-- Regular columns -->
      <column ... />  <!-- Calculated fields -->
    </datasource>
  </datasources>
  <worksheets>
    <worksheet name='Sheet 1'>...</worksheet>
  </worksheets>
  <dashboards>
    <dashboard name='Dashboard 1'>...</dashboard>
  </dashboards>
  <windows>...</windows>
</workbook>
```

---

## Skill: DatasourceBuilder

**Purpose**: Creates the datasource XML section with column definitions, calculated fields, and geographic roles.

### Usage
```python
from builders import DatasourceBuilder, CalculatedField

# Create datasource with unique name
ds = DatasourceBuilder(
    name='federated.abc1234',           # Unique identifier
    hyper_path='Data/Extract.hyper',    # Path in TWBX
    caption='My Data'                   # Display name
)

# Add columns from DataFrame
ds.add_columns_from_df(df, geo_roles={'State': 'State'})

# Or add columns manually
ds.add_column('Sales', 'real', 'measure', 'quantitative')
ds.add_column('Category', 'string', 'dimension', 'nominal')

# Generate XML
xml = ds.to_xml()
```

### Key Parameters

| Parameter | Description | Values |
|-----------|-------------|--------|
| `datatype` | Tableau data type | `'string'`, `'real'`, `'integer'`, `'datetime'`, `'boolean'` |
| `role` | Field role | `'dimension'`, `'measure'` |
| `col_type` | Type classification | `'nominal'`, `'ordinal'`, `'quantitative'` |
| `geo_role` | Geographic role | `'State'`, `'Country'`, `'City'`, `'Postal Code'` |

### Geographic Role Mapping
```python
GEO_ROLE_MAP = {
    'State': '[State].[Name]',
    'Country': '[Country].[Name]',
    'City': '[City].[Name]',
    'Postal Code': '[ZipCode].[Name]',
}
```

---

## Skill: CalculatedField

**Purpose**: Defines Tableau calculated fields with formulas.

### Usage
```python
from builders import CalculatedField

# Simple ratio calculation
profit_ratio = CalculatedField(
    caption='Profit Ratio',              # Display name
    formula='SUM([Profit])/SUM([Sales])', # Tableau formula
    datatype='real',
    role='measure',
    col_type='quantitative',
    default_format='p0.0%'               # Percentage format
)

# Add to datasource
ds.add_calculated_field(profit_ratio)

# Reference in worksheets
calc_id = profit_ratio.clean_name  # e.g., 'Calculation_abc123'
```

### Common Formula Patterns
```python
# Aggregations
'SUM([Sales])'
'AVG([Profit])'
'COUNT([Order ID])'
'COUNTD([Customer ID])'

# Ratios
'SUM([Profit])/SUM([Sales])'

# Date functions
'YEAR([Order Date])'
'DATETRUNC("month", [Order Date])'

# Conditional
'IF [Profit] > 0 THEN "Profitable" ELSE "Loss" END'

# String
'SPLIT([Product Name], " ", 1)'
```

---

## Skill: WorksheetBuilder

**Purpose**: Creates individual worksheet visualizations with various mark types.

### Usage
```python
from builders import WorksheetBuilder, MarkType, Aggregation

ws = WorksheetBuilder('Sales by Category', 'federated.abc1234')
ws.set_mark_type(MarkType.BAR)
ws.add_row_field('Category', 'dimension')
ws.add_col_field('Sales', 'measure', Aggregation.SUM)
ws.add_color_encoding('Region', 'dimension')

# Add column dependencies (required for proper rendering)
ws.add_dependency_column('Category', 'string', 'dimension', 'nominal')
ws.add_dependency_column('Sales', 'real', 'measure', 'quantitative', aggregation='Sum')

xml = ws.to_xml()
```

### Mark Types
```python
class MarkType(Enum):
    AUTOMATIC = 'Automatic'  # Tableau chooses
    BAR = 'Bar'              # Bar charts
    LINE = 'Line'            # Line charts
    AREA = 'Area'            # Area charts (sparklines)
    CIRCLE = 'Circle'        # Scatter plots
    TEXT = 'Text'            # KPI cards
    MAP = 'Map'              # Geographic maps
```

### Aggregation Types
```python
class Aggregation(Enum):
    NONE = 'None'      # Dimensions
    SUM = 'Sum'        # Sum of values
    AVG = 'Avg'        # Average
    COUNT = 'Count'    # Count
    MIN = 'Min'        # Minimum
    MAX = 'Max'        # Maximum
```

### Field Instance Naming Convention
```
[derivation:FieldName:type_key]

- Dimensions: [none:Category:nk]     (nk = nominal key)
- Measures:   [sum:Sales:qk]         (qk = quantitative key)
- Calculated: [avg:Calculation_xxx:qk]
- Pre-aggregated: [usr:Calculation_xxx:qk]  (formula already has SUM/AVG)
```

### Pre-aggregated Calculated Fields
**CRITICAL**: For calculated fields whose formula already contains aggregation functions
(e.g., `SUM([Profit])/SUM([Sales])`), Tableau expects:
- `derivation='User'` (not 'Sum' or 'Avg')
- Instance name prefix `usr:` (not `sum:` or `avg:`)

This tells Tableau to evaluate the formula as-is without wrapping in additional aggregation.

```python
# Example: Profit Ratio = SUM([Profit])/SUM([Sales])
ws.add_col_field('Profit Ratio', 'measure', Aggregation.SUM,
                 is_calculated=True, calc_id=profit_ratio_calc_id,
                 is_preaggregated=True)  # <-- This flag is critical!
```

**Result in XML:**
```xml
<column-instance column='[Calculation_xxx]' derivation='User'
                 name='[usr:Calculation_xxx:qk]' pivot='key' type='quantitative' />
```

---

## Skill: DashboardBuilder

**Purpose**: Creates dashboard layouts with zone-based positioning.

### Usage
```python
from builders import DashboardBuilder

db = DashboardBuilder('My Dashboard', width=1400, height=900)

# Add root container
root_id = db.add_container_zone(0, 0, 100000, 100000)

# Add worksheets
db.add_worksheet_zone('Sheet 1', x=0, y=0, w=50000, h=50000, parent_id=root_id)
db.add_worksheet_zone('Sheet 2', x=50000, y=0, w=50000, h=50000, parent_id=root_id)

xml = db.to_xml()
```

### Coordinate System
- **Scale**: 0-100000 (100,000 units = 100% of available space)
- **Origin**: Top-left (0, 0)
- **X**: Increases to the right
- **Y**: Increases downward

### Layout Helper Functions
```python
from builders.dashboard_builder import (
    create_kpi_row_layout,         # Row of KPI cards
    create_two_column_layout,      # Side-by-side worksheets
    create_full_width_layout,      # Full-width worksheet
    create_superstore_dashboard_layout  # Complete Superstore layout
)
```

---

## Skill: TWBX Packaging

**Purpose**: Package TWB and Hyper extract into a TWBX file.

### Usage
```python
import pandas as pd
import pantab as pt
import zipfile
from pathlib import Path

def create_twbx(df, twb_xml, output_path):
    work_dir = Path('temp')
    work_dir.mkdir(exist_ok=True)

    # Create Hyper extract
    hyper_path = work_dir / 'Extract.hyper'
    pt.frame_to_hyper(df, str(hyper_path), table='Extract')

    # Write TWB
    twb_path = work_dir / 'workbook.twb'
    with open(twb_path, 'w', encoding='utf-8') as f:
        f.write(twb_xml)

    # Package as TWBX (ZIP)
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.write(twb_path, 'workbook.twb')
        zf.write(hyper_path, 'Data/Extract.hyper')

    # Cleanup
    os.remove(twb_path)
    os.remove(hyper_path)
```

### TWBX Structure
```
my_workbook.twbx (ZIP archive)
├── workbook.twb           # XML workbook definition
└── Data/
    └── Extract.hyper      # Hyper data extract
```

---

## Common Patterns

### Pattern 1: Bar Chart
```python
ws = WorksheetBuilder('Sales by Category', datasource_name)
ws.set_mark_type(MarkType.BAR)
ws.add_row_field('Category', 'dimension')
ws.add_col_field('Sales', 'measure', Aggregation.SUM)
```

### Pattern 2: Scatter Plot
```python
ws = WorksheetBuilder('Sales vs Profit', datasource_name)
ws.set_mark_type(MarkType.CIRCLE)
ws.add_col_field('Sales', 'measure', Aggregation.SUM)      # X-axis
ws.add_row_field('Profit', 'measure', Aggregation.SUM)     # Y-axis
ws.add_detail_encoding('Manufacturer', 'dimension')         # One point per
```

### Pattern 3: Choropleth Map
```python
ws = WorksheetBuilder('Profit by State', datasource_name)
ws.set_mark_type(MarkType.AUTOMATIC)
ws.add_row_field('Latitude (generated)', 'measure', Aggregation.AVG)
ws.add_col_field('Longitude (generated)', 'measure', Aggregation.AVG)
ws.add_detail_encoding('State', 'dimension')
ws.add_color_encoding('Profit', 'measure', Aggregation.SUM)
# Requires State column with semantic-role='[State].[Name]' in datasource
```

### Pattern 4: KPI Card (BAN - Big Ass Number)
```python
# CRITICAL: BAN should have NO row/col fields - only text encoding
# This creates a large centered number, not a bar chart
ws = WorksheetBuilder('Total Sales', datasource_name)
ws.set_mark_type(MarkType.TEXT)
# NO add_row_field - this would create an axis/bar chart
ws.add_label_encoding('Sales', 'measure', Aggregation.SUM)
ws.add_dependency_column('Sales', 'real', 'measure', 'quantitative', aggregation='Sum')
```

### Pattern 4b: KPI Card with Pre-aggregated Calculated Field
```python
# For calculated fields that already have aggregation in formula (e.g., SUM([Profit])/SUM([Sales]))
# Use is_preaggregated=True to generate 'User' derivation and 'usr:' prefix
ws = WorksheetBuilder('Profit Ratio KPI', datasource_name)
ws.set_mark_type(MarkType.TEXT)
ws.add_label_encoding('Profit Ratio', 'measure', Aggregation.SUM,
                      is_calculated=True, calc_id=profit_ratio_calc_id,
                      is_preaggregated=True)
ws.add_dependency_column(profit_ratio_calc_id, 'real', 'measure', 'quantitative',
                         caption='Profit Ratio', aggregation='Sum')
```

### Pattern 5: Sparkline
```python
ws = WorksheetBuilder('Sales Trend', datasource_name)
ws.set_mark_type(MarkType.AREA)
ws.add_row_field('Sales', 'measure', Aggregation.SUM)
ws.add_col_field('Order Date', 'dimension')
```

### Pattern 6: Grouped Bar Chart
```python
ws = WorksheetBuilder('Sales by Sub-Category', datasource_name)
ws.set_mark_type(MarkType.BAR)
ws.add_row_field('Category', 'dimension')
ws.add_row_field('Sub-Category', 'dimension')  # Nested dimension
ws.add_col_field('Sales', 'measure', Aggregation.SUM)
ws.add_color_encoding('Category', 'dimension')  # Color by parent
```

---

## Troubleshooting

### Issue: TWBX won't open in Tableau
- **Cause**: Invalid XML structure
- **Fix**: Ensure all XML special characters are escaped (`&`, `<`, `>`, `'`, `"`)

### Issue: Map not rendering
- **Cause**: Geographic role not set
- **Fix**: Add `semantic-role='[State].[Name]'` to State column in datasource

### Issue: Calculated field not working
- **Cause**: Formula syntax error or field references incorrect
- **Fix**: Field names in formulas must match column names exactly, wrapped in brackets

### Issue: Empty worksheet
- **Cause**: Missing `add_dependency_column()` calls
- **Fix**: Add dependency columns for all fields used in the worksheet

### Issue: Encoding errors when loading CSV
- **Fix**: Try multiple encodings: `['utf-8', 'latin-1', 'cp1252']`

---

## Quick Reference

### Datasource Name Format
```
federated.{7-char-uuid}
Example: federated.abc1234
```

### Column Instance Format
```
[derivation:FieldName:type_key]
Examples:
  [none:Category:nk]         # Dimension
  [sum:Sales:qk]            # Measure with Sum
  [avg:Calculation_xxx:qk]  # Calculated field with Avg
```

### Full Field Reference
```
[datasource_name].[column_instance]
Example: [federated.abc1234].[sum:Sales:qk]
```

### Dashboard Coordinates
```
Scale: 0-100000
Full width: w=100000
Half width: w=50000
Third width: w=33333
```

---

## Version History

- **v1.0** (2025-01): Initial release with bar, scatter, map, KPI, sparkline support
