from lapse import config, fetch


def test_constraint_merra2():
    ds = config.DATASETS["merra2"]
    ce = fetch.constraint(ds, ds.variables[:1], 4)
    assert ce == "/T[0:1:0][0:1:41][0:4:360][0:4:575];/lat[0:4:360];/lev"


def test_constraint_airs_averages_day_and_night():
    ds = config.DATASETS["airs"]
    ce = fetch.constraint(ds, ds.variables, 2)
    assert "/ascending/Data_Fields/Temperature_A[0:1:23][0:2:179][0:2:359]" in ce
    assert "/descending/Data_Fields/Temperature_D[0:1:23][0:2:179][0:2:359]" in ce
    assert ce.endswith("/location/Data_Fields/Latitude[0:2:179][0:1:0]")


def test_parse_granule():
    item = {"umm": {
        "GranuleUR": "AIRS3STM.7.0:AIRS.2023.12.01.L3.RetStd_IR031.v7.0.9.3.G25290153000.hdf",
        "RelatedUrls": [
            {"Type": "GET DATA", "URL": "https://data.example/file.hdf"},
            {"Type": "USE SERVICE API", "Subtype": "OPENDAP DATA", "URL": "https://opendap.example/g"},
        ]}}
    assert fetch.parse_granule(config.DATASETS["airs"], item) == ("2023-12", "https://opendap.example/g")
    item["umm"]["GranuleUR"] = "M2IMNPASM.5.12.4:MERRA2_400.instM_3d_asm_Np.202401.nc4"
    assert fetch.parse_granule(config.DATASETS["merra2"], item)[0] == "2024-01"
    item["umm"]["RelatedUrls"] = []
    assert fetch.parse_granule(config.DATASETS["merra2"], item) is None


def test_token_problem_reads_expiry_without_network():
    import base64, json, time

    def make(exp):
        body = base64.urlsafe_b64encode(json.dumps({"uid": "someone", "exp": exp}).encode()).decode().rstrip("=")
        return f"aaa.{body}.zzz"

    assert fetch.token_problem(None)[0] is None
    assert "three parts" in fetch.token_problem("abc")[0]
    assert "expired" in fetch.token_problem(make(time.time() - 86400))[0]
    problem, text = fetch.token_problem(make(time.time() + 86400))
    assert problem is None and "someone" in text
