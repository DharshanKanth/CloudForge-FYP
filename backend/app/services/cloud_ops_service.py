"""Cloud-provider control operations that Terraform does not express.

Stop/start are *not* destroy operations — they call the provider API directly
(EC2 ``StopInstances`` / ``StartInstances``) using the project owner's connected
credentials. On invalid credentials or permissions the real API error is
returned; success is never faked.
"""
from typing import Dict, List

# Terraform resource types that support an in-place power operation.
POWER_CONTROLLABLE = {"aws_instance"}


def supports_power(resource_type: str) -> bool:
    return resource_type in POWER_CONTROLLABLE


def _client(env: Dict[str, str], region: str):
    import boto3  # imported lazily so startup/tests don't require AWS

    return boto3.client(
        "ec2",
        region_name=region or env.get("AWS_DEFAULT_REGION") or "us-east-1",
        aws_access_key_id=env.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=env.get("AWS_SECRET_ACCESS_KEY"),
        aws_session_token=env.get("AWS_SESSION_TOKEN"),
    )


def power(instance_ids: List[str], action: str, env: Dict[str, str], region: str = "") -> Dict:
    """Start or stop EC2 instances. Returns a structured result, never raises."""
    if action not in ("start", "stop"):
        return {"state": "failed", "message": f"Unsupported action: {action}"}
    if not instance_ids:
        return {"state": "failed", "message": "No instances specified"}

    try:
        client = _client(env, region)
        if action == "start":
            resp = client.start_instances(InstanceIds=instance_ids)
        else:
            resp = client.stop_instances(InstanceIds=instance_ids)
        changes = [
            {
                "instance_id": c.get("InstanceId"),
                "previous_state": (c.get("PreviousState") or {}).get("Name"),
                "current_state": (c.get("CurrentState") or {}).get("Name"),
            }
            for c in (resp.get("StartingInstances") or resp.get("StoppingInstances") or [])
        ]
        return {"state": "started" if action == "start" else "stopped", "changes": changes}
    except Exception as exc:  # noqa: BLE001 - surface the provider error verbatim
        return {"state": "failed", "message": str(exc)}
