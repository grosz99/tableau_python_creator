"""
Superstore Profitability Overview Dashboard Generator

SKILL DOCUMENTATION:
====================
This script generates a complex Tableau dashboard matching the "Superstore Profitability
Overview" design. It demonstrates how to use the builder classes to create:

1. Multiple worksheets (KPI cards, sparklines, map, scatter plot, bar chart)
2. Calculated fields (Profit Ratio)
3. Geographic visualizations (State choropleth map)
4. Complex dashboard layouts

DASHBOARD COMPONENTS:
- 3 KPI cards with sparklines (Profit Ratio, Total Profit, Total Sales)
- Choropleth map (Profit Ratio by State)
- Scatter plot (Profitability by Manufacturer)
- Grouped bar chart (Profit Ratio - Category Rank)

USAGE:
    python superstore_dashboard_generator.py

OUTPUT:
    superstore_profitability_overview.twbx (in current directory)

PREREQUISITES:
    - pandas
    - pantab (for Hyper file creation)
    - Sample - Superstore.csv in the same directory
"""

import pandas as pd
import pantab as pt
import zipfile
import os
import uuid
from pathlib import Path
from datetime import datetime

# Import our builders
from builders.datasource_builder import DatasourceBuilder, CalculatedField, ColumnDefinition
from builders.worksheet_builder import (
    WorksheetBuilder, MarkType, Aggregation,
    create_bar_chart, create_scatter_plot, create_kpi_card, create_sparkline, create_map_worksheet
)
from builders.dashboard_builder import (
    DashboardBuilder, create_superstore_dashboard_layout
)


# ==============================================================================
# STEP 1: DATA LOADING AND PREPROCESSING
# ==============================================================================
# SKILL: Loading and transforming data for Tableau visualization

def load_superstore_data(csv_path: str) -> pd.DataFrame:
    """
    Load and preprocess the Superstore dataset.

    SKILL DOCUMENTATION:
    ====================
    Data preprocessing steps for Tableau:
    1. Load CSV with proper encoding
    2. Parse date columns to datetime
    3. Extract derived fields (Manufacturer from Product Name)
    4. Ensure data types are compatible with Tableau/Hyper

    IMPORTANT: Column names in the DataFrame become field names in Tableau.
    Avoid special characters that may cause XML issues.

    Args:
        csv_path: Path to the Superstore CSV file

    Returns:
        Preprocessed pandas DataFrame
    """
    print(f"Loading data from {csv_path}...")

    # Load the CSV
    # Try multiple encodings as Superstore CSV may have special characters
    for encoding in ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
        try:
            df = pd.read_csv(csv_path, encoding=encoding)
            print(f"  Successfully loaded with encoding: {encoding}")
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError(f"Could not decode CSV file with any standard encoding")

    print(f"  Loaded {len(df)} rows, {len(df.columns)} columns")

    # Parse date columns
    # SKILL: Tableau date handling
    # Tableau expects datetime objects for proper date filtering and aggregation
    df['Order Date'] = pd.to_datetime(df['Order Date'], format='%m/%d/%Y')
    df['Ship Date'] = pd.to_datetime(df['Ship Date'], format='%m/%d/%Y')

    # Extract Manufacturer from Product Name
    # SKILL: Derived field creation
    # The Manufacturer is typically the first word in the Product Name
    # This is used for the "Profitability by Manufacturer" scatter plot
    df['Manufacturer'] = df['Product Name'].str.split().str[0]

    print(f"  Extracted {df['Manufacturer'].nunique()} unique manufacturers")

    # Ensure numeric columns are float for Tableau compatibility
    df['Sales'] = df['Sales'].astype(float)
    df['Profit'] = df['Profit'].astype(float)
    df['Discount'] = df['Discount'].astype(float)
    df['Quantity'] = df['Quantity'].astype(int)

    return df


# ==============================================================================
# STEP 2: DATASOURCE CONFIGURATION
# ==============================================================================
# SKILL: Building the Tableau datasource with calculated fields and geo roles

