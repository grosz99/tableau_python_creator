"""
DashboardBuilder - Generates Tableau dashboard XML with zone-based layouts.

SKILL DOCUMENTATION:
====================
Dashboards arrange multiple worksheets into a single view. This builder handles:
- Zone-based layouts (tiled arrangement)
- Worksheet placement with x, y, width, height
- Container zones for grouping
- Filter zones for interactive filtering
- Text/title zones

KEY CONCEPTS:
- Tableau uses a 100,000 unit coordinate system (0-100000 for both x and y)
- Zones can be worksheets, containers, text, filters, or blanks
- Container zones (layout-basic) group child zones horizontally or vertically
- Zone IDs must be unique integers

COORDINATE SYSTEM:
- Origin (0, 0) is top-left
- x increases to the right
- y increases downward
- w (width) and h (height) are in the same 100,000 unit scale
- 100000 = 100% of available space

USAGE EXAMPLE:
    db = DashboardBuilder('Sales Dashboard', width=1400, height=900)
    db.add_worksheet_zone('Sheet 1', x=0, y=0, w=50000, h=50000)
    db.add_worksheet_zone('Sheet 2', x=50000, y=0, w=50000, h=50000)
    xml = db.to_xml()
"""

import html
from dataclasses import dataclass, field
from typing import List, Optional, Literal
from enum import Enum


class ZoneType(Enum):
    """
    Types of zones in a Tableau dashboard.

    SKILL DOCUMENTATION:
    ====================
    LAYOUT_BASIC - Container zone for grouping other zones
    WORKSHEET - References a worksheet by name
    TEXT - Text box or annotation
    TITLE - Dashboard title
    FILTER - Quick filter control
    PARAMETER - Parameter control
    BLANK - Empty space/padding
    IMAGE - Image element
    WEB - Web page embed
    """
    LAYOUT_BASIC = 'layout-basic'
    WORKSHEET = 'worksheet'
    TEXT = 'text'
    TITLE = 'title'
    FILTER = 'filter'
    PARAMETER = 'paramctrl'
    BLANK = 'blank'
    IMAGE = 'bitmap'
    WEB = 'web'


@dataclass
class DashboardZone:
    """
    Represents a single zone in a dashboard layout.

    SKILL DOCUMENTATION:
    ====================
    Zones are the building blocks of dashboard layouts. Each zone has:
    - Position (x, y) relative to parent container
    - Size (w, h) in Tableau's 100,000 unit scale
    - Type (worksheet, container, filter, etc.)
    - Optional name (for worksheet references)

    ZONE XML FORMAT:
    <zone h='50000' id='5' name='Sheet 1' w='50000' x='0' y='0' type-v2='worksheet' />

    For containers:
    <zone h='100000' id='1' type-v2='layout-basic' w='100000' x='0' y='0'>
      <zone ... />  <!-- child zones -->
    </zone>

    ATTRIBUTES:
        zone_id: Unique integer ID for this zone
        zone_type: ZoneType enum value
        x, y: Position in 100,000 unit scale
        w, h: Size in 100,000 unit scale
        name: Worksheet name (for WORKSHEET type)
        children: Child zones (for LAYOUT_BASIC containers)
        param_name: Parameter/filter field reference
    """
    zone_id: int
    zone_type: ZoneType
    x: int
    y: int
    w: int
    h: int
    name: Optional[str] = None
    children: List['DashboardZone'] = field(default_factory=list)
    param_name: Optional[str] = None  # For filters/parameters

    def to_xml(self, indent: int = 8) -> str:
        """
        Generate XML for this zone and its children.

        Args:
            indent: Number of spaces for indentation

        Returns:
            XML string for this zone
        """
        ind = ' ' * indent
        attrs = [
            f"h='{self.h}'",
            f"id='{self.zone_id}'",
        ]

        if self.name:
            attrs.append(f"name='{html.escape(self.name)}'")

        if self.param_name:
            attrs.append(f"param='{html.escape(self.param_name)}'")

        attrs.extend([
            f"type-v2='{self.zone_type.value}'",
            f"w='{self.w}'",
            f"x='{self.x}'",
            f"y='{self.y}'",
        ])

        attr_str = ' '.join(attrs)

        if self.children:
            # Container with children
            child_xml = '\n'.join(child.to_xml(indent + 2) for child in self.children)
            return f"{ind}<zone {attr_str}>\n{child_xml}\n{ind}</zone>"
        else:
            # Self-closing zone
            return f"{ind}<zone {attr_str} />"


