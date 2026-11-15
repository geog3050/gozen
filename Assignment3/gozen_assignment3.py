"""Assignment 3: Spatial Overlays and Areal Interpolation.
Complete three functions using ArcPy and pathlib.Path. Prepare and project
copies before analysis; preserve inputs and avoid hardcoded paths or values.
Check input paths, geometry types, fields, coordinate systems, and output names.
Use try/except handling to catch and report errors.
Find and download census boundaries, a census/ACS numeric attribute, and roads (or another dataset with line geometry).
"""

import arcpy
from pathlib import Path
import csv
import math
import uuid

arcpy.env.workspace = r"C:\Users\Gulsen Ozen\Assignment3\data"


def hawkid():
    return(["Gulsen Ozen", "gozen"])

print(hawkid())



data_folder = Path(r"C:\Users\Gulsen Ozen\Assignment3\data")

files = [
    "block_groups.shp",
    "practice_zone.shp",
    "practice_lines.shp",
    "practice_polygons.shp"
]

for filename in files:

    fc = data_folder / filename

    print("\n----------------------------")
    print("File:", filename)

    if arcpy.Exists(str(fc)):

        desc = arcpy.Describe(str(fc))

        print("Geometry:", desc.shapeType)
        print("Coordinate System:", desc.spatialReference.name)
        print("Units:", desc.spatialReference.linearUnitName)

        print("Fields:")

        for field in arcpy.ListFields(str(fc)):
            print("  ", field.name, "-", field.type)

    else:
        print("File not found!")