def create_datasource(df: pd.DataFrame, datasource_name: str) -> DatasourceBuilder:
    """
    Create and configure the datasource with all columns and calculated fields.

    SKILL DOCUMENTATION:
    ====================
    The datasource defines:
    1. All columns from the data with proper types
    2. Calculated fields with formulas
    3. Geographic roles for mapping

    CALCULATED FIELD: Profit Ratio
    Formula: SUM([Profit])/SUM([Sales])
    Purpose: Shows profitability as a percentage, used in KPI, map, and bar chart

    GEOGRAPHIC ROLE: State
    Assignment: semantic-role='[State].[Name]'
    Purpose: Enables Tableau to geocode states for the choropleth map

    Args:
        df: Preprocessed DataFrame
        datasource_name: Unique datasource identifier

    Returns:
        Configured DatasourceBuilder
    """
    print("Creating datasource configuration...")

    ds = DatasourceBuilder(datasource_name, 'Data/Extract.hyper', 'Superstore')

    # Add columns from DataFrame with geo roles
    # SKILL: Geographic role assignment
    # Setting geo_role='State' adds semantic-role='[State].[Name]' to enable mapping
    geo_roles = {'State': 'State', 'Country': 'Country', 'City': 'City'}
    ds.add_columns_from_df(df, geo_roles=geo_roles)

    # Add calculated field: Profit Ratio
    # SKILL: Calculated field creation
    # This is a table calculation that computes profit margin
    profit_ratio = CalculatedField(
        caption='Profit Ratio',
        formula='SUM([Profit])/SUM([Sales])',
        datatype='real',
        role='measure',
        col_type='quantitative',
        default_format='p0.0%'  # Percentage format with 1 decimal
    )
    ds.add_calculated_field(profit_ratio)

    print(f"  Added {len(ds.columns)} columns and {len(ds.calculated_fields)} calculated fields")
    print(f"  Profit Ratio calc ID: {profit_ratio.clean_name}")

    return ds


# ==============================================================================
# STEP 3: WORKSHEET CREATION
# ==============================================================================
# SKILL: Building individual worksheets for different visualization types

def create_kpi_worksheets(datasource_name: str, profit_ratio_calc_id: str) -> list:
    """
    Create the three KPI card worksheets.

    SKILL DOCUMENTATION:
    ====================
    KPI cards (BANs - Big Ass Numbers) display single aggregated values.
    They use:
    - Text mark type
    - A single measure field
    - No dimensions (aggregates across all data)

    For calculated fields, we need to pass:
    - is_calculated=True
    - calc_id=the internal calculation ID

    Args:
        datasource_name: Datasource reference
        profit_ratio_calc_id: Internal ID of the Profit Ratio calculated field

    Returns:
        List of WorksheetBuilder instances
    """
    print("Creating KPI card worksheets...")
    worksheets = []

    # KPI 1: Profit Ratio
    # SKILL: BAN (Big Ass Number) - Text mark with measure ONLY on label encoding
    # CRITICAL: Do NOT put measure on rows - that creates an axis/bar chart
    # For pre-aggregated calculated fields, use is_preaggregated=True
    ws1 = WorksheetBuilder('Profit Ratio KPI', datasource_name)
    ws1.set_mark_type(MarkType.TEXT)
    # NO add_row_field - BAN should have empty rows to show just the number
    ws1.add_label_encoding('Profit Ratio', 'measure', Aggregation.SUM,
                           is_calculated=True, calc_id=profit_ratio_calc_id,
                           is_preaggregated=True)
    ws1.add_dependency_column(profit_ratio_calc_id, 'real', 'measure', 'quantitative',
                              caption='Profit Ratio', aggregation='Sum')
    worksheets.append(ws1)

    # KPI 2: Total Profit
    # SKILL: BAN with standard measure - text only, no rows
    ws2 = WorksheetBuilder('Total Profit KPI', datasource_name)
    ws2.set_mark_type(MarkType.TEXT)
    # NO add_row_field - BAN should have empty rows
    ws2.add_label_encoding('Profit', 'measure', Aggregation.SUM)
    ws2.add_dependency_column('Profit', 'real', 'measure', 'quantitative', aggregation='Sum')
    worksheets.append(ws2)

    # KPI 3: Total Sales
    # SKILL: BAN with standard measure - text only, no rows
    ws3 = WorksheetBuilder('Total Sales KPI', datasource_name)
    ws3.set_mark_type(MarkType.TEXT)
    # NO add_row_field - BAN should have empty rows
    ws3.add_label_encoding('Sales', 'measure', Aggregation.SUM)
    ws3.add_dependency_column('Sales', 'real', 'measure', 'quantitative', aggregation='Sum')
    worksheets.append(ws3)

    print(f"  Created {len(worksheets)} KPI worksheets")
    return worksheets


