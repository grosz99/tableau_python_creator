"""
WorksheetBuilder - Generates Tableau worksheet XML for various visualization types.

SKILL DOCUMENTATION:
====================
Worksheets are individual visualizations in Tableau. This builder supports:
- Bar charts (horizontal/vertical)
- Scatter plots (dual-axis with circles)
- Maps (filled/choropleth with geographic data)
- Text/KPI cards (Big Ass Numbers - BANs)
- Area/Line charts (sparklines)

KEY CONCEPTS:
- Mark types: 'Automatic', 'Bar', 'Line', 'Area', 'Circle', 'Square', 'Text', 'Map', 'Polygon'
- Shelves: rows (Y-axis), cols (X-axis)
- Encodings: color, size, detail, label, tooltip
- Column instances: Field references with derivation (Sum, Avg, None, etc.)

FIELD REFERENCE FORMAT:
- Dimensions: [none:FieldName:nk] where nk = nominal key
- Measures: [sum:FieldName:qk] or [avg:FieldName:qk] where qk = quantitative key
- Full reference: [datasource_name].[field_instance]

USAGE EXAMPLE:
    ws = WorksheetBuilder('Sales by Category', 'federated.abc1234')
    ws.set_mark_type('Bar')
    ws.add_row_field('Category', 'dimension')
    ws.add_col_field('Sales', 'measure', aggregation='Sum')
    ws.add_color_encoding('Region', 'dimension')
    xml = ws.to_xml()
"""

import html
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Literal
from enum import Enum


class MarkType(Enum):
    """
    Available mark types in Tableau.

    SKILL DOCUMENTATION:
    ====================
    AUTOMATIC - Tableau infers best mark type from data
    BAR - Horizontal or vertical bars (default for dimension + measure)
    LINE - Connected line chart (good for time series)
    AREA - Filled area chart (good for sparklines, cumulative)
    CIRCLE - Scatter plot points
    SQUARE - Square marks (heat maps)
    TEXT - Text labels only (KPI cards, BANs)
    MAP - Geographic filled map (requires lat/lon or geo-coded fields)
    POLYGON - Custom shapes with path order
    """
    AUTOMATIC = 'Automatic'
    BAR = 'Bar'
    LINE = 'Line'
    AREA = 'Area'
    CIRCLE = 'Circle'
    SQUARE = 'Square'
    TEXT = 'Text'
    MAP = 'Map'
    POLYGON = 'Polygon'
    SHAPE = 'Shape'
    PIE = 'Pie'
    GANTT = 'GanttBar'


class Aggregation(Enum):
    """
    Aggregation types for measures.

    SKILL DOCUMENTATION:
    ====================
    NONE - No aggregation (for dimensions or LOD expressions)
    SUM - Sum of values (default for most measures)
    AVG - Average/mean
    COUNT - Count of rows
    COUNTD - Count distinct
    MIN - Minimum value
    MAX - Maximum value
    MEDIAN - Median value
    ATTR - Attribute (returns value if all same, else *)
    """
    NONE = 'None'
    SUM = 'Sum'
    AVG = 'Avg'
    COUNT = 'Count'
    COUNTD = 'Countd'
    MIN = 'Min'
    MAX = 'Max'
    MEDIAN = 'Median'
    ATTR = 'Attr'


