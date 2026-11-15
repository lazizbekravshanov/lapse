import json

import numpy as np
import pytest

from lapse.backend.actions import export
from lapse.backend.data import synthetic
from lapse.backend.operations import stats
from lapse.hub import registry, router


def ar1(rng, n, phi, cells):
    e = rng.standard_normal((n, cells))
    x = np.empty((n, cells))
    x[0] = e[0]
    for i in range(1, n):
        x[i] = phi * x[i - 1] + np.sqrt(1 - phi * phi) * e[i]
    return x


def test_every_method_has_the_same_interface_and_finds_a_planted_trend():
    rng = np.random.default_rng(0)
    t = np.arange(288) + 2002 * 12
    y = ar1(rng, 288, 0.5, 40) * 0.3 + 0.6 * np.arange(288)[:, None] / 120.0
    y[30:40, 0] = np.nan                                   # gaps
    y[:, 1] = np.nan                                       # a cell with no data
    for m in registry.METHODS.values():
        out = m.run(y, t, alpha=0.05, min_n=60)
        assert set(out) >= {"slope", "lo", "hi", "p", "r1", "n"}, m.id
        assert all(np.shape(out[k]) == (40,) for k in ("slope", "lo", "hi", "p")), m.id
        assert np.isnan(out["slope"][1]), m.id
        good = np.delete(np.arange(40), 1)
        assert np.all(np.abs(out["slope"][good] - 0.6) < 0.25), m.id
        assert np.all(out["lo"][good] <= out["hi"][good]), m.id
        assert np.mean(out["p"][good] < 0.05) > 0.9, m.id


def test_sound_methods_keep_false_alarms_low_and_textbook_does_not():
    """No trend, but strong month-to-month memory. The target false-alarm rate is 5%."""
    rng = np.random.default_rng(1)
    t = np.arange(288) + 2002 * 12
    null = ar1(rng, 288, 0.7, 600)
    rate = {m.id: float(np.mean(m.run(null[:, :200] if m.id == "robust" else null, t, alpha=0.05, min_n=60)["p"] < 0.05))
            for m in registry.METHODS.values()}
    for mid in registry.SOUND:
        assert rate[mid] < 0.11, (mid, rate)
    assert rate["textbook"] > 0.25, rate                  # why it does not count toward agreement


def test_registry_has_one_recommended_method_and_a_complete_catalog():
    assert [m.id for m in registry.METHODS.values() if m.recommended] == [registry.DEFAULT_METHOD]
    assert "textbook" not in registry.SOUND and len(registry.SOUND) == 3
    cat = registry.catalog()
    assert {m["id"] for m in cat["methods"]} == set(registry.METHODS)
    assert all(m["plain"] and m["science"] for m in cat["methods"])
    assert {c["id"] for c in cat["checks"]} == {"fdr", "witness", "volcano", "jump"}
    assert "{method}" in cat["routes"]["trend"]


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    root = tmp_path_factory.mktemp("hub")
    synthetic.generate(root / "zonal")
    for extra in ("merra2_qv.nc", "merra2_o3.nc"):
        (root / "zonal" / extra).unlink()
    export.run(root / "zonal", root / "web", verbose=False)
    return root / "web"


def test_router_fills_in_auto_choices(site):
    manifest, catalog = json.loads((site / "manifest.json").read_text()), json.loads((site / "catalog.json").read_text())
    res = router.resolve({"what": "Air temperature", "where": "arctic", "km": 32}, manifest, catalog)
    assert res["dataset"] == "airs"                         # satellite first
    assert res["method"] == "robust" and res["period"] == "full"
    assert res["chosen_by_auto"] == ["dataset", "method", "period"]
    assert res["place"] == {"region": "arctic"}
    levels = manifest["datasets"][1]["levels_hpa"]
    assert levels[res["level"]] == 10
    assert router.route(res, catalog) == "trend/airs/t/full__none__robust.json"

    res = router.resolve({"where": "-17", "dataset": "merra2", "method": "classic", "period": "airs_era"}, manifest, catalog)
    assert res["place"] == {"lat": 14} and res["chosen_by_auto"] == []
    assert router.route(res, catalog) == "trend/merra2/t/airs_era__none__classic.json"


def test_router_rejects_unknown_tools(site):
    manifest, catalog = json.loads((site / "manifest.json").read_text()), json.loads((site / "catalog.json").read_text())
    for bad in ({"method": "magic"}, {"what": "gold"}, {"where": "narnia"}, {"dataset": "airs", "what": "o3"}, {"period": "1066"}):
        with pytest.raises(ValueError):
            router.resolve(bad, manifest, catalog)


def test_router_answers_from_the_published_files(site):
    low = router.answer({"where": "global", "km": 5}, site)
    high = router.answer({"where": "global", "km": 45, "method": "yearly"}, site)
    assert low["rate"] > 0 > high["rate"]                   # the planted signal
    assert low["label"] in ("Clear change", "Likely change")
    assert low["methods_agree"] == "3 of 3"
    assert "very likely between" in low["sentence"]
    assert (site / high["route"]).exists() and high["request"]["method"] == "yearly"
    strongest = router.answer({"where": "tropics"}, site)   # no height: picks the strongest labelled change
    assert strongest["rate"] is not None