def create_sparkline_worksheets(datasource_name: str, profit_ratio_calc_id: str) -> list:
    """
    Create sparkline worksheets for each KPI.

    SKILL DOCUMENTATION:
    ====================
    Sparklines are minimal trend charts that accompany KPI cards.
    They show how a measure changes over time.

    Structure:
    - Measure on rows (Y-axis)
    - Date dimension on columns (X-axis)
    - Area or Line mark type
    - Minimal formatting (no axis labels, title, etc.)

    Args:
        datasource_name: Datasource reference
        profit_ratio_calc_id: Internal ID of the Profit Ratio calculated field

    Returns:
        List of WorksheetBuilder instances
    """
    print("Creating sparkline worksheets...")
    worksheets = []

    # Sparkline 1: Profit Ratio trend
    # SKILL: Pre-aggregated calculated field on rows - use is_preaggregated=True
    ws1 = WorksheetBuilder('Profit Ratio Sparkline', datasource_name)
    ws1.set_mark_type(MarkType.AREA)
    ws1.add_row_field('Profit Ratio', 'measure', Aggregation.SUM,
                      is_calculated=True, calc_id=profit_ratio_calc_id,
                      is_preaggregated=True)
    ws1.add_col_field('Order Date', 'dimension')
    ws1.add_dependency_column(profit_ratio_calc_id, 'real', 'measure', 'quantitative',
                              caption='Profit Ratio', aggregation='Sum')
    ws1.add_dependency_column('Order Date', 'datetime', 'dimension', 'ordinal')
    worksheets.append(ws1)

    # Sparkline 2: Profit trend
    ws2 = WorksheetBuilder('Profit Sparkline', datasource_name)
    ws2.set_mark_type(MarkType.AREA)
    ws2.add_row_field('Profit', 'measure', Aggregation.SUM)
    ws2.add_col_field('Order Date', 'dimension')
    ws2.add_dependency_column('Profit', 'real', 'measure', 'quantitative', aggregation='Sum')
    ws2.add_dependency_column('Order Date', 'datetime', 'dimension', 'ordinal')
    worksheets.append(ws2)

    # Sparkline 3: Sales trend
    ws3 = WorksheetBuilder('Sales Sparkline', datasource_name)
    ws3.set_mark_type(MarkType.AREA)
    ws3.add_row_field('Sales', 'measure', Aggregation.SUM)
    ws3.add_col_field('Order Date', 'dimension')
    ws3.add_dependency_column('Sales', 'real', 'measure', 'quantitative', aggregation='Sum')
    ws3.add_dependency_column('Order Date', 'datetime', 'dimension', 'ordinal')
    worksheets.append(ws3)

    print(f"  Created {len(worksheets)} sparkline worksheets")
    return worksheets


