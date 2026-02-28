from cs_caller.callout_mapper import CalloutMapper, Region, point_in_polygon


def test_point_in_polygon_inside_and_outside() -> None:
    polygon = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    assert point_in_polygon((5.0, 5.0), polygon) is True
    assert point_in_polygon((11.0, 5.0), polygon) is False


def test_callout_mapper_maps_expected_region() -> None:
    mapper = CalloutMapper(
        [
            Region("A Site", [(0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0)]),
            Region("B Site", [(5.0, 5.0), (9.0, 5.0), (9.0, 9.0), (5.0, 9.0)]),
        ]
    )
    assert mapper.map_point((2.0, 2.0)) == "A Site"
    assert mapper.map_point((7.0, 7.0)) == "B Site"
    assert mapper.map_point((20.0, 20.0)) is None