class DashboardBuilder:
    """
    Builds complete dashboard XML for Tableau workbooks.

    SKILL DOCUMENTATION:
    ====================
    Creates a dashboard with:
    - Size specification (pixels)
    - Zone-based layout structure
    - Worksheet references
    - Optional filters and parameters

    TWB STRUCTURE:
    <dashboard name='Dashboard Name'>
      <style />
      <size maxheight='900' maxwidth='1400' minheight='900' minwidth='1400' />
      <zones>
        <zone ...>
          <!-- nested zones -->
        </zone>
      </zones>
    </dashboard>

    LAYOUT PATTERNS:
    ----------------
    1. SIMPLE GRID:
       Create zones with explicit x, y, w, h for each worksheet

    2. NESTED CONTAINERS:
       Use layout-basic containers to create rows/columns
       - Horizontal row: children have same y, different x
       - Vertical column: children have same x, different y

    3. KPI ROW + CONTENT:
       Common pattern for dashboards:
       - Top row: 3 KPI cards side by side (each w=33333)
       - Middle: Map and chart side by side (each w=50000)
       - Bottom: Full-width chart (w=100000)

    USAGE:
        db = DashboardBuilder('My Dashboard', 1400, 900)

        # Add root container
        root = db.add_container_zone(0, 0, 100000, 100000)

        # Add worksheet zones
        db.add_worksheet_zone('KPI 1', 0, 0, 33333, 15000, parent_id=root)
        db.add_worksheet_zone('KPI 2', 33333, 0, 33333, 15000, parent_id=root)
        db.add_worksheet_zone('Map', 0, 15000, 50000, 85000, parent_id=root)

        xml = db.to_xml()
    """

    def __init__(self, name: str, width: int = 1400, height: int = 900):
        """
        Initialize a DashboardBuilder.

        Args:
            name: Dashboard name (shown in Tableau tabs)
            width: Dashboard width in pixels
            height: Dashboard height in pixels
        """
        self.name = name
        self.width = width
        self.height = height
        self._next_zone_id = 4  # Tableau typically starts at 4
        self.zones: List[DashboardZone] = []
        self._zone_lookup: dict = {}  # id -> zone for finding parents

    def _get_next_id(self) -> int:
        """Get the next available zone ID."""
        zone_id = self._next_zone_id
        self._next_zone_id += 1
        return zone_id

    def add_container_zone(self, x: int, y: int, w: int, h: int,
                           parent_id: Optional[int] = None) -> int:
        """
        Add a container zone for grouping other zones.

        SKILL DOCUMENTATION:
        ====================
        Container zones (layout-basic) organize child zones. Use containers for:
        - Grouping related worksheets
        - Creating rows or columns
        - Nesting layouts for complex arrangements

        Args:
            x, y: Position in 100,000 unit scale
            w, h: Size in 100,000 unit scale
            parent_id: ID of parent container (None for root level)

        Returns:
            Zone ID of the new container
        """
        zone_id = self._get_next_id()
        zone = DashboardZone(
            zone_id=zone_id,
            zone_type=ZoneType.LAYOUT_BASIC,
            x=x, y=y, w=w, h=h
        )

        if parent_id is not None and parent_id in self._zone_lookup:
            self._zone_lookup[parent_id].children.append(zone)
        else:
            self.zones.append(zone)

        self._zone_lookup[zone_id] = zone
        return zone_id

    def add_worksheet_zone(self, worksheet_name: str, x: int, y: int, w: int, h: int,
                           parent_id: Optional[int] = None) -> int:
        """
        Add a worksheet zone that displays a worksheet.

        SKILL DOCUMENTATION:
        ====================
        Worksheet zones reference worksheets by name. The worksheet must exist
        in the workbook's <worksheets> section with a matching name.

        IMPORTANT: The name must exactly match the worksheet name in the workbook.

        Args:
            worksheet_name: Name of the worksheet to display
            x, y: Position in 100,000 unit scale
            w, h: Size in 100,000 unit scale
            parent_id: ID of parent container (None for root level)

        Returns:
            Zone ID of the new worksheet zone
        """
        zone_id = self._get_next_id()
        zone = DashboardZone(
            zone_id=zone_id,
            zone_type=ZoneType.WORKSHEET,
            x=x, y=y, w=w, h=h,
            name=worksheet_name
        )

        if parent_id is not None and parent_id in self._zone_lookup:
            self._zone_lookup[parent_id].children.append(zone)
        else:
            self.zones.append(zone)

        self._zone_lookup[zone_id] = zone
        return zone_id

    def add_text_zone(self, x: int, y: int, w: int, h: int,
                      parent_id: Optional[int] = None) -> int:
        """
        Add a text zone for titles or annotations.

        Args:
            x, y: Position in 100,000 unit scale
            w, h: Size in 100,000 unit scale
            parent_id: ID of parent container

        Returns:
            Zone ID
        """
        zone_id = self._get_next_id()
        zone = DashboardZone(
            zone_id=zone_id,
            zone_type=ZoneType.TEXT,
            x=x, y=y, w=w, h=h
        )

        if parent_id is not None and parent_id in self._zone_lookup:
            self._zone_lookup[parent_id].children.append(zone)
        else:
            self.zones.append(zone)

        self._zone_lookup[zone_id] = zone
        return zone_id

    def add_filter_zone(self, field_ref: str, x: int, y: int, w: int, h: int,
                        parent_id: Optional[int] = None) -> int:
        """
        Add a filter control zone.

        SKILL DOCUMENTATION:
        ====================
        Filter zones add interactive filter controls to the dashboard.
        The field_ref should be the full field reference including datasource.

        Format: [datasource_name].[field_instance]
        Example: [federated.abc1234].[none:Order Date:ok]

        Args:
            field_ref: Full field reference for the filter
            x, y: Position in 100,000 unit scale
            w, h: Size in 100,000 unit scale
            parent_id: ID of parent container

        Returns:
            Zone ID
        """
        zone_id = self._get_next_id()
        zone = DashboardZone(
            zone_id=zone_id,
            zone_type=ZoneType.FILTER,
            x=x, y=y, w=w, h=h,
            param_name=field_ref
        )

        if parent_id is not None and parent_id in self._zone_lookup:
            self._zone_lookup[parent_id].children.append(zone)
        else:
            self.zones.append(zone)

        self._zone_lookup[zone_id] = zone
        return zone_id

    def add_blank_zone(self, x: int, y: int, w: int, h: int,
                       parent_id: Optional[int] = None) -> int:
        """
        Add a blank/padding zone.

        Args:
            x, y: Position in 100,000 unit scale
            w, h: Size in 100,000 unit scale
            parent_id: ID of parent container

        Returns:
            Zone ID
        """
        zone_id = self._get_next_id()
        zone = DashboardZone(
            zone_id=zone_id,
            zone_type=ZoneType.BLANK,
            x=x, y=y, w=w, h=h
        )

        if parent_id is not None and parent_id in self._zone_lookup:
            self._zone_lookup[parent_id].children.append(zone)
        else:
            self.zones.append(zone)

        self._zone_lookup[zone_id] = zone
        return zone_id

    def to_xml(self) -> str:
        """
        Generate the complete <dashboard> XML.

        SKILL DOCUMENTATION:
        ====================
        Produces a complete dashboard element including:
        - Size specification
        - All zones (nested structure)

        Note: The zones XML is built recursively, handling nested containers.
        """
        # Build zones XML
        zones_xml = '\n'.join(zone.to_xml(indent=8) for zone in self.zones)

        return f'''    <dashboard name='{html.escape(self.name)}'>
      <style />
      <size maxheight='{self.height}' maxwidth='{self.width}' minheight='{self.height}' minwidth='{self.width}' />
      <zones>
{zones_xml}
      </zones>
    </dashboard>'''