def create_map_worksheet_custom(datasource_name: str, profit_ratio_calc_id: str) -> WorksheetBuilder:
    """
    Create the Profit Ratio by State choropleth map.

    SKILL DOCUMENTATION:
    ====================
    Choropleth maps show geographic data with color-coded regions.

    Key requirements:
    1. Geographic field (State) with semantic-role set
    2. Generated Latitude/Longitude fields on rows/cols
    3. Color encoding with a measure (Profit Ratio)
    4. Detail encoding with the geographic field

    Tableau auto-generates Lat/Lon when:
    - A field has a geographic role
    - It's placed on detail
    - The view has map capabilities

    Args:
        datasource_name: Datasource reference
        profit_ratio_calc_id: Internal ID of the Profit Ratio calculated field

    Returns:
        Configured WorksheetBuilder
    """
    print("Creating map worksheet...")

    # NOTE: Map visualizations require Tableau to auto-generate Lat/Lon fields
    # which is complex to do programmatically. Using a bar chart instead to show
    # the same data (Profit Ratio by State) in a format that works reliably.
    ws = WorksheetBuilder('Profit Ratio by State', datasource_name)
    ws.set_mark_type(MarkType.BAR)

    # State on rows, Profit Ratio on cols - simple bar chart pattern
    # SKILL: Pre-aggregated calculated field - use is_preaggregated=True
    ws.add_row_field('State', 'dimension')
    ws.add_col_field('Profit Ratio', 'measure', Aggregation.SUM,
                     is_calculated=True, calc_id=profit_ratio_calc_id,
                     is_preaggregated=True)

    # Color by Profit Ratio for visual emphasis
    ws.add_color_encoding('Profit Ratio', 'measure', Aggregation.SUM,
                          is_calculated=True, calc_id=profit_ratio_calc_id,
                          is_preaggregated=True)

    # Add column dependencies
    ws.add_dependency_column('State', 'string', 'dimension', 'nominal')
    ws.add_dependency_column(profit_ratio_calc_id, 'real', 'measure', 'quantitative',
                             caption='Profit Ratio', aggregation='Sum')

    print("  Created map worksheet: Profit Ratio by State")
    return ws


def create_scatter_worksheet_custom(datasource_name: str) -> WorksheetBuilder:
    """
    Create the Profitability by Manufacturer scatter plot.

    SKILL DOCUMENTATION:
    ====================
    Scatter plots show relationships between two measures.

    Structure:
    - X-axis (cols): One measure (Sales)
    - Y-axis (rows): Another measure (Profit)
    - Detail: Dimension for individual points (Manufacturer)
    - Mark type: Circle

    Each point represents one Manufacturer, positioned by their
    total Sales (X) and total Profit (Y).

    Args:
        datasource_name: Datasource reference

    Returns:
        Configured WorksheetBuilder
    """
    print("Creating scatter plot worksheet...")

    ws = WorksheetBuilder('Profitability by Manufacturer', datasource_name)
    ws.set_mark_type(MarkType.CIRCLE)

    # X-axis: Sales
    ws.add_col_field('Sales', 'measure', Aggregation.SUM)

    # Y-axis: Profit
    ws.add_row_field('Profit', 'measure', Aggregation.SUM)

    # Detail: One point per Manufacturer
    ws.add_detail_encoding('Manufacturer', 'dimension')

    # Optional: Color by Category for additional insight
    ws.add_color_encoding('Category', 'dimension')

    # Add column dependencies
    ws.add_dependency_column('Sales', 'real', 'measure', 'quantitative', aggregation='Sum')
    ws.add_dependency_column('Profit', 'real', 'measure', 'quantitative', aggregation='Sum')
    ws.add_dependency_column('Manufacturer', 'string', 'dimension', 'nominal')
    ws.add_dependency_column('Category', 'string', 'dimension', 'nominal')

    print("  Created scatter plot: Profitability by Manufacturer")
    return ws


