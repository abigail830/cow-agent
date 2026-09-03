from app.platform.hook_config import normalize_hooks


def test_hooks_map_with_params():
    hooks = normalize_hooks(
        {
            "sql_validator": {"max_rows": 100},
            "result_truncator": {"max_observation_bytes": 1000},
        }
    )
    assert hooks == [
        ("sql_validator", {"max_rows": 100}),
        ("result_truncator", {"max_observation_bytes": 1000}),
    ]


def test_hooks_map_empty_uses_defaults():
    hooks = normalize_hooks({"sql_validator": {}})
    assert hooks[0][0] == "sql_validator"
    assert hooks[0][1]["max_rows"] == 2000


def test_sql_viz_hook_defaults():
    hooks = normalize_hooks({"sql_viz": {}})
    assert hooks[0] == ("sql_viz", {"auto": False, "min_rows": 3})


def test_hooks_list():
    hooks = normalize_hooks(["sql_validator", "result_truncator"])
    assert [h[0] for h in hooks] == ["sql_validator", "result_truncator"]
    assert hooks[0][1]["max_rows"] == 2000


def test_legacy_custom_and_guardrails():
    hooks = normalize_hooks(
        {"custom": ["sql_validator", "result_truncator"]},
        legacy_guardrails={"sql": {"max_rows": 500, "max_observation_bytes": 999}},
    )
    assert hooks[0] == ("sql_validator", {"max_rows": 500})
    assert hooks[1] == ("result_truncator", {"max_observation_bytes": 999})
