from src.memory.checkpointer import TaggedSqliteSaver


class FakeSaver:
    def __init__(self):
        self.last_meta = None

    def put(self, config, checkpoint, metadata=None):
        self.last_meta = metadata
        return "ok"


def test_tagged_saver_adds_tags_and_diff():
    saver = TaggedSqliteSaver(FakeSaver())
    config = {"metadata": {"scenario_id": "demo", "user_id": "user-1"}}
    checkpoint = {"state": {"messages": [1, 2], "context": {"foo": "bar"}}}
    saver.put(config, checkpoint, metadata={})
    assert "scenario:demo" in saver.inner.last_meta["tags"]
    assert "user:user-1" in saver.inner.last_meta["tags"]
    assert "context" in saver.inner.last_meta["state_diff"]