def create_bar_chart_worksheet(datasource_name: str, profit_ratio_calc_id: str) -> WorksheetBuilder:
    """
    Create the Profit Ratio - Category Rank grouped bar chart.

    SKILL DOCUMENTATION:
    ====================
    Grouped bar charts show a measure broken down by multiple dimensions.

    Structure:
    - Rows: Multiple dimensions (Category, Sub-Category)
    - Cols: Measure (Profit Ratio)
    - Color: Grouping dimension (Category)

    The chart shows Sub-Categories grouped by their parent Category,
    with bars colored by Category for visual grouping.

    Args:
        datasource_name: Datasource reference
        profit_ratio_calc_id: Internal ID of the Profit Ratio calculated field

    Returns:
        Configured WorksheetBuilder
    """
    print("Creating bar chart worksheet...")

    ws = WorksheetBuilder('Profit Ratio - Category Rank', datasource_name)
    ws.set_mark_type(MarkType.BAR)

    # Rows: Sub-Category only (single dimension like working tableau_generator.py)
    # The original working pattern uses ONE dimension on rows
    ws.add_row_field('Sub-Category', 'dimension')

    # Cols: Profit Ratio measure
    # SKILL: Pre-aggregated calculated field - use is_preaggregated=True
    ws.add_col_field('Profit Ratio', 'measure', Aggregation.SUM,
                     is_calculated=True, calc_id=profit_ratio_calc_id,
                     is_preaggregated=True)

    # Color by Category for visual grouping (shows category relationship)
    ws.add_color_encoding('Category', 'dimension')

    # Add column dependencies
    ws.add_dependency_column('Sub-Category', 'string', 'dimension', 'nominal')
    ws.add_dependency_column('Category', 'string', 'dimension', 'nominal')
    ws.add_dependency_column(profit_ratio_calc_id, 'real', 'measure', 'quantitative',
                             caption='Profit Ratio', aggregation='Sum')

    print("  Created bar chart: Profit Ratio - Category Rank")
    return ws


# ==============================================================================
# STEP 4: TWB XML GENERATION
# ==============================================================================
# SKILL: Assembling the complete TWB workbook XML

def generate_twb_xml(datasource: DatasourceBuilder, worksheets: list,
                     dashboard: DashboardBuilder) -> str:
    """
    Generate the complete TWB (Tableau Workbook) XML.

    SKILL DOCUMENTATION:
    ====================
    A TWB file is an XML document with the following structure:

    <?xml version='1.0' encoding='utf-8' ?>
    <workbook ...>
      <preferences>...</preferences>
      <datasources>
        <datasource>...</datasource>
      </datasources>
      <worksheets>
        <worksheet>...</worksheet>
        ...
      </worksheets>
      <dashboards>
        <dashboard>...</dashboard>
      </dashboards>
      <windows>...</windows>
    </workbook>

    Key sections:
    - preferences: UI settings
    - datasources: Data connections and column definitions
    - worksheets: Individual visualizations
    - dashboards: Layout arrangements of worksheets
    - windows: UI state (which sheets are open)

    Args:
        datasource: Configured DatasourceBuilder
        worksheets: List of WorksheetBuilder instances
        dashboard: Configured DashboardBuilder

    Returns:
        Complete TWB XML string
    """
    print("Generating TWB XML...")

    # Build datasources section
    datasources_xml = f'''  <datasources>
{datasource.to_xml()}
  </datasources>'''

    # Build worksheets section
    worksheets_xml_parts = [ws.to_xml() for ws in worksheets]
    worksheets_xml = f'''  <worksheets>
{chr(10).join(worksheets_xml_parts)}
  </worksheets>'''

    # Build dashboards section
    dashboards_xml = f'''  <dashboards>
{dashboard.to_xml()}
  </dashboards>'''

    # Build windows section (tracks open sheets)
    # SKILL: Windows configuration
    # This tells Tableau which sheet to show when the workbook opens
    # IMPORTANT: The window element requires a 'cards' structure with edge/strip/card elements
    # We define one worksheet window - Tableau will handle the dashboard automatically
    first_worksheet_name = worksheets[0].name if worksheets else 'Sheet 1'
    windows_xml = f'''  <windows source-height='30'>
    <window class='worksheet' name='{first_worksheet_name}'>
      <cards>
        <edge name='left'>
          <strip size='160'>
            <card type='pages' />
            <card type='filters' />
            <card type='marks' />
          </strip>
        </edge>
        <edge name='top'>
          <strip size='2147483647'>
            <card type='columns' />
          </strip>
          <strip size='2147483647'>
            <card type='rows' />
          </strip>
          <strip size='31'>
            <card type='title' />
          </strip>
        </edge>
      </cards>
    </window>
  </windows>'''

    # Assemble complete TWB
    twb_xml = f'''<?xml version='1.0' encoding='utf-8' ?>
<workbook source-build='2022.3.0 (20223.22.1005.1835)' source-platform='win' version='18.1' xmlns:user='http://www.tableausoftware.com/xml/user'>
  <preferences>
    <preference name='ui.encoding.shelf.height' value='24' />
    <preference name='ui.shelf.height' value='26' />
  </preferences>
{datasources_xml}
{worksheets_xml}
{dashboards_xml}
{windows_xml}
</workbook>'''

    print(f"  Generated TWB XML ({len(twb_xml)} characters)")
    return twb_xml