# Problem 1 (20 points)
def prepare_data(input_fc, output_geodatabase, out_coordinate_system,
                 join_table=None, join_field=None, value_field=None):
    """Create or reuse the geodatabase; import and project one feature dataset.
    Use the input base name and return the prepared feature class path.
    For polygons, import a CSV's ID attribute and one numeric value
    and join that value using the join_field. Supply all three join
    arguments together. Preserve inputs and reject existing output names.
    """

    try:
        # Check that the input feature class exists
        input_fc = str(input_fc)

        if not arcpy.Exists(input_fc):
            raise FileNotFoundError(f"Input file not found: {input_fc}")

        desc = arcpy.Describe(input_fc)

        # Check geometry type
        if desc.shapeType not in ["Point", "Polyline", "Polygon"]:
            raise ValueError("Input must contain point, line, or polygon geometry.")

        # Check input coordinate system
        if desc.spatialReference.name == "Unknown":
            raise ValueError("Input has an unknown coordinate system.")

        # Validate output coordinate system
        if isinstance(out_coordinate_system, arcpy.SpatialReference):
            output_sr = out_coordinate_system
        elif isinstance(out_coordinate_system, int):
            output_sr = arcpy.SpatialReference(out_coordinate_system)
        else:
            output_sr = arcpy.SpatialReference(str(out_coordinate_system))

        if output_sr.name == "Unknown":
            raise ValueError("Invalid output coordinate system.")

        if output_sr.type != "Projected":
            raise ValueError("Output coordinate system must be projected.")

        if not math.isclose(output_sr.metersPerUnit, 1.0, rel_tol=1e-9):
            raise ValueError("Output coordinate system must use meters.")

        # Check optional CSV join arguments
        join_args = [join_table, join_field, value_field]

        if any(arg is not None for arg in join_args):
            if not all(arg is not None for arg in join_args):
                raise ValueError("join_table, join_field, and value_field must all be provided.")

            if desc.shapeType != "Polygon":
                raise ValueError("CSV joins are only allowed for polygons.")

        # Create or reuse output geodatabase
        output_geodatabase = Path(output_geodatabase)

        if output_geodatabase.suffix.lower() != ".gdb":
            raise ValueError("Output geodatabase must end with .gdb")

        if not output_geodatabase.parent.is_dir():
            raise FileNotFoundError("Output folder does not exist.")

        if not arcpy.Exists(str(output_geodatabase)):
            arcpy.management.CreateFileGDB(str(output_geodatabase.parent), output_geodatabase.name)

        # Create output name using input base name
        output_name = arcpy.ValidateTableName(desc.baseName, str(output_geodatabase))

        output_fc = str(output_geodatabase / output_name)

        if arcpy.Exists(output_fc):
            raise FileExistsError(f"Output already exists: {output_fc}")

        # Validate CSV and read numeric values
        csv_values = None

        if all(arg is not None for arg in join_args):

            # Check join field in polygon dataset
            input_fields = {
                field.name.lower(): field.name
                for field in arcpy.ListFields(input_fc)
            }

            if join_field.lower() not in input_fields:
                raise ValueError(f"Join field '{join_field}' not found in input polygons.")
            join_field_name = input_fields[join_field.lower()]

            csv_file = Path(join_table)

            if not csv_file.is_file():
                raise FileNotFoundError(f"CSV file not found: {csv_file}")

            csv_values = {}

            with csv_file.open("r", encoding="utf-8-sig", newline="") as file:
                reader = csv.DictReader(file)

                if reader.fieldnames is None:
                    raise ValueError("CSV file has no column headers.")

                csv_fields = {
                    name.lower(): name
                    for name in reader.fieldnames
                }

                if join_field.lower() not in csv_fields:
                    raise ValueError(f"Join field '{join_field}' not found in CSV.")

                if value_field.lower() not in csv_fields:
                    raise ValueError(f"Value field '{value_field}' not found in CSV.")

                csv_id = csv_fields[join_field.lower()]
                csv_value = csv_fields[value_field.lower()]

                for row in reader:
                    identifier = row[csv_id]

                    if identifier is None or not identifier.strip():
                        continue

                    identifier = identifier.strip()

                    if identifier in csv_values:
                        raise ValueError(f"Duplicate join identifier in CSV: {identifier}")

                    value = row[csv_value]

                    if value is None or not value.strip():
                        numeric_value = None
                    else:
                        numeric_value = float(value.replace(",", "").strip())

                        if not math.isfinite(numeric_value):
                            raise ValueError("CSV contains an invalid numeric value.")

                    csv_values[identifier] = numeric_value

        # Project input into the geodatabase
        arcpy.management.Project(input_fc, output_fc, output_sr)

        # Step 10: Join population values for polygon data
        if csv_values is not None:

            output_fields = {
                field.name.lower(): field.name
                for field in arcpy.ListFields(output_fc)
            }

            output_join_field = output_fields[join_field.lower()]

            new_field = arcpy.ValidateFieldName(value_field,str(output_geodatabase))

            if new_field.lower() in output_fields:
                raise ValueError(f"Output field '{new_field}' already exists.")

            arcpy.management.AddField(output_fc, new_field, "DOUBLE")

            with arcpy.da.UpdateCursor(output_fc,[output_join_field, new_field]) as cursor:
                for row in cursor:
                    identifier = row[0]

                    if identifier is None:
                        row[1] = None
                    else:
                        row[1] = csv_values.get(str(identifier).strip())

                    cursor.updateRow(row)

            print(f"Joined CSV field: {new_field}")

        print("Problem 1 completed successfully!")
        print("Output feature class:", output_fc)

        return output_fc

    except Exception as error:
        print("Error in prepare_data:", error)

        if isinstance(error, arcpy.ExecuteError):
            print(arcpy.GetMessages(2))

        raise