@dataclass
class FieldPlacement:
    """
    Represents a field placed on a shelf (rows/cols) or encoding.

    SKILL DOCUMENTATION:
    ====================
    Fields can be placed on:
    - Rows shelf (Y-axis)
    - Cols shelf (X-axis)
    - Color encoding
    - Size encoding
    - Detail (LOD - Level of Detail)
    - Label/Text
    - Tooltip

    INSTANCE NAMING CONVENTION:
    - [derivation:FieldName:type_key]
    - derivation: none, sum, avg, min, max, usr (for pre-aggregated calcs)
    - type_key: nk (nominal), ok (ordinal), qk (quantitative)

    Examples:
    - [none:Category:nk] - Category as dimension
    - [sum:Sales:qk] - Sum of Sales as measure
    - [usr:Calculation_xxx:qk] - Pre-aggregated calculated field (already has SUM/AVG in formula)

    CRITICAL: For calculated fields that already contain aggregation functions
    like SUM([Profit])/SUM([Sales]), use derivation='User' and prefix 'usr:'.
    This tells Tableau to use the calculation as-is without wrapping in another aggregation.
    """
    field_name: str
    field_type: Literal['dimension', 'measure']
    aggregation: Aggregation = Aggregation.NONE
    is_calculated: bool = False
    calc_id: Optional[str] = None  # For calculated fields, the internal ID
    is_preaggregated: bool = False  # True if formula already has SUM/AVG/etc

    @property
    def type_key(self) -> str:
        """Returns nk for nominal (dimension) or qk for quantitative (measure)."""
        return 'nk' if self.field_type == 'dimension' else 'qk'

    @property
    def derivation(self) -> str:
        """
        Returns the derivation string for column-instance.

        SKILL: Pre-aggregated calculated fields use 'User' derivation.
        This tells Tableau to evaluate the formula as-is without additional aggregation.
        """
        if self.field_type == 'dimension':
            return 'None'
        # Pre-aggregated calculated fields (formula already has SUM/AVG) use 'User'
        if self.is_calculated and self.is_preaggregated:
            return 'User'
        return self.aggregation.value

    @property
    def instance_name(self) -> str:
        """
        Generate the column-instance name.

        Format: [derivation:FieldName:type_key]

        SKILL: Pre-aggregated calculated fields use 'usr:' prefix instead of 'sum:', 'avg:', etc.
        """
        name = self.calc_id if self.is_calculated and self.calc_id else self.field_name

        # Pre-aggregated calculated fields use 'usr:' prefix
        if self.is_calculated and self.is_preaggregated:
            return f"[usr:{name}:{self.type_key}]"

        deriv = self.derivation.lower()
        return f"[{deriv}:{name}:{self.type_key}]"

    @property
    def bracket_name(self) -> str:
        """Get the field name in brackets for XML references."""
        if self.is_calculated and self.calc_id:
            return f"[{self.calc_id}]"
        return f"[{self.field_name}]"

    def to_column_instance_xml(self) -> str:
        """
        Generate <column-instance> XML for datasource-dependencies.

        SKILL DOCUMENTATION:
        ====================
        Column instances define how a field is used in a specific view.

        Attributes:
        - column: Reference to the source column [FieldName]
        - derivation: How the field is aggregated (None, Sum, Avg, User, etc.)
        - name: The instance name [derivation:Field:key]
        - pivot: Usually 'key'
        - type: 'nominal', 'ordinal', or 'quantitative'

        CRITICAL: Pre-aggregated calculated fields (formulas containing SUM/AVG/etc.)
        must use derivation='User' and name prefix 'usr:' to tell Tableau to
        evaluate the formula as-is without wrapping in additional aggregation.
        """
        field_ref = self.calc_id if self.is_calculated and self.calc_id else self.field_name
        type_val = 'nominal' if self.field_type == 'dimension' else 'quantitative'

        return f'''            <column-instance column='[{field_ref}]' derivation='{self.derivation}' name='{self.instance_name}' pivot='key' type='{type_val}' />'''