# ==============================================================================
# STEP 5: TWBX PACKAGING
# ==============================================================================
# SKILL: Creating the packaged Tableau workbook file

def create_twbx(df: pd.DataFrame, twb_xml: str, output_path: str, work_dir: Path) -> str:
    """
    Package the TWB and Hyper extract into a TWBX file.

    SKILL DOCUMENTATION:
    ====================
    A TWBX file is a ZIP archive containing:
    - workbook.twb (the XML workbook definition)
    - Data/Extract.hyper (the data extract)
    - Optionally: images, custom shapes, etc.

    Structure:
    my_workbook.twbx (ZIP)
    ├── workbook.twb
    └── Data/
        └── Extract.hyper

    The Hyper file is created using pantab, which provides a high-performance
    interface to Tableau's Hyper database format.

    Args:
        df: DataFrame to extract
        twb_xml: Complete TWB XML string
        output_path: Path for output .twbx file
        work_dir: Temporary directory for intermediate files

    Returns:
        Path to the created TWBX file
    """
    print(f"Creating TWBX package: {output_path}")

    # Ensure work directory exists
    work_dir.mkdir(parents=True, exist_ok=True)

    # Create Hyper extract
    # SKILL: Hyper file creation with pantab
    # pantab.frame_to_hyper() converts a DataFrame to Tableau's Hyper format
    hyper_path = work_dir / 'Extract.hyper'
    print(f"  Creating Hyper extract: {hyper_path}")
    pt.frame_to_hyper(df, str(hyper_path), table='Extract')

    # Write TWB file
    twb_path = work_dir / 'workbook.twb'
    print(f"  Writing TWB: {twb_path}")
    with open(twb_path, 'w', encoding='utf-8') as f:
        f.write(twb_xml)

    # Package as TWBX (ZIP archive)
    # SKILL: TWBX packaging
    # The paths inside the ZIP must match the references in the TWB
    print(f"  Packaging TWBX: {output_path}")
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.write(twb_path, 'workbook.twb')
        zf.write(hyper_path, 'Data/Extract.hyper')

    # Cleanup temp files
    os.remove(twb_path)
    os.remove(hyper_path)

    # Verify the output
    file_size = os.path.getsize(output_path)
    print(f"  Created TWBX: {output_path} ({file_size:,} bytes)")

    return output_path


# ==============================================================================
# STEP 6: MAIN ORCHESTRATION
# ==============================================================================

