from runtime.nexo_agent_api.gpt_writer import producer_of, split_by_producer


def test_unlabelled_items_always_apply():
    items = [{"kind": "ROADMAP_CHARTER", "_inbox_name": "conv-1"}, {"kind": "BATTERY_STATUS", "_inbox_source": "WRITER_ROBOT"}]
    keep, shadow = split_by_producer(items, "CLAUDE")
    assert keep == items and shadow == []


def test_only_active_producer_applies():
    gpt = {"producer": "gpt", "kind": "CONTEST"}
    claude = {"producer": "CLAUDE", "kind": "CONTEST"}
    sched = {"kind": "NEXO_THOUGHT", "_inbox_name": "scheduled-pitia-nexo-thought-1"}
    keep, shadow = split_by_producer([gpt, claude, sched], "GPT")
    assert keep == [gpt, sched] and shadow == [claude]
    keep, shadow = split_by_producer([gpt, claude, sched], "CLAUDE")
    assert keep == [claude] and shadow == [gpt, sched]


def test_unknown_active_defaults_to_gpt():
    assert producer_of({"_inbox_name": "scheduled-x"}) == "GPT"
    keep, _ = split_by_producer([{"producer": "GPT"}], "bogus")
    assert keep == [{"producer": "GPT"}]


def test_battery_is_recipe_only():
    import inspect
    from runtime.nexo_agent_api import evolution
    src = inspect.getsource(evolution.battery_requests)
    assert "recipe" in src and 'spec.get("script")' in src  # inline code is refused
