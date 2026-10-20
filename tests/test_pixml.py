import pandas as pd

from fews_mike_adapter.pixml_to_dfs0 import read_pixml
from fews_mike_adapter.utils import add_xml_series, new_pi_timeseries_root, write_pi_xml


def test_roundtrip_pixml(tmp_path):
    index = pd.date_range("2026-10-20", periods=3, freq="h")
    df = pd.DataFrame({"1:Node_A": [1.0, None, 3.0], "Node_B": [4.0, 5.0, 6.0]}, index=index)

    root = new_pi_timeseries_root()
    add_xml_series(root, df, parameter_id="H.sim", units="m")
    out = tmp_path / "out.xml"
    write_pi_xml(root, str(out))

    groups = read_pixml(str(out))
    assert list(groups) == ["H.sim"]
    result = groups["H.sim"]
    assert list(result.columns) == ["Node_A", "Node_B"]   # "1:" prefix stripped
    assert result["Node_A"].iloc[1] == -99.0              # missing written as missVal
    assert result["Node_B"].tolist() == [4.0, 5.0, 6.0]
    assert 'flag="8"' in out.read_text()


def test_settings_paths_relative_to_ini(tmp_path):
    from fews_mike_adapter.config import read_settings, resolve_path

    ini = tmp_path / "settings.ini"
    ini.write_text("[pixml_to_dfs0]\npixml_file = Assam/forcing.xml\n")
    cfg = read_settings(str(ini))
    assert resolve_path(cfg, cfg["pixml_to_dfs0"]["pixml_file"]) == str(tmp_path / "Assam/forcing.xml")


def test_cli_default_settings():
    from fews_mike_adapter.cli import build_parser

    args = build_parser().parse_args(["--forecast"])
    assert args.settings == "settings.ini" and args.forecast
