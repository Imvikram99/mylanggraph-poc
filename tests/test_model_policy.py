from src.models.policy import ModelPolicy
from src.graph.nodes.router import RouterNode


def test_model_policy_advise_default():
    policy = ModelPolicy({"default": "balanced", "presets": {"balanced": {"preferred_route": "rag"}}})
    decision = policy.advise({})
    assert decision["preferred_route"] == "rag"


def test_router_respects_policy_boost(monkeypatch):
    policy_cfg = {
        "default": "cost_sensitive",
        "presets": {
            "cost_sensitive": {"preferred_route": "skills", "boost": 0.5},
        },
    }
    router = RouterNode({"defaults": {"router": {}}}, policy_config=policy_cfg)
    state = {
        "messages": [{"role": "user", "content": "Write a report"}],
        "context": {},
        "metadata": {},
    }
    router.run(state)
    assert state["route"] == "skills"
