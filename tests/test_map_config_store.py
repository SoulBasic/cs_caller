from pathlib import Path

from cs_caller.callout_mapper import Region
from cs_caller.map_config_store import MapConfig, MapConfigStore


def test_store_save_and_load_roundtrip(tmp_path: Path) -> None:
    store = MapConfigStore(tmp_path)
    config = MapConfig(
        map_name="de_inferno",
        regions=[
            Region(
                name="Banana",
                polygon=[(10.0, 20.0), (50.0, 20.0), (50.0, 80.0), (10.0, 80.0)],
            )
        ],
    )

    save_path = store.save(config)
    assert save_path.exists()

    loaded = store.load("de_inferno")
    assert loaded.map_name == "de_inferno"
    assert len(loaded.regions) == 1
    assert loaded.regions[0].name == "Banana"
    assert loaded.regions[0].polygon == [
        (10.0, 20.0),
        (50.0, 20.0),
        (50.0, 80.0),
        (10.0, 80.0),
    ]


def test_store_list_map_names_sorted(tmp_path: Path) -> None:
    store = MapConfigStore(tmp_path)
    store.save(MapConfig(map_name="de_nuke", regions=[]))
    store.save(MapConfig(map_name="de_anubis", regions=[]))

    assert store.list_map_names() == ["de_anubis", "de_nuke"]
