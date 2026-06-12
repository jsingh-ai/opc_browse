from opc_browse.services.tag_tree import build_tag_tree, split_opc_path


def test_split_opc_path_ignores_empty_segments():
    assert split_opc_path("Area1//LineA / Pump01 / Speed") == [
        "Area1",
        "LineA",
        "Pump01",
        "Speed",
    ]


def test_build_tag_tree_builds_nested_branches():
    rows = [
        {
            "tag_id": 1,
            "opc_path": "Area1/LineA/Speed",
            "display_name": "Speed",
            "browse_name": "Speed",
            "data_type": "Double",
            "parent_branch": "LineA",
            "last_seen_utc": None,
            "sample_count": 5,
            "is_numeric": True,
        },
        {
            "tag_id": 2,
            "opc_path": "Area1/LineA/Temp",
            "display_name": "Temp",
            "browse_name": "Temp",
            "data_type": "Double",
            "parent_branch": "LineA",
            "last_seen_utc": None,
            "sample_count": 7,
            "is_numeric": True,
        },
        {
            "tag_id": 3,
            "opc_path": "Area1/LineB/State",
            "display_name": "State",
            "browse_name": "State",
            "data_type": "String",
            "parent_branch": "LineB",
            "last_seen_utc": None,
            "sample_count": 2,
            "is_numeric": False,
        },
    ]

    tree = build_tag_tree(rows)

    assert tree["name"] == "root"
    assert len(tree["children"]) == 1
    area = tree["children"][0]
    assert area["name"] == "Area1"
    assert [child["name"] for child in area["children"]] == ["LineA", "LineB"]
    line_a = area["children"][0]
    assert [tag["tag_id"] for tag in line_a["tags"]] == [1, 2]


def test_build_tag_tree_handles_root_tags():
    rows = [
        {
            "tag_id": 10,
            "opc_path": "StandaloneTag",
            "display_name": "StandaloneTag",
            "browse_name": "StandaloneTag",
            "data_type": "Int32",
            "parent_branch": None,
            "last_seen_utc": None,
            "sample_count": 1,
            "is_numeric": True,
        }
    ]

    tree = build_tag_tree(rows)

    assert tree["children"] == []
    assert tree["tags"][0]["tag_id"] == 10