class WorksheetBuilder:
    """
    Builds complete worksheet XML for Tableau workbooks.

    SKILL DOCUMENTATION:
    ====================
    A worksheet defines a single visualization with:
    - Data source reference
    - Field placements (rows, cols, encodings)
    - Mark type and styling
    - Filters (optional)

    TWB STRUCTURE:
    <worksheet name='Sheet Name'>
      <table>
        <view>
          <datasources>...</datasources>
          <datasource-dependencies>...</datasource-dependencies>
          <aggregation value='true' />
        </view>
        <style />
        <panes>
          <pane>
            <view><breakdown value='auto' /></view>
            <mark class='Bar' />
            <encodings>...</encodings>
          </pane>
        </panes>
        <rows>[datasource].[field_instance]</rows>
        <cols>[datasource].[field_instance]</cols>
      </table>
    </worksheet>

    VISUALIZATION TYPE PATTERNS:
    ----------------------------
    1. BAR CHART:
       - rows: dimension [none:Category:nk]
       - cols: measure [sum:Sales:qk]
       - mark: Bar

    2. SCATTER PLOT:
       - rows: measure [sum:Profit:qk]
       - cols: measure [sum:Sales:qk]
       - mark: Circle
       - detail: dimension for each point

    3. MAP (Choropleth):
       - rows: [avg:Latitude (generated):qk]
       - cols: [avg:Longitude (generated):qk]
       - mark: Automatic (Tableau detects Map)
       - color: measure for fill color
       - detail: geographic dimension (State)

    4. KPI CARD (Text):
       - rows: (empty or measure)
       - cols: (empty)
       - mark: Text
       - Single aggregated value displayed

    5. SPARKLINE (Area/Line):
       - rows: measure [sum:Sales:qk]
       - cols: date dimension continuous [none:Order Date:ok]
       - mark: Area or Line
    """

    def __init__(self, name: str, datasource_name: str):
        """
        Initialize a WorksheetBuilder.

        Args:
            name: Worksheet name (shown in tabs and dashboard references)
            datasource_name: Full datasource name (e.g., 'federated.abc1234')
        """
        self.name = name
        self.datasource_name = datasource_name
        self.mark_type = MarkType.AUTOMATIC
        self.rows: List[FieldPlacement] = []
        self.cols: List[FieldPlacement] = []
        self.color_encoding: Optional[FieldPlacement] = None
        self.size_encoding: Optional[FieldPlacement] = None
        self.detail_encodings: List[FieldPlacement] = []
        self.label_encoding: Optional[FieldPlacement] = None
        self.tooltip_fields: List[FieldPlacement] = []
        self.title: Optional[str] = None

        # For map worksheets
        self.is_map = False

        # Column definitions needed for dependencies
        self._dependency_columns: List[Dict] = []

    def set_mark_type(self, mark_type: MarkType) -> 'WorksheetBuilder':
        """
        Set the mark type for this visualization.

        Args:
            mark_type: MarkType enum value

        Returns:
            self for method chaining
        """
        self.mark_type = mark_type
        if mark_type == MarkType.MAP:
            self.is_map = True
        return self

    def add_row_field(self, field_name: str, field_type: Literal['dimension', 'measure'],
                      aggregation: Aggregation = Aggregation.SUM,
                      is_calculated: bool = False, calc_id: Optional[str] = None,
                      is_preaggregated: bool = False) -> 'WorksheetBuilder':
        """
        Add a field to the rows shelf (Y-axis).

        Args:
            field_name: Name of the field
            field_type: 'dimension' or 'measure'
            aggregation: Aggregation type (for measures)
            is_calculated: Whether this is a calculated field
            calc_id: Internal calculation ID (for calculated fields)
            is_preaggregated: True if formula already contains SUM/AVG/etc (uses 'User' derivation)

        Returns:
            self for method chaining
        """
        if field_type == 'dimension':
            aggregation = Aggregation.NONE

        placement = FieldPlacement(
            field_name=field_name,
            field_type=field_type,
            aggregation=aggregation,
            is_calculated=is_calculated,
            calc_id=calc_id,
            is_preaggregated=is_preaggregated
        )
        self.rows.append(placement)
        return self

    def add_col_field(self, field_name: str, field_type: Literal['dimension', 'measure'],
                      aggregation: Aggregation = Aggregation.SUM,
                      is_calculated: bool = False, calc_id: Optional[str] = None,
                      is_preaggregated: bool = False) -> 'WorksheetBuilder':
        """
        Add a field to the columns shelf (X-axis).

        Args:
            field_name: Name of the field
            field_type: 'dimension' or 'measure'
            aggregation: Aggregation type (for measures)
            is_calculated: Whether this is a calculated field
            calc_id: Internal calculation ID (for calculated fields)
            is_preaggregated: True if formula already contains SUM/AVG/etc (uses 'User' derivation)

        Returns:
            self for method chaining
        """
        if field_type == 'dimension':
            aggregation = Aggregation.NONE

        placement = FieldPlacement(
            field_name=field_name,
            field_type=field_type,
            aggregation=aggregation,
            is_calculated=is_calculated,
            calc_id=calc_id,
            is_preaggregated=is_preaggregated
        )
        self.cols.append(placement)
        return self

    def add_color_encoding(self, field_name: str, field_type: Literal['dimension', 'measure'],
                           aggregation: Aggregation = Aggregation.SUM,
                           is_calculated: bool = False, calc_id: Optional[str] = None,
                           is_preaggregated: bool = False) -> 'WorksheetBuilder':
        """
        Add a field to the color encoding (marks card).

        SKILL DOCUMENTATION:
        ====================
        Color encoding determines mark colors:
        - Dimensions: Discrete colors (one per category)
        - Measures: Continuous color gradient

        For maps, use a measure to create choropleth coloring.
        For pre-aggregated calculated fields, set is_preaggregated=True.
        """
        if field_type == 'dimension':
            aggregation = Aggregation.NONE

        self.color_encoding = FieldPlacement(
            field_name=field_name,
            field_type=field_type,
            aggregation=aggregation,
            is_calculated=is_calculated,
            calc_id=calc_id,
            is_preaggregated=is_preaggregated
        )
        return self

    def add_detail_encoding(self, field_name: str, field_type: Literal['dimension', 'measure'] = 'dimension',
                            is_calculated: bool = False, calc_id: Optional[str] = None) -> 'WorksheetBuilder':
        """
        Add a field to the detail encoding (Level of Detail).

        SKILL DOCUMENTATION:
        ====================
        Detail fields affect the level of aggregation without adding visual encoding.
        Common uses:
        - Scatter plots: detail = individual items (one point per item)
        - Maps: detail = geographic level (State, City, etc.)
        """
        placement = FieldPlacement(
            field_name=field_name,
            field_type=field_type,
            aggregation=Aggregation.NONE,
            is_calculated=is_calculated,
            calc_id=calc_id
        )
        self.detail_encodings.append(placement)
        return self

    def add_size_encoding(self, field_name: str, field_type: Literal['dimension', 'measure'] = 'measure',
                          aggregation: Aggregation = Aggregation.SUM,
                          is_calculated: bool = False, calc_id: Optional[str] = None) -> 'WorksheetBuilder':
        """
        Add a field to the size encoding.

        Useful for bubble charts where mark size represents a measure.
        """
        self.size_encoding = FieldPlacement(
            field_name=field_name,
            field_type=field_type,
            aggregation=aggregation,
            is_calculated=is_calculated,
            calc_id=calc_id
        )
        return self

    def add_label_encoding(self, field_name: str, field_type: Literal['dimension', 'measure'],
                           aggregation: Aggregation = Aggregation.SUM,
                           is_calculated: bool = False, calc_id: Optional[str] = None,
                           is_preaggregated: bool = False) -> 'WorksheetBuilder':
        """
        Add a field to display as label on marks.

        For pre-aggregated calculated fields, set is_preaggregated=True.
        """
        if field_type == 'dimension':
            aggregation = Aggregation.NONE

        self.label_encoding = FieldPlacement(
            field_name=field_name,
            field_type=field_type,
            aggregation=aggregation,
            is_calculated=is_calculated,
            calc_id=calc_id,
            is_preaggregated=is_preaggregated
        )
        return self

    def add_dependency_column(self, name: str, datatype: str, role: str, col_type: str,
                              caption: Optional[str] = None, aggregation: Optional[str] = None,
                              semantic_role: Optional[str] = None) -> 'WorksheetBuilder':
        """
        Add a column definition for datasource-dependencies.

        This is needed for columns referenced in the worksheet that need
        explicit type information.
        """
        self._dependency_columns.append({
            'name': name,
            'datatype': datatype,
            'role': role,
            'type': col_type,
            'caption': caption or name,
            'aggregation': aggregation,
            'semantic_role': semantic_role
        })
        return self

    def _get_all_field_placements(self) -> List[FieldPlacement]:
        """Get all field placements used in this worksheet."""
        placements = []
        placements.extend(self.rows)
        placements.extend(self.cols)
        if self.color_encoding:
            placements.append(self.color_encoding)
        if self.size_encoding:
            placements.append(self.size_encoding)
        placements.extend(self.detail_encodings)
        if self.label_encoding:
            placements.append(self.label_encoding)
        placements.extend(self.tooltip_fields)
        return placements

    def _build_dependency_columns_xml(self) -> str:
        """Build <column> elements for datasource-dependencies."""
        parts = []
        for col in self._dependency_columns:
            agg_attr = f" aggregation='{col['aggregation']}'" if col.get('aggregation') else ""
            sem_attr = f" semantic-role='{col['semantic_role']}'" if col.get('semantic_role') else ""
            parts.append(
                f"          <column caption='{html.escape(col['caption'])}' datatype='{col['datatype']}' "
                f"name='[{col['name']}]' role='{col['role']}' type='{col['type']}'{agg_attr}{sem_attr} />"
            )
        return '\n'.join(parts)

    def _build_column_instances_xml(self) -> str:
        """Build <column-instance> elements for all field placements."""
        seen = set()
        parts = []
        for fp in self._get_all_field_placements():
            key = fp.instance_name
            if key not in seen:
                seen.add(key)
                parts.append(fp.to_column_instance_xml())
        return '\n'.join(parts)

    def _build_encodings_xml(self) -> str:
        """
        Build the <encodings> section for the marks card.

        SKILL DOCUMENTATION:
        ====================
        Encodings define visual properties of marks:
        <encodings>
          <color column='[ds].[field]' />
          <size column='[ds].[field]' />
          <lod column='[ds].[field]' />  <!-- detail/LOD -->
          <text column='[ds].[field]' />
        </encodings>
        """
        parts = []

        if self.color_encoding:
            full_ref = f"[{self.datasource_name}].{self.color_encoding.instance_name}"
            parts.append(f"              <color column='{full_ref}' />")

        if self.size_encoding:
            full_ref = f"[{self.datasource_name}].{self.size_encoding.instance_name}"
            parts.append(f"              <size column='{full_ref}' />")

        for detail in self.detail_encodings:
            full_ref = f"[{self.datasource_name}].{detail.instance_name}"
            parts.append(f"              <lod column='{full_ref}' />")

        if self.label_encoding:
            full_ref = f"[{self.datasource_name}].{self.label_encoding.instance_name}"
            parts.append(f"              <text column='{full_ref}' />")

        if parts:
            return f'''            <encodings>
{chr(10).join(parts)}
            </encodings>'''
        return ''

    def _build_rows_xml(self) -> str:
        """Build the <rows> element content."""
        if not self.rows:
            return ''
        # IMPORTANT: Multiple fields must be space-separated, not newline-separated
        # Tableau parses this as a single expression where fields are combined
        refs = [f"[{self.datasource_name}].{fp.instance_name}" for fp in self.rows]
        return ' '.join(refs)

    def _build_cols_xml(self) -> str:
        """Build the <cols> element content."""
        if not self.cols:
            return ''
        # IMPORTANT: Multiple fields must be space-separated, not newline-separated
        refs = [f"[{self.datasource_name}].{fp.instance_name}" for fp in self.cols]
        return ' '.join(refs)

    def to_xml(self) -> str:
        """
        Generate the complete <worksheet> XML.

        SKILL DOCUMENTATION:
        ====================
        This produces a complete worksheet element that can be included
        in the <worksheets> section of a TWB file.
        """
        dep_columns = self._build_dependency_columns_xml()
        col_instances = self._build_column_instances_xml()
        encodings = self._build_encodings_xml()
        rows_content = self._build_rows_xml()
        cols_content = self._build_cols_xml()

        # Build pane content
        encodings_section = f"\n{encodings}" if encodings else ""

        return f'''    <worksheet name='{html.escape(self.name)}'>
      <table>
        <view>
          <datasources>
            <datasource caption='{self.datasource_name.split(".")[-1]}' name='{self.datasource_name}' />
          </datasources>
          <datasource-dependencies datasource='{self.datasource_name}'>
{dep_columns}
{col_instances}
          </datasource-dependencies>
          <aggregation value='true' />
        </view>
        <style />
        <panes>
          <pane selection-relaxation-option='selection-relaxation-allow'>
            <view>
              <breakdown value='auto' />
            </view>
            <mark class='{self.mark_type.value}' />{encodings_section}
          </pane>
        </panes>
        <rows>{rows_content}</rows>
        <cols>{cols_content}</cols>
      </table>
    </worksheet>'''