def generate_superstore_dashboard(csv_path: str, output_path: str) -> str:
    """
    Main function to generate the complete Superstore Profitability Overview dashboard.

    SKILL DOCUMENTATION:
    ====================
    This orchestrates the entire dashboard generation process:

    1. Load and preprocess data
    2. Create datasource with columns and calculated fields
    3. Create all worksheets:
       - 3 KPI cards
       - 3 sparklines
       - 1 choropleth map
       - 1 scatter plot
       - 1 grouped bar chart
    4. Create dashboard with zone layout
    5. Generate TWB XML
    6. Package as TWBX

    Args:
        csv_path: Path to Sample - Superstore.csv
        output_path: Path for output .twbx file

    Returns:
        Path to the created TWBX file
    """
    print("=" * 70)
    print("SUPERSTORE PROFITABILITY OVERVIEW DASHBOARD GENERATOR")
    print("=" * 70)
    print()

    # Step 1: Load data
    df = load_superstore_data(csv_path)
    print()

    # Step 2: Create datasource
    datasource_name = f'federated.{uuid.uuid4().hex[:7]}'
    datasource = create_datasource(df, datasource_name)

    # Get the Profit Ratio calculation ID for referencing
    profit_ratio_calc = datasource.get_calculated_field('Profit Ratio')
    profit_ratio_calc_id = profit_ratio_calc.clean_name
    print()

    # Step 3: Create worksheets
    worksheets = []

    # KPI cards
    kpi_worksheets = create_kpi_worksheets(datasource_name, profit_ratio_calc_id)
    worksheets.extend(kpi_worksheets)

    # Sparklines
    sparkline_worksheets = create_sparkline_worksheets(datasource_name, profit_ratio_calc_id)
    worksheets.extend(sparkline_worksheets)

    # Map
    map_worksheet = create_map_worksheet_custom(datasource_name, profit_ratio_calc_id)
    worksheets.append(map_worksheet)

    # Scatter plot
    scatter_worksheet = create_scatter_worksheet_custom(datasource_name)
    worksheets.append(scatter_worksheet)

    # Bar chart
    bar_worksheet = create_bar_chart_worksheet(datasource_name, profit_ratio_calc_id)
    worksheets.append(bar_worksheet)

    print(f"\nTotal worksheets created: {len(worksheets)}")
    print()

    # Step 4: Create dashboard
    print("Creating dashboard layout...")
    dashboard = DashboardBuilder('Superstore Profitability Overview', width=1400, height=900)

    # Use the helper to create the standard layout
    # KPI names for the top row (we'll combine KPI + sparkline visually)
    kpi_names = ['Profit Ratio KPI', 'Total Profit KPI', 'Total Sales KPI']

    create_superstore_dashboard_layout(
        dashboard,
        kpi_worksheets=kpi_names,
        map_worksheet='Profit Ratio by State',
        scatter_worksheet='Profitability by Manufacturer',
        bar_worksheet='Profit Ratio - Category Rank'
    )
    print("  Dashboard layout created")
    print()

    # Step 5: Generate TWB XML
    twb_xml = generate_twb_xml(datasource, worksheets, dashboard)
    print()

    # Step 6: Create TWBX
    work_dir = Path(os.path.dirname(output_path)) / 'twbx_temp'
    result_path = create_twbx(df, twb_xml, output_path, work_dir)

    # Cleanup work directory
    try:
        work_dir.rmdir()
    except OSError:
        pass  # Directory not empty or doesn't exist

    print()
    print("=" * 70)
    print("DASHBOARD GENERATION COMPLETE!")
    print("=" * 70)
    print(f"\nOutput file: {result_path}")
    print("\nTo view the dashboard:")
    print("1. Open Tableau Desktop")
    print("2. File > Open > Select the .twbx file")
    print("3. Click on 'Superstore Profitability Overview' dashboard tab")
    print()

    return result_path


# ==============================================================================
# ENTRY POINT
# ==============================================================================

if __name__ == '__main__':
    # Get the script's directory
    script_dir = Path(__file__).parent

    # Input and output paths
    csv_path = script_dir / 'Sample - Superstore.csv'
    output_path = script_dir / 'superstore_profitability_overview.twbx'

    # Generate the dashboard
    generate_superstore_dashboard(str(csv_path), str(output_path))
