from app.seed import _demo_graph, should_seed
from app.services.validation_service import validate_architecture


def test_demo_graph_is_valid():
    nodes, edges = _demo_graph()
    assert len(nodes) >= 8
    res = validate_architecture(nodes, edges)
    errors = [i.message for i in res.issues if i.level == "error"]
    assert res.valid, errors


def test_should_seed_respects_env(monkeypatch):
    monkeypatch.delenv("CLOUDFORGE_SEED_DEMO", raising=False)
    monkeypatch.setenv("CLOUDFORGE_ENV", "production")
    assert should_seed() is False

    monkeypatch.setenv("CLOUDFORGE_SEED_DEMO", "true")
    assert should_seed() is True

    monkeypatch.setenv("CLOUDFORGE_SEED_DEMO", "false")
    monkeypatch.setenv("CLOUDFORGE_ENV", "development")
    assert should_seed() is False

    monkeypatch.delenv("CLOUDFORGE_SEED_DEMO", raising=False)
    monkeypatch.setenv("CLOUDFORGE_ENV", "development")
    assert should_seed() is True