# ==============================================================================
# FACTORY FUNCTIONS FOR COMMON WORKSHEET TYPES
# ==============================================================================
# These functions create pre-configured WorksheetBuilder instances for common
# visualization patterns. Use these as templates for creating specific chart types.

def create_bar_chart(name: str, datasource_name: str,
                     dimension_field: str, measure_field: str,
                     color_field: Optional[str] = None) -> WorksheetBuilder:
    """
    Factory function to create a horizontal bar chart worksheet.

    SKILL DOCUMENTATION:
    ====================
    Creates a standard bar chart with:
    - Dimension on rows (categories)
    - Measure on columns (bar length)
    - Optional color encoding

    Args:
        name: Worksheet name
        datasource_name: Datasource reference
        dimension_field: Field for categories (rows)
        measure_field: Field for values (columns)
        color_field: Optional field for bar colors

    Returns:
        Configured WorksheetBuilder
    """
    ws = WorksheetBuilder(name, datasource_name)
    ws.set_mark_type(MarkType.BAR)
    ws.add_row_field(dimension_field, 'dimension')
    ws.add_col_field(measure_field, 'measure', Aggregation.SUM)

    # Add column dependencies
    ws.add_dependency_column(dimension_field, 'string', 'dimension', 'nominal')
    ws.add_dependency_column(measure_field, 'real', 'measure', 'quantitative', aggregation='Sum')

    if color_field:
        ws.add_color_encoding(color_field, 'dimension')
        ws.add_dependency_column(color_field, 'string', 'dimension', 'nominal')

    return ws


