"""
DatasourceBuilder - Generates Tableau datasource XML with calculated fields and geographic roles.

SKILL DOCUMENTATION:
====================
This module handles the datasource section of a Tableau TWB file, which defines:
1. Connection to the data (Hyper extract file)
2. Column definitions with data types and roles
3. Calculated fields with formulas
4. Geographic semantic roles for mapping

KEY CONCEPTS:
- Datasource names use format: federated.{7-char-uuid}
- Columns have: name, caption, datatype, role (dimension/measure), type (nominal/quantitative)
- Calculated fields are columns with nested <calculation> elements
- Geographic roles use semantic-role attribute: [State].[Name], [Country].[Name], etc.

USAGE EXAMPLE:
    ds = DatasourceBuilder('federated.abc1234', 'Data/Extract.hyper')
    ds.add_column('Sales', 'real', 'measure', 'quantitative')
    ds.add_column('State', 'string', 'dimension', 'nominal', geo_role='State')
    ds.add_calculated_field(CalculatedField('Profit Ratio', 'SUM([Profit])/SUM([Sales])'))
    xml = ds.to_xml()
"""

import uuid
import html
from dataclasses import dataclass, field
from typing import List, Optional, Dict


@dataclass
class CalculatedField:
    """
    Represents a Tableau calculated field.

    SKILL DOCUMENTATION:
    ====================
    Calculated fields allow custom formulas in Tableau. They are stored as <column>
    elements with a nested <calculation> element.

    FORMULA SYNTAX:
    - Field references: [FieldName]
    - Aggregations: SUM([Field]), AVG([Field]), COUNT([Field]), MIN([Field]), MAX([Field])
    - Math operators: +, -, *, /
    - Date functions: YEAR([Date]), MONTH([Date]), DATETRUNC('month', [Date])
    - String functions: LEFT([Field], n), SPLIT([Field], ' ', 1)
    - Logical: IF condition THEN value ELSE value END

    XML OUTPUT FORMAT:
    <column caption='Profit Ratio' datatype='real' name='[Calculation_abc123]'
            role='measure' type='quantitative'>
      <calculation class='tableau' formula='SUM([Profit])/SUM([Sales])' />
    </column>

    ATTRIBUTES:
        caption: Display name shown in Tableau UI
        formula: Tableau calculation formula
        datatype: 'real', 'integer', 'string', 'boolean', 'date', 'datetime'
        role: 'measure' or 'dimension'
        col_type: 'quantitative', 'nominal', 'ordinal'
        default_format: Optional format string (e.g., 'p0%' for percentage)
    """
    caption: str
    formula: str
    datatype: str = 'real'
    role: str = 'measure'
    col_type: str = 'quantitative'
    default_format: Optional[str] = None
    _calc_id: str = field(default_factory=lambda: f"Calculation_{uuid.uuid4().hex[:12]}")

    @property
    def name(self) -> str:
        """Returns the internal field name used in TWB XML."""
        return f"[{self._calc_id}]"

    @property
    def clean_name(self) -> str:
        """Returns the calculation ID without brackets."""
        return self._calc_id

    def to_column_xml(self) -> str:
        """
        Generate the <column> XML for the datasource section.

        Note: Formula must be HTML-escaped for XML compatibility.
        Special chars like < > & ' " need escaping.
        """
        escaped_formula = html.escape(self.formula, quote=True)
        # Also escape single quotes for XML attribute
        escaped_formula = escaped_formula.replace("'", "&apos;")

        format_attr = f" default-format='{self.default_format}'" if self.default_format else ""

        return f'''      <column caption='{html.escape(self.caption)}' datatype='{self.datatype}' name='{self.name}' role='{self.role}' type='{self.col_type}'{format_attr}>
        <calculation class='tableau' formula='{escaped_formula}' />
      </column>'''

    def to_dependency_xml(self, with_aggregation: bool = True) -> str:
        """
        Generate the <column> XML for datasource-dependencies section.

        This is a simplified version used within worksheet views.
        """
        agg_attr = " aggregation='Sum'" if self.role == 'measure' and with_aggregation else ""
        return f'''          <column caption='{html.escape(self.caption)}' datatype='{self.datatype}' name='{self.name}' role='{self.role}' type='{self.col_type}'{agg_attr} />'''