# Problem 2 (40 points)
def estimatePopulationInZone(source_polygons, population_field, study_zone,
                             output_fc):
    """Similar to the week 10 and 11 notebook exercises, you overlay a buffer with source_polygons
    such as census units, and calculate the proportion of a source polygon that overlaps
    with the buffer (the study zone) using areal interpolation.
    Combine the study zone, intersect, calculate area-weighted population,
    and total the estimates. Save SRC_KM2, PART_KM2, and EST_POP; return the total.
    Inputs must share a projected CRS in meters.
    """

    # Checking input and output paths
    source_polygons = str(source_polygons)
    study_zone = str(study_zone)
    output_fc = str(output_fc)

    if not arcpy.Exists(source_polygons) or not arcpy.Exists(study_zone):
        raise FileNotFoundError("One or more input datasets do not exist.")

    if arcpy.Exists(output_fc):
        raise FileExistsError("Output feature class already exists.")

    workspace = str(Path(output_fc).parent)
    if not arcpy.Exists(workspace):
        raise FileNotFoundError("Output workspace does not exist.")

    # Checking geometry types
    source_desc = arcpy.Describe(source_polygons)
    zone_desc = arcpy.Describe(study_zone)

    if source_desc.shapeType != "Polygon" or zone_desc.shapeType != "Polygon":
        raise ValueError("Both inputs must be polygons.")

    # Checking coordinate systems
    sr1 = source_desc.spatialReference
    sr2 = zone_desc.spatialReference

    if sr1.type != "Projected" or sr2.type != "Projected":
        raise ValueError("Both inputs must use projected coordinate systems.")

    if not math.isclose(sr1.metersPerUnit, 1.0) or not math.isclose(sr2.metersPerUnit, 1.0):
        raise ValueError("Coordinate systems must use meters.")

    if sr1.exportToString() != sr2.exportToString():
        raise ValueError("Both inputs must use the same coordinate system.")

    # Checking population field
    fields = {f.name.lower(): f for f in arcpy.ListFields(source_polygons)}

    if population_field.lower() not in fields:
        raise ValueError(f"Population field '{population_field}' not found.")

    pop_field = fields[population_field.lower()]

    if pop_field.type not in ["SmallInteger", "Integer", "BigInteger", "Single", "Double"]:
        raise ValueError("Population field must be numeric.")

    for name in ["SRC_KM2", "PART_KM2", "EST_POP"]:
        if name.lower() in fields:
            raise ValueError(f"Field '{name}' already exists in source polygons.")

    # Creating temporary datasets
    source_copy = str(Path(workspace) / f"temp_source_{uuid.uuid4().hex[:8]}")
    zone_copy = str(Path(workspace) / f"temp_zone_{uuid.uuid4().hex[:8]}")

    arcpy.management.CopyFeatures(source_polygons, source_copy)
    arcpy.management.Dissolve(study_zone, zone_copy)

    # Calculating source polygon area
    arcpy.management.AddField(source_copy, "SRC_KM2", "DOUBLE")

    with arcpy.da.UpdateCursor(source_copy, ["SHAPE@", "SRC_KM2"]) as cursor:
        for row in cursor:
            row[1] = row[0].area / 1000000.0 if row[0] else 0.0
            cursor.updateRow(row)

    # Intersecting source polygons with study zone
    arcpy.analysis.Intersect([source_copy, zone_copy], output_fc, "ALL", None, "INPUT")

    # Adding area and population fields
    arcpy.management.AddField(output_fc, "PART_KM2", "DOUBLE")
    arcpy.management.AddField(output_fc, "EST_POP", "DOUBLE")

    # Calculating area-weighted population
    total_population = 0.0

    with arcpy.da.UpdateCursor(output_fc, ["SHAPE@", "SRC_KM2", "PART_KM2", "EST_POP", pop_field.name]) as cursor:
        for row in cursor:
            source_area = row[1]
            part_area = row[0].area / 1000000.0 if row[0] else 0.0
            population = row[4]

            if source_area is not None and source_area > 0 and population is not None:
                estimated_pop = float(population) * (part_area / source_area)
            else:
                estimated_pop = 0.0

            row[2] = part_area
            row[3] = estimated_pop
            total_population += estimated_pop
            cursor.updateRow(row)

    # Deleting temporary datasets
    arcpy.management.Delete(source_copy)
    arcpy.management.Delete(zone_copy)

    print("Problem 2 completed")
    print(f"Total estimated population: {total_population:,.2f}")
    print(f"Output saved to: {output_fc}")

    return total_population