# ==============================================================================
# LAYOUT HELPER FUNCTIONS
# ==============================================================================
# These functions create common dashboard layout patterns.

def create_kpi_row_layout(dashboard: DashboardBuilder, kpi_worksheets: List[str],
                          y_start: int = 0, height: int = 15000,
                          parent_id: Optional[int] = None) -> int:
    """
    Create a row of evenly-spaced KPI cards.

    SKILL DOCUMENTATION:
    ====================
    Common pattern for KPI dashboards: a row of 3-4 KPI cards at the top.
    Each card gets equal width.

    Args:
        dashboard: DashboardBuilder instance
        kpi_worksheets: List of worksheet names for KPI cards
        y_start: Y position for the row
        height: Height of the row
        parent_id: Parent container ID

    Returns:
        Container zone ID for the KPI row
    """
    num_kpis = len(kpi_worksheets)
    if num_kpis == 0:
        return -1

    width_each = 100000 // num_kpis

    # Create container for KPI row
    container_id = dashboard.add_container_zone(0, y_start, 100000, height, parent_id)

    # Add each KPI worksheet
    for i, ws_name in enumerate(kpi_worksheets):
        x = i * width_each
        w = width_each if i < num_kpis - 1 else (100000 - x)  # Last one takes remainder
        dashboard.add_worksheet_zone(ws_name, x, 0, w, height, container_id)

    return container_id


