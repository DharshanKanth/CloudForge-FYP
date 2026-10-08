"""Project deployment lifecycle state machine.

The nine states below describe where a project is in the
design → validate → generate → plan → deploy → destroy pipeline. The live
infrastructure itself is still derived from Terraform state (see
deployment_service.infrastructure); this status is the pipeline position shown
in the UI.
"""

DRAFT = "draft"
VALIDATED = "validated"
GENERATED = "generated"
READY = "ready"
DEPLOYING = "deploying"
DEPLOYED = "deployed"
DESTROYING = "destroying"
DESTROYED = "destroyed"
FAILED = "failed"

ALL_STATES = [
    DRAFT, VALIDATED, GENERATED, READY,
    DEPLOYING, DEPLOYED, DESTROYING, DESTROYED, FAILED,
]

# Allowed forward/backward moves. A state may always "transition" to itself.
TRANSITIONS = {
    DRAFT: {VALIDATED, GENERATED, READY, DRAFT},
    VALIDATED: {GENERATED, READY, DRAFT, FAILED},
    GENERATED: {READY, VALIDATED, DRAFT, FAILED},
    READY: {DEPLOYING, DRAFT, VALIDATED, GENERATED, FAILED},
    DEPLOYING: {DEPLOYED, FAILED},
    DEPLOYED: {DESTROYING, READY, GENERATED, DRAFT},
    DESTROYING: {DESTROYED, FAILED},
    DESTROYED: {DRAFT, VALIDATED, GENERATED, READY},
    FAILED: {DRAFT, VALIDATED, GENERATED, READY, DEPLOYED, DESTROYED},
}

# States in which the design may be edited (not mid-deployment / deployed).
_DESIGN_EDITABLE = {DRAFT, VALIDATED, GENERATED, READY, DESTROYED, FAILED}


def can_transition(current: str, nxt: str) -> bool:
    if current == nxt:
        return True
    return nxt in TRANSITIONS.get(current, set())


def is_design_editable(current: str) -> bool:
    return current in _DESIGN_EDITABLE
