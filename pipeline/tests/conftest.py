import pytest

from lapse.backend.actions import export
from lapse.backend.data import synthetic


@pytest.fixture(scope="session")
def site(tmp_path_factory):
    """A small published site built from synthetic cubes: temperature only, both datasets."""
    root = tmp_path_factory.mktemp("site")
    synthetic.generate(root / "zonal")
    for extra in ("merra2_qv.nc", "merra2_o3.nc"):
        (root / "zonal" / extra).unlink()
    export.run(root / "zonal", root / "web", verbose=False)
    return root / "web"