def create_scatter_plot(name: str, datasource_name: str,
                        x_measure: str, y_measure: str,
                        detail_field: str,
                        color_field: Optional[str] = None) -> WorksheetBuilder:
    """
    Factory function to create a scatter plot worksheet.

    SKILL DOCUMENTATION:
    ====================
    Creates a scatter plot with:
    - Measure on columns (X-axis)
    - Measure on rows (Y-axis)
    - Dimension on detail (one mark per item)
    - Optional color encoding

    Args:
        name: Worksheet name
        datasource_name: Datasource reference
        x_measure: Field for X-axis
        y_measure: Field for Y-axis
        detail_field: Field for individual points
        color_field: Optional field for point colors

    Returns:
        Configured WorksheetBuilder
    """
    ws = WorksheetBuilder(name, datasource_name)
    ws.set_mark_type(MarkType.CIRCLE)
    ws.add_col_field(x_measure, 'measure', Aggregation.SUM)
    ws.add_row_field(y_measure, 'measure', Aggregation.SUM)
    ws.add_detail_encoding(detail_field, 'dimension')

    # Add column dependencies
    ws.add_dependency_column(x_measure, 'real', 'measure', 'quantitative', aggregation='Sum')
    ws.add_dependency_column(y_measure, 'real', 'measure', 'quantitative', aggregation='Sum')
    ws.add_dependency_column(detail_field, 'string', 'dimension', 'nominal')

    if color_field:
        ws.add_color_encoding(color_field, 'dimension')
        ws.add_dependency_column(color_field, 'string', 'dimension', 'nominal')

    return ws


