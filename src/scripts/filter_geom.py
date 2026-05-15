import geopandas as gpd
import pandas as pd
import os
from pathlib import Path

os.environ["OGR_GEOJSON_MAX_OBJ_SIZE"] = "0"

project_root = Path(__file__).parent.parent.parent


def build_enriched_geojson(geo_type: str) -> None:
    """
    Merge 2016 and 2021 census data with geometry for a given geographic unit.

    Args:
        geo_type: Either "csd" or "cd"
    """
    geo_type = geo_type.lower()
    if geo_type not in ("csd", "cd"):
        raise ValueError(f"geo_type must be 'csd' or 'cd', got '{geo_type}'")

    uid_col = f"{geo_type.upper()}UID"  # e.g. CSDUID or CDUID

    # --- Load geometry ---
    geom_path = project_root / "static" / "geojson" / f"{geo_type}_geom.geojson"
    geom = gpd.read_file(geom_path)
    geom[uid_col] = geom[uid_col].astype(str)

    # --- Load both census CSVs ---
    def load_census(year: int) -> pd.DataFrame:
        path = project_root / "static" / f"{geo_type}_vs_province_{year}.csv"
        df = pd.read_csv(path)
        df["GeoUID"] = df["GeoUID"].astype(str)
        # Suffix all non-join columns with the year
        df = df.rename(columns={
            col: f"{col}_{year}"
            for col in df.columns
            if col != "GeoUID"
        })
        return df

    data_2016 = load_census(2016)
    data_2021 = load_census(2021)

    # --- Merge both years onto geometry ---
    enriched = (
        geom
        .merge(data_2016, left_on=uid_col, right_on="GeoUID", how="inner")
        .drop(columns=["GeoUID"])
        .merge(data_2021, left_on=uid_col, right_on="GeoUID", how="inner")
        .drop(columns=["GeoUID"])
    )

    # --- Save ---
    output_path = project_root / "static" / "geojson" / f"{geo_type}_enriched.geojson"
    enriched.to_file(output_path, driver="GeoJSON")

    print(f"✓ Created {output_path}")
    print(f"  - {len(enriched)} {geo_type.upper()}s matched")
    print(f"  - {len(enriched.columns)} columns total")


if __name__ == "__main__":
    build_enriched_geojson("csd")
    build_enriched_geojson("cd")