from app.services import cloud_ops_service as ops


def test_supports_power():
    assert ops.supports_power("aws_instance")
    assert not ops.supports_power("aws_vpc")
    assert not ops.supports_power("aws_db_instance")


def test_power_rejects_bad_action_and_empty_ids():
    assert ops.power([], "start", {})["state"] == "failed"
    assert ops.power(["i-1"], "reboot", {})["state"] == "failed"


def test_power_stop_maps_provider_response(monkeypatch):
    class FakeClient:
        def stop_instances(self, InstanceIds):
            return {"StoppingInstances": [{
                "InstanceId": InstanceIds[0],
                "PreviousState": {"Name": "running"},
                "CurrentState": {"Name": "stopping"},
            }]}

    monkeypatch.setattr(ops, "_client", lambda env, region: FakeClient())
    result = ops.power(["i-123"], "stop", {}, "us-east-1")
    assert result["state"] == "stopped"
    assert result["changes"][0]["previous_state"] == "running"
    assert result["changes"][0]["current_state"] == "stopping"


def test_power_surfaces_provider_error(monkeypatch):
    def boom(env, region):
        raise RuntimeError("InvalidClientTokenId")

    monkeypatch.setattr(ops, "_client", boom)
    result = ops.power(["i-123"], "start", {}, "us-east-1")
    assert result["state"] == "failed"
    assert "InvalidClientTokenId" in result["message"]
