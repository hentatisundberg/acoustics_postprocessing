
# Workflow for Finngrundet pre-analysis, February 2025

# Load data 
load dir=./data/data pattern=SLUAquaSailor* positions=./positions/positions.txt

# Add year etc. to dataset
create year from timestamp        # Extract year
create hour from timestamp        # Extract hour (0-23)
create dayofyear from timestamp   # Extract day of month (1-31)
create month from timestamp       # Extract month (1-12)
create week from timestamp       # Extract month (1-12)

# Calculate abundance from NASC
calc abund_km2=(nasc0/sigma_mean)/(conv_nmi2_km2) 
calc tonnes_km2=abund_km2*weight_lengthA*mean_length**weight_lengthB/(1000*1000)


# Plots for checking cut offs for outliers etc. 

# Modified Z-score of 10 for tonnes_km2 appears reasonable, retains low value while cutting some extremes 
# A weak positive effect of time of the year 
scatter tonnes_km2 vs dayofyear 30min outliers=modified_zscore z_thresh=10   


# Clear effect of day and night
boxplot tonnes_km2 vs hour 30min outliers=modified_zscore z_thresh=10   

# Similar values for 2024 and 2025
boxplot tonnes_km2 vs year 30min logy=true outliers=modified_zscore z_thresh=10   

# Clear positive effect of depth
scatter tonnes_km2 vs depth 30min outliers=modified_zscore z_thresh=10   

# No effect of Northing
scatter tonnes_km2 vs northing 30min outliers=modified_zscore z_thresh=10   

# No effect of Easting
scatter tonnes_km2 vs easting 30min outliers=modified_zscore z_thresh=10   

# Map of abundance estimates


# Summarize by 30 min and export
stats columns=tonnes_km2,nasc0 30min outliers=modified_zscore z_thresh=10



