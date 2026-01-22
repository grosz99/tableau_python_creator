# tableau_python_creator

Programmatically generate Tableau workbooks (.twbx) from Python. No Tableau Desktop required for generation.
What It Does

Takes data (Excel, CSV, DataFrame) and chart specifications
Generates valid Tableau workbook files
Output opens directly in Tableau Desktop

Why
Tableau dashboard development is slow. This library lets you:

Prototype faster — generate starter dashboards from code
Automate — build dashboards programmatically from data pipelines
Integrate with AI — expose as MCP tools for Claude to build dashboards from natural language

Installation
bashpip install pandas pantab jinja2 openpyxl
Quick Start
pythonfrom tableau_builder import Workbook, Worksheet, Dashboard, Datasource

# Load your data
ds = Datasource.from_excel("sales_data.xlsx")

# Create a bar chart
bar = Worksheet.bar_chart(
    datasource=ds,
    name="Sales by Category",
    dimension="Category",
    measure="Sales"
)

# Create a dashboard
dashboard = Dashboard("Sales Dashboard")
dashboard.add(bar)

# Export
wb = Workbook(datasource=ds, worksheets=[bar], dashboard=dashboard)
wb.to_twbx("output.twbx")
Open output.twbx in Tableau Desktop.
