# The data in this folder

`zonal/` holds four small files (about 11 MB together). They are the only data the
statistics need, so every number on the site can be recomputed from a fresh clone
with no NASA login:

    make verify

| File | NASA product | What it holds |
|---|---|---|
| `zonal/airs_t.nc` | AIRS3STM v7.0 (Aqua satellite, GES DISC) | Air temperature, 2002-09 to 2026-09, 24 heights |
| `zonal/merra2_t.nc` | M2IMNPASM v5.12.4 (MERRA-2, GES DISC) | Air temperature, 1980-01 to 2026-09, 42 heights |
| `zonal/merra2_qv.nc` | M2IMNPASM v5.12.4 | Water vapor (specific humidity), same months and heights |
| `zonal/merra2_o3.nc` | M2IMNPASM v5.12.4 | Ozone (mass mixing ratio), same months and heights |

Each file is one array, `value(time, level, lat)`: one value per month, per height
(pressure level in hPa) and per 5-degree band of latitude (36 bands).

## How they were made

`python -m lapse fetch airs` and `python -m lapse fetch merra2` (needs a free
Earthdata login). For each monthly file the code:

1. asks NASA's server for the needed variables only, at every 2nd grid point for
   AIRS and every 4th for MERRA-2;
2. for AIRS, averages the daytime and night-time passes in each grid cell, with
   equal weight;
3. averages around the Earth at each latitude, skipping missing values;
4. averages the latitudes inside each 5-degree band, weighted by cos(latitude).

Nothing else is done here. Removing the seasons, trends, tests and labels all
happen later, in `pipeline/lapse/backend`.

## Known gaps

- MERRA-2 June 1998 is missing (the download failed). It is stored as empty.
  `python -m lapse fetch merra2` fills it in; then run `python -m lapse export`.
- Near the ground, heights that lie below mountains have no data at some latitudes.

`cache/` (not in the repository) holds the per-month downloads that the cubes are
assembled from.

These are reduced copies of public NASA data. Please cite the original products.