def create_two_column_layout(dashboard: DashboardBuilder,
                             left_worksheet: str, right_worksheet: str,
                             y_start: int, height: int,
                             left_width: int = 50000,
                             parent_id: Optional[int] = None) -> int:
    """
    Create a two-column layout with worksheets side by side.

    SKILL DOCUMENTATION:
    ====================
    Common pattern: two visualizations side by side (e.g., map + chart).

    Args:
        dashboard: DashboardBuilder instance
        left_worksheet: Name of left worksheet
        right_worksheet: Name of right worksheet
        y_start: Y position for the row
        height: Height of the row
        left_width: Width of left column (right gets remainder)
        parent_id: Parent container ID

    Returns:
        Container zone ID
    """
    right_width = 100000 - left_width

    container_id = dashboard.add_container_zone(0, y_start, 100000, height, parent_id)

    dashboard.add_worksheet_zone(left_worksheet, 0, 0, left_width, height, container_id)
    dashboard.add_worksheet_zone(right_worksheet, left_width, 0, right_width, height, container_id)

    return container_id


def create_full_width_layout(dashboard: DashboardBuilder,
                             worksheet: str,
                             y_start: int, height: int,
                             parent_id: Optional[int] = None) -> int:
    """
    Create a full-width worksheet zone.

    SKILL DOCUMENTATION:
    ====================
    Simple pattern: one worksheet spanning the full width.

    Args:
        dashboard: DashboardBuilder instance
        worksheet: Worksheet name
        y_start: Y position
        height: Height
        parent_id: Parent container ID

    Returns:
        Zone ID
    """
    return dashboard.add_worksheet_zone(worksheet, 0, y_start, 100000, height, parent_id)


def create_superstore_dashboard_layout(dashboard: DashboardBuilder,
                                       kpi_worksheets: List[str],
                                       map_worksheet: str,
                                       scatter_worksheet: str,
                                       bar_worksheet: str) -> None:
    """
    Create the complete Superstore Profitability Overview dashboard layout.

    SKILL DOCUMENTATION:
    ====================
    This creates the specific layout matching the target dashboard image:

    +------------------------------------------------------------------+
    | KPI 1 (33.3%)    | KPI 2 (33.3%)    | KPI 3 (33.3%)             | 15%
    +------------------------------------------------------------------+
    | MAP (50%)                    | SCATTER (50%)                    | 45%
    +------------------------------------------------------------------+
    | BAR CHART (100%)                                                | 40%
    +------------------------------------------------------------------+

    Args:
        dashboard: DashboardBuilder instance
        kpi_worksheets: List of 3 KPI worksheet names
        map_worksheet: Map worksheet name
        scatter_worksheet: Scatter plot worksheet name
        bar_worksheet: Bar chart worksheet name
    """
    # Root container
    root_id = dashboard.add_container_zone(0, 0, 100000, 100000)

    # KPI Row (top 15%)
    create_kpi_row_layout(dashboard, kpi_worksheets, y_start=0, height=15000, parent_id=root_id)

    # Middle row: Map + Scatter (45%)
    create_two_column_layout(dashboard, map_worksheet, scatter_worksheet,
                            y_start=15000, height=45000, parent_id=root_id)

    # Bottom row: Bar chart (40%)
    create_full_width_layout(dashboard, bar_worksheet, y_start=60000, height=40000, parent_id=root_id)