@dataclass
class ColumnDefinition:
    """
    Represents a standard (non-calculated) column from the data source.

    SKILL DOCUMENTATION:
    ====================
    Regular columns map directly to fields in the Hyper extract.

    DATATYPE MAPPING (Python -> Tableau):
    - object/string -> 'string'
    - int64/int32 -> 'integer'
    - float64/float32 -> 'real'
    - datetime64 -> 'datetime'
    - bool -> 'boolean'

    ROLE DETERMINATION:
    - Strings/categories -> 'dimension' (categorical data)
    - Numbers -> 'measure' (quantitative data)
    - Dates can be either depending on use

    TYPE MAPPING:
    - Dimensions: 'nominal' (unordered) or 'ordinal' (ordered)
    - Measures: 'quantitative'

    GEOGRAPHIC ROLES (semantic-role attribute):
    - State: '[State].[Name]'
    - Country: '[Country].[Name]' or '[Country].[ISO3166_2]'
    - City: '[City].[Name]'
    - Postal Code: '[ZipCode].[Name]'
    - Latitude: '[Latitude]'
    - Longitude: '[Longitude]'
    """
    name: str
    datatype: str
    role: str
    col_type: str
    caption: Optional[str] = None
    geo_role: Optional[str] = None  # State, Country, City, etc.

    # Mapping of geo role names to semantic-role attribute values
    GEO_ROLE_MAP: Dict[str, str] = field(default_factory=lambda: {
        'State': '[State].[Name]',
        'Country': '[Country].[Name]',
        'Country_ISO': '[Country].[ISO3166_2]',
        'City': '[City].[Name]',
        'Postal Code': '[ZipCode].[Name]',
        'ZipCode': '[ZipCode].[Name]',
        'Latitude': '[Latitude]',
        'Longitude': '[Longitude]',
        'Region': '[State].[Name]',  # Tableau treats regions as states
        'County': '[County].[Name]',
    })

    def __post_init__(self):
        if self.caption is None:
            self.caption = self.name

    def to_column_xml(self) -> str:
        """
        Generate <column> XML for the datasource section.

        Includes semantic-role attribute if geo_role is specified.
        """
        geo_attr = ""
        if self.geo_role and self.geo_role in self.GEO_ROLE_MAP:
            semantic_role = self.GEO_ROLE_MAP[self.geo_role]
            geo_attr = f" semantic-role='{semantic_role}'"

        return f'''      <column caption='{html.escape(self.caption)}' datatype='{self.datatype}' name='[{self.name}]' role='{self.role}' type='{self.col_type}'{geo_attr} />'''

    def to_dependency_xml(self) -> str:
        """Generate <column> XML for datasource-dependencies section."""
        agg_attr = " aggregation='Sum'" if self.role == 'measure' else ""
        return f'''          <column caption='{html.escape(self.caption)}' datatype='{self.datatype}' name='[{self.name}]' role='{self.role}' type='{self.col_type}'{agg_attr} />'''


