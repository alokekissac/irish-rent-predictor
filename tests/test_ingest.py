from rentcast.data.ingest import jsonstat_to_frame


def test_jsonstat_flattens_in_row_major_order_and_drops_missing():
    payload = {
        "id": ["q", "loc"],
        "size": [2, 2],
        "dimension": {
            "q": {"label": "Quarter", "category": {"index": ["a", "b"], "label": {"a": "2024Q1", "b": "2024Q2"}}},
            "loc": {"label": "Location", "category": {"index": ["x", "y"], "label": {"x": "Cork", "y": "Sligo"}}},
        },
        "value": [1.0, None, 3.0, 4.0],
    }
    df = jsonstat_to_frame(payload)
    assert df.to_dict("records") == [
        {"Quarter": "2024Q1", "Location": "Cork", "value": 1.0},
        {"Quarter": "2024Q2", "Location": "Cork", "value": 3.0},
        {"Quarter": "2024Q2", "Location": "Sligo", "value": 4.0},
    ]
