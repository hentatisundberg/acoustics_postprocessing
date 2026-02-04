import geopandas as gpd
import matplotlib.pyplot as plt

# 1. Load the coastline GeoJSON (EPSG:4326)
coastline = gpd.read_file('./data/geodata/CNTR_RG_03M_2024_4326.geojson')
print("Coastline CRS:", coastline.crs)

# 2. Crop to bounding box: E12-20, N55-62
minx, maxx = 12, 20  # Longitude
miny, maxy = 55, 62  # Latitude
coastline_cropped = coastline.cx[minx:maxx, miny:maxy]
print(f"Cropped coastline: {len(coastline_cropped)} features")

# 3. Reproject to SWEREF99 TM (EPSG:3006)
coastline_sweref = coastline_cropped.to_crs(epsg=3006)
print("Reprojected CRS:", coastline_sweref.crs)

# 4. Plot the cropped and reprojected coastline
fig, ax = plt.subplots(figsize=(8, 8))
coastline_sweref.plot(ax=ax, color='lightblue', edgecolor='black')
ax.set_title('SWEREF99 TM (EPSG:3006) - Cropped Coastline')
ax.set_xlabel('Easting (m)')
ax.set_ylabel('Northing (m)')
plt.show()