class DatasourceBuilder:
    """
    Builds the complete datasource XML section of a Tableau workbook.

    SKILL DOCUMENTATION:
    ====================
    The datasource section defines data connections, columns, and calculations.

    TWB STRUCTURE:
    <datasources>
      <datasource caption='Extract' inline='true' name='federated.xxx' version='18.1'>
        <connection class='hyper' dbname='Data/Extract.hyper' ...>
          <relation name='Extract' table='[public].[Extract]' type='table' />
        </connection>
        <column ... />  <!-- Regular columns -->
        <column ... />  <!-- Calculated fields -->
      </datasource>
    </datasources>

    WORKFLOW:
    1. Create DatasourceBuilder with unique name and hyper path
    2. Add columns from DataFrame using add_column() or add_columns_from_df()
    3. Add calculated fields using add_calculated_field()
    4. Set geographic roles for map-enabled columns
    5. Call to_xml() to generate the complete datasource XML

    ATTRIBUTES:
        name: Unique datasource identifier (federated.{uuid})
        hyper_path: Relative path to Hyper file in TWBX (usually 'Data/Extract.hyper')
        caption: Display name for the datasource
    """

    def __init__(self, name: str, hyper_path: str = 'Data/Extract.hyper', caption: str = 'Extract'):
        """
        Initialize a new DatasourceBuilder.

        Args:
            name: Unique datasource name (recommend: federated.{uuid.uuid4().hex[:7]})
            hyper_path: Path to Hyper file within TWBX archive
            caption: Display name shown in Tableau
        """
        self.name = name
        self.hyper_path = hyper_path
        self.caption = caption
        self.columns: List[ColumnDefinition] = []
        self.calculated_fields: List[CalculatedField] = []

    def add_column(self, name: str, datatype: str, role: str, col_type: str,
                   caption: Optional[str] = None, geo_role: Optional[str] = None) -> 'DatasourceBuilder':
        """
        Add a column definition to the datasource.

        Args:
            name: Field name (must match column name in Hyper extract)
            datatype: Tableau datatype ('string', 'real', 'integer', 'datetime', 'date', 'boolean')
            role: 'dimension' or 'measure'
            col_type: 'nominal', 'ordinal', or 'quantitative'
            caption: Display name (defaults to name)
            geo_role: Geographic role ('State', 'Country', 'City', 'Postal Code', etc.)

        Returns:
            self for method chaining
        """
        col = ColumnDefinition(
            name=name,
            datatype=datatype,
            role=role,
            col_type=col_type,
            caption=caption,
            geo_role=geo_role
        )
        self.columns.append(col)
        return self

    def add_columns_from_df(self, df, geo_roles: Optional[Dict[str, str]] = None) -> 'DatasourceBuilder':
        """
        Automatically add column definitions by inspecting a pandas DataFrame.

        SKILL DOCUMENTATION:
        ====================
        This method infers Tableau column metadata from pandas dtypes:
        - object/string -> string dimension
        - int64/int32 -> integer measure
        - float64/float32 -> real measure
        - datetime64 -> datetime dimension
        - bool -> boolean dimension

        Args:
            df: pandas DataFrame to inspect
            geo_roles: Dict mapping column names to geographic roles
                      e.g., {'State': 'State', 'Country': 'Country'}

        Returns:
            self for method chaining
        """
        geo_roles = geo_roles or {}

        for col_name in df.columns:
            dtype = df[col_name].dtype

            # Determine Tableau datatype, role, and type from pandas dtype
            if dtype == 'object' or dtype.name == 'string':
                datatype = 'string'
                role = 'dimension'
                col_type = 'nominal'
            elif dtype in ['int64', 'int32']:
                datatype = 'integer'
                role = 'measure'
                col_type = 'quantitative'
            elif dtype in ['float64', 'float32']:
                datatype = 'real'
                role = 'measure'
                col_type = 'quantitative'
            elif 'datetime' in str(dtype):
                datatype = 'datetime'
                role = 'dimension'
                col_type = 'ordinal'
            elif dtype == 'bool':
                datatype = 'boolean'
                role = 'dimension'
                col_type = 'nominal'
            else:
                # Default fallback
                datatype = 'string'
                role = 'dimension'
                col_type = 'nominal'

            geo_role = geo_roles.get(col_name)
            self.add_column(col_name, datatype, role, col_type, geo_role=geo_role)

        return self

    def add_calculated_field(self, calc_field: CalculatedField) -> 'DatasourceBuilder':
        """
        Add a calculated field to the datasource.

        Args:
            calc_field: CalculatedField instance with formula and metadata

        Returns:
            self for method chaining
        """
        self.calculated_fields.append(calc_field)
        return self

    def get_calculated_field(self, caption: str) -> Optional[CalculatedField]:
        """
        Retrieve a calculated field by its caption.

        Useful for referencing the field's internal name in worksheets.
        """
        for cf in self.calculated_fields:
            if cf.caption == caption:
                return cf
        return None

    def get_column(self, name: str) -> Optional[ColumnDefinition]:
        """Retrieve a column definition by name."""
        for col in self.columns:
            if col.name == name:
                return col
        return None

    def to_xml(self) -> str:
        """
        Generate the complete <datasource> XML.

        SKILL DOCUMENTATION:
        ====================
        Output structure:
        <datasource caption='...' inline='true' name='...' version='18.1'>
          <connection class='hyper' dbname='...' default-settings='yes' sslmode='' username='tableau'>
            <relation name='Extract' table='[public].[Extract]' type='table' />
          </connection>
          <!-- Regular columns -->
          <!-- Calculated fields -->
        </datasource>
        """
        # Build column definitions
        column_xml_parts = []
        for col in self.columns:
            column_xml_parts.append(col.to_column_xml())

        for calc in self.calculated_fields:
            column_xml_parts.append(calc.to_column_xml())

        columns_xml = '\n'.join(column_xml_parts)

        return f'''    <datasource caption='{html.escape(self.caption)}' inline='true' name='{self.name}' version='18.1'>
      <connection class='hyper' dbname='{self.hyper_path}' default-settings='yes' sslmode='' username='tableau'>
        <relation name='Extract' table='[public].[Extract]' type='table' />
      </connection>
{columns_xml}
    </datasource>'''

    def get_dependency_columns_xml(self, field_names: List[str]) -> str:
        """
        Generate <column> elements for datasource-dependencies section.

        Used by WorksheetBuilder to include only the columns used in a worksheet.

        Args:
            field_names: List of field names (captions) to include

        Returns:
            XML string with column elements
        """
        parts = []
        for name in field_names:
            # Check regular columns
            for col in self.columns:
                if col.name == name or col.caption == name:
                    parts.append(col.to_dependency_xml())
                    break
            else:
                # Check calculated fields
                for calc in self.calculated_fields:
                    if calc.caption == name:
                        parts.append(calc.to_dependency_xml())
                        break

        return '\n'.join(parts)