def create_kpi_card(name: str, datasource_name: str,
                    measure_field: str, aggregation: Aggregation = Aggregation.SUM,
                    is_calculated: bool = False, calc_id: Optional[str] = None) -> WorksheetBuilder:
    """
    Factory function to create a KPI card (BAN - Big Ass Number).

    SKILL DOCUMENTATION:
    ====================
    Creates a text-based KPI display with:
    - Single aggregated measure value
    - Text mark type
    - No dimensions (single value)

    Used for dashboard KPI cards showing totals, ratios, etc.

    Args:
        name: Worksheet name
        datasource_name: Datasource reference
        measure_field: Field to display
        aggregation: How to aggregate the measure
        is_calculated: Whether field is a calculated field
        calc_id: Internal ID for calculated fields

    Returns:
        Configured WorksheetBuilder
    """
    ws = WorksheetBuilder(name, datasource_name)
    ws.set_mark_type(MarkType.TEXT)

    # For KPI cards, we put the measure on rows and use it as a label
    ws.add_row_field(measure_field, 'measure', aggregation, is_calculated, calc_id)
    ws.add_label_encoding(measure_field, 'measure', aggregation, is_calculated, calc_id)

    # Add dependency
    field_ref = calc_id if is_calculated and calc_id else measure_field
    ws.add_dependency_column(field_ref, 'real', 'measure', 'quantitative',
                            caption=measure_field, aggregation=aggregation.value)

    return ws


def create_sparkline(name: str, datasource_name: str,
                     measure_field: str, date_field: str,
                     mark_type: MarkType = MarkType.AREA,
                     aggregation: Aggregation = Aggregation.SUM,
                     is_calculated: bool = False, calc_id: Optional[str] = None) -> WorksheetBuilder:
    """
    Factory function to create a sparkline chart.

    SKILL DOCUMENTATION:
    ====================
    Creates a minimal trend chart (sparkline) with:
    - Measure on rows
    - Date/time on columns (continuous)
    - Area or Line mark type
    - Minimal chrome (no axes labels, gridlines hidden in formatting)

    Used alongside KPI cards to show trends.

    Args:
        name: Worksheet name
        datasource_name: Datasource reference
        measure_field: Field for Y-axis values
        date_field: Date field for X-axis
        mark_type: AREA or LINE
        aggregation: How to aggregate the measure
        is_calculated: Whether measure is a calculated field
        calc_id: Internal ID for calculated fields

    Returns:
        Configured WorksheetBuilder
    """
    ws = WorksheetBuilder(name, datasource_name)
    ws.set_mark_type(mark_type)

    # Measure on rows, date on columns
    ws.add_row_field(measure_field, 'measure', aggregation, is_calculated, calc_id)
    ws.add_col_field(date_field, 'dimension')  # Date as dimension for discrete points

    # Add dependencies
    field_ref = calc_id if is_calculated and calc_id else measure_field
    ws.add_dependency_column(field_ref, 'real', 'measure', 'quantitative',
                            caption=measure_field, aggregation=aggregation.value)
    ws.add_dependency_column(date_field, 'datetime', 'dimension', 'ordinal')

    return ws


def create_map_worksheet(name: str, datasource_name: str,
                         geo_field: str, color_measure: str,
                         color_aggregation: Aggregation = Aggregation.AVG,
                         is_color_calculated: bool = False,
                         color_calc_id: Optional[str] = None) -> WorksheetBuilder:
    """
    Factory function to create a filled/choropleth map worksheet.

    SKILL DOCUMENTATION:
    ====================
    Creates a geographic map with:
    - Auto-generated Latitude on rows
    - Auto-generated Longitude on columns
    - Geographic field on detail (State, Country, etc.)
    - Measure on color encoding (fills polygons)

    IMPORTANT: The geographic field must have a semantic-role set in the
    datasource (e.g., '[State].[Name]' for US states).

    Tableau automatically generates Latitude/Longitude when:
    1. A field has a geographic role
    2. It's placed on detail or another encoding
    3. The mark type is set appropriately

    Args:
        name: Worksheet name
        datasource_name: Datasource reference
        geo_field: Geographic field (State, Country, etc.)
        color_measure: Measure field for fill color
        color_aggregation: How to aggregate the color measure
        is_color_calculated: Whether color field is calculated
        color_calc_id: Internal ID for calculated color field

    Returns:
        Configured WorksheetBuilder
    """
    ws = WorksheetBuilder(name, datasource_name)
    ws.set_mark_type(MarkType.AUTOMATIC)  # Tableau auto-detects Map
    ws.is_map = True

    # For maps, we use generated Lat/Lon fields
    # These are special Tableau-generated fields when geographic roles are assigned
    ws.add_row_field('Latitude (generated)', 'measure', Aggregation.AVG)
    ws.add_col_field('Longitude (generated)', 'measure', Aggregation.AVG)

    # Geographic field on detail determines the map level
    ws.add_detail_encoding(geo_field, 'dimension')

    # Color encoding for the choropleth fill
    ws.add_color_encoding(color_measure, 'measure', color_aggregation,
                         is_color_calculated, color_calc_id)

    # Add dependencies
    ws.add_dependency_column('Latitude (generated)', 'real', 'measure', 'quantitative',
                            aggregation='Avg')
    ws.add_dependency_column('Longitude (generated)', 'real', 'measure', 'quantitative',
                            aggregation='Avg')
    ws.add_dependency_column(geo_field, 'string', 'dimension', 'nominal',
                            semantic_role='[State].[Name]')

    color_ref = color_calc_id if is_color_calculated and color_calc_id else color_measure
    ws.add_dependency_column(color_ref, 'real', 'measure', 'quantitative',
                            caption=color_measure, aggregation=color_aggregation.value)

    return ws
