from cs_caller.callout_mapper import CalloutMapper
from cs_caller.region_editor import build_rect_region, normalize_rect, rect_to_polygon


def test_normalize_rect_handles_reverse_drag() -> None:
    rect = normalize_rect(80, 70, 10, 20)
    assert rect.x1 == 10
    assert rect.y1 == 20
    assert rect.x2 == 80
    assert rect.y2 == 70


def test_rect_region_maps_points_correctly() -> None:
    region = build_rect_region("A Site", 10, 20, 110, 220)
    mapper = CalloutMapper([region])

    assert mapper.map_point((50.0, 50.0)) == "A Site"
    assert mapper.map_point((10.0, 20.0)) == "A Site"
    assert mapper.map_point((150.0, 50.0)) is None


def test_rect_to_polygon_clockwise() -> None:
    rect = normalize_rect(5, 8, 30, 40)
    polygon = rect_to_polygon(rect)
    assert polygon == [(5, 8), (30, 8), (30, 40), (5, 40)]