# Problem 3 (40 points)
def summarizeLineLength(lines, polygons, polygon_id_field, output_fc):
    """Compute the total length of lines that intersect a polygon.
    Intersect, measure lengths, summarize by polygon ID, and join totals back.
    Save all polygons with LINE_KM (zero if no lines); return output_fc.
    Use a shared projected CRS in meters.
    """

    # Check input and output paths
    lines = str(lines)
    polygons = str(polygons)
    output_fc = str(output_fc)

    if not arcpy.Exists(lines) or not arcpy.Exists(polygons):
        raise FileNotFoundError("One or more input datasets do not exist.")

    if arcpy.Exists(output_fc):
        raise FileExistsError("Output already exists.")

    workspace = str(Path(output_fc).parent)
    if not arcpy.Exists(workspace):
        raise FileNotFoundError("Output workspace does not exist.")

    # Check geometry types
    line_desc = arcpy.Describe(lines)
    polygon_desc = arcpy.Describe(polygons)

    if line_desc.shapeType != "Polyline":
        raise ValueError("Lines must contain polyline geometry.")

    if polygon_desc.shapeType != "Polygon":
        raise ValueError("Polygons must contain polygon geometry.")

    # Check coordinate systems
    sr1 = line_desc.spatialReference
    sr2 = polygon_desc.spatialReference

    if sr1.type != "Projected" or sr2.type != "Projected":
        raise ValueError("Both inputs must use projected coordinate systems.")

    if not math.isclose(sr1.metersPerUnit, 1.0) or not math.isclose(sr2.metersPerUnit, 1.0):
        raise ValueError("Both coordinate systems must use meters.")

    if sr1.exportToString() != sr2.exportToString():
        raise ValueError("Both inputs must use the same coordinate system.")

    # Check polygon ID field
    fields = {f.name.lower(): f for f in arcpy.ListFields(polygons)}

    if polygon_id_field.lower() not in fields:
        raise ValueError(f"Polygon ID field '{polygon_id_field}' not found.")

    id_field = fields[polygon_id_field.lower()].name

    if "line_km" in fields:
        raise ValueError("LINE_KM already exists.")

    # Check that polygon IDs are unique
    polygon_ids = set()

    with arcpy.da.SearchCursor(polygons, [id_field]) as cursor:
        for row in cursor:
            polygon_id = row[0]

            if polygon_id is None or polygon_id == "":
                raise ValueError("Polygon ID contains null or empty values.")

            if polygon_id in polygon_ids:
                raise ValueError("Polygon IDs must be unique.")

            polygon_ids.add(polygon_id)

    # Create a temporary polygon copy
    polygon_copy = str(Path(workspace) / f"temp_poly_{uuid.uuid4().hex[:8]}")
    arcpy.management.CopyFeatures(polygons, polygon_copy)

    # Add temporary ID to avoid field-name conflicts
    temp_id = "TMP_POLY_ID"
    existing = {f.name.upper() for f in arcpy.ListFields(polygon_copy)}

    while temp_id.upper() in existing:
        temp_id = f"TP_{uuid.uuid4().hex[:8]}"

    arcpy.management.AddField(polygon_copy, temp_id, "LONG")

    id_lookup = {}

    with arcpy.da.UpdateCursor(polygon_copy, [id_field, temp_id]) as cursor:
        for number, row in enumerate(cursor, start=1):
            row[1] = number
            id_lookup[number] = row[0]
            cursor.updateRow(row)

    # Intersect lines and polygons
    intersect_fc = str(Path(workspace) / f"temp_intersect_{uuid.uuid4().hex[:8]}")
    arcpy.analysis.Intersect([polygon_copy, lines], intersect_fc, "ALL", None, "LINE")

    # Calculate line lengths in kilometers
    arcpy.management.AddField(intersect_fc, "SEG_KM", "DOUBLE")

    with arcpy.da.UpdateCursor(intersect_fc, ["SHAPE@", "SEG_KM"]) as cursor:
        for row in cursor:
            row[1] = row[0].length / 1000.0 if row[0] else 0.0
            cursor.updateRow(row)

    # Summarize line lengths by polygon ID
    summary_table = str(Path(workspace) / f"temp_summary_{uuid.uuid4().hex[:8]}")
    arcpy.analysis.Statistics(intersect_fc, summary_table, [["SEG_KM", "SUM"]], temp_id)

    # Store summarized lengths
    length_totals = {}

    with arcpy.da.SearchCursor(summary_table, [temp_id, "SUM_SEG_KM"]) as cursor:
        for row in cursor:
            original_id = id_lookup[row[0]]
            length_totals[original_id] = float(row[1]) if row[1] is not None else 0.0

    # Copy all polygons to output
    arcpy.management.CopyFeatures(polygons, output_fc)
    arcpy.management.AddField(output_fc, "LINE_KM", "DOUBLE")

    # Join total lengths to polygons
    with arcpy.da.UpdateCursor(output_fc, [id_field, "LINE_KM"]) as cursor:
        for row in cursor:
            row[1] = length_totals.get(row[0], 0.0)
            cursor.updateRow(row)

    # Delete temporary datasets
    arcpy.management.Delete(polygon_copy)
    arcpy.management.Delete(intersect_fc)
    arcpy.management.Delete(summary_table)

    print("Problem 3 completed successfully!")
    print("Output saved to:", output_fc)

    return output_fc


######################################################################
# MAKE NO CHANGES BEYOND THIS POINT.
######################################################################
if __name__ == "__main__" and hawkid()[1] == "hawkid":
    print("### Error: YOU MUST provide your HawkID in the hawkid() function.")



