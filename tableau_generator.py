"""
Tableau Workbook Generator
Generates a simple bar chart TWBX from data
"""

import pandas as pd
import pantab as pt
import zipfile
import os
import uuid
from pathlib import Path

# Create sample Superstore-like data
def create_sample_data():
    """Create sample data resembling Superstore"""
    data = {
        'Category': ['Furniture', 'Furniture', 'Office Supplies', 'Office Supplies', 
                     'Technology', 'Technology', 'Furniture', 'Office Supplies', 'Technology'],
        'Sub-Category': ['Chairs', 'Tables', 'Paper', 'Binders', 
                         'Phones', 'Computers', 'Bookcases', 'Labels', 'Accessories'],
        'Sales': [731.94, 957.58, 261.96, 14.62, 
                  911.42, 1097.54, 261.54, 14.62, 407.98],
        'Profit': [219.58, -64.78, 109.61, 4.39,
                   68.36, 274.38, -60.70, 6.16, 122.39],
        'Quantity': [3, 5, 7, 2, 4, 1, 2, 3, 6]
    }
    return pd.DataFrame(data)


def generate_twb(datasource_name: str, dimension_field: str, measure_field: str, columns: list) -> str:
    """
    Generate TWB XML for a simple bar chart
    
    Args:
        datasource_name: Unique identifier for the datasource
        dimension_field: Field to put on rows (category)
        measure_field: Field to put on columns (measure)
        columns: List of dicts with column metadata
    """
    
    # Build column definitions for datasource
    column_defs = []
    for col in columns:
        col_xml = f'''      <column caption='{col["name"]}' datatype='{col["datatype"]}' name='[{col["name"]}]' role='{col["role"]}' type='{col["type"]}' />'''
        column_defs.append(col_xml)
    
    column_defs_str = '\n'.join(column_defs)
    
    # Build column definitions for datasource-dependencies
    dep_columns = []
    for col in columns:
        agg_attr = " aggregation='Sum'" if col["role"] == "measure" else ""
        col_xml = f'''          <column caption='{col["name"]}' datatype='{col["datatype"]}' name='[{col["name"]}]' role='{col["role"]}' type='{col["type"]}'{agg_attr} />'''
        dep_columns.append(col_xml)
    
    dep_columns_str = '\n'.join(dep_columns)
    
    # Determine the dimension and measure column metadata
    dim_col = next(c for c in columns if c["name"] == dimension_field)
    meas_col = next(c for c in columns if c["name"] == measure_field)
    
    twb_xml = f'''<?xml version='1.0' encoding='utf-8' ?>
<workbook source-build='2022.3.0 (20223.22.1005.1835)' source-platform='win' version='18.1' xmlns:user='http://www.tableausoftware.com/xml/user'>
  <preferences>
    <preference name='ui.encoding.shelf.height' value='24' />
    <preference name='ui.shelf.height' value='26' />
  </preferences>
  <datasources>
    <datasource caption='Extract' inline='true' name='{datasource_name}' version='18.1'>
      <connection class='hyper' dbname='Data/Extract.hyper' default-settings='yes' sslmode='' username='tableau'>
        <relation name='Extract' table='[public].[Extract]' type='table' />
      </connection>
{column_defs_str}
    </datasource>
  </datasources>
  <worksheets>
    <worksheet name='Sheet 1'>
      <table>
        <view>
          <datasources>
            <datasource caption='Extract' name='{datasource_name}' />
          </datasources>
          <datasource-dependencies datasource='{datasource_name}'>
{dep_columns_str}
            <column-instance column='[{dimension_field}]' derivation='None' name='[none:{dimension_field}:nk]' pivot='key' type='nominal' />
            <column-instance column='[{measure_field}]' derivation='Sum' name='[sum:{measure_field}:qk]' pivot='key' type='quantitative' />
          </datasource-dependencies>
          <aggregation value='true' />
        </view>
        <style />
        <panes>
          <pane selection-relaxation-option='selection-relaxation-allow'>
            <view>
              <breakdown value='auto' />
            </view>
            <mark class='Automatic' />
          </pane>
        </panes>
        <rows>[{datasource_name}].[none:{dimension_field}:nk]</rows>
        <cols>[{datasource_name}].[sum:{measure_field}:qk]</cols>
      </table>
    </worksheet>
  </worksheets>
  <dashboards>
    <dashboard name='Dashboard 1'>
      <style />
      <size maxheight='800' maxwidth='1200' minheight='800' minwidth='1200' />
      <zones>
        <zone h='100000' id='4' type-v2='layout-basic' w='100000' x='0' y='0'>
          <zone h='100000' id='5' name='Sheet 1' w='100000' x='0' y='0' type-v2='worksheet' />
        </zone>
      </zones>
    </dashboard>
  </dashboards>
  <windows source-height='30'>
    <window class='worksheet' name='Sheet 1'>
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
  </windows>
</workbook>'''
    
    return twb_xml


def get_column_metadata(df: pd.DataFrame) -> list:
    """Extract column metadata from DataFrame"""
    columns = []
    for col_name in df.columns:
        dtype = df[col_name].dtype
        
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
        else:
            datatype = 'string'
            role = 'dimension'
            col_type = 'nominal'
        
        columns.append({
            'name': col_name,
            'datatype': datatype,
            'role': role,
            'type': col_type
        })
    
    return columns


def generate_twbx(df: pd.DataFrame, dimension: str, measure: str, output_path: str):
    """
    Generate a complete TWBX file
    
    Args:
        df: Source DataFrame
        dimension: Column name to use as dimension (rows)
        measure: Column name to use as measure (columns)
        output_path: Path for output .twbx file
    """
    
    # Create temp directory for working files
    work_dir = Path('/home/claude/twbx_temp')
    work_dir.mkdir(exist_ok=True)
    
    # Generate unique datasource name
    ds_id = uuid.uuid4().hex[:7]
    datasource_name = f'federated.{ds_id}'
    
    # 1. Create Hyper extract
    hyper_path = work_dir / 'Extract.hyper'
    print(f"Creating Hyper extract: {hyper_path}")
    pt.frame_to_hyper(df, str(hyper_path), table='Extract')
    
    # 2. Generate TWB
    columns = get_column_metadata(df)
    twb_content = generate_twb(datasource_name, dimension, measure, columns)
    
    twb_path = work_dir / 'workbook.twb'
    print(f"Creating TWB: {twb_path}")
    with open(twb_path, 'w', encoding='utf-8') as f:
        f.write(twb_content)
    
    # 3. Package as TWBX
    print(f"Packaging TWBX: {output_path}")
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.write(twb_path, 'workbook.twb')
        zf.write(hyper_path, 'Data/Extract.hyper')
    
    print(f"Done! Created: {output_path}")
    
    # Cleanup
    os.remove(twb_path)
    os.remove(hyper_path)
    work_dir.rmdir()
    
    return output_path


if __name__ == '__main__':
    # Create sample data
    print("Creating sample Superstore data...")
    df = create_sample_data()
    print(df)
    print()
    
    # Generate TWBX with Category on rows, Sales on columns
    output_file = '/home/claude/superstore_bar_chart.twbx'
    generate_twbx(
        df=df,
        dimension='Category',
        measure='Sales',
        output_path=output_file
    )
