import argparse
import geopandas as gpd
import os
from pathlib import Path

os.environ["OGR_GEOJSON_MAX_OBJ_SIZE"] = "0"

parser = argparse.ArgumentParser(description="Simplify GeoJSON geometry.")
parser.add_argument(
	"--input",
	default="static/geojson/csd_enriched.geojson",
	help="Input GeoJSON path",
)
parser.add_argument(
	"--output",
	default=None,
	help="Output GeoJSON path (defaults to overwrite input)",
)
parser.add_argument(
	"--tolerance",
	type=float,
	default=500.0,
	help="Simplification tolerance in EPSG:3347 units (meters)",
)
args = parser.parse_args()

input_path = Path(args.input)
output_path = Path(args.output) if args.output else input_path

print("Reading...")
gdf = gpd.read_file(input_path)
print(f"  Original: {input_path.stat().st_size / 1e6:.0f} MB, {len(gdf)} features")

print("Simplifying...")
gdf["geometry"] = (
	gdf.geometry.to_crs("EPSG:3347")
	.simplify(tolerance=args.tolerance)
	.to_crs("EPSG:4326")
)

print("Writing...")
gdf.to_file(output_path, driver="GeoJSON")
print(f"  Final: {output_path.stat().st_size / 1e6:.0f} MB")