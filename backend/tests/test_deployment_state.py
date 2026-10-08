from app.services import deployment_state as st


def test_all_states_present():
    assert set(st.ALL_STATES) == {
        "draft", "validated", "generated", "ready", "deploying",
        "deployed", "destroying", "destroyed", "failed",
    }


def test_happy_path_transitions():
    assert st.can_transition(st.DRAFT, st.VALIDATED)
    assert st.can_transition(st.VALIDATED, st.GENERATED)
    assert st.can_transition(st.GENERATED, st.READY)
    assert st.can_transition(st.READY, st.DEPLOYING)
    assert st.can_transition(st.DEPLOYING, st.DEPLOYED)
    assert st.can_transition(st.DEPLOYED, st.DESTROYING)
    assert st.can_transition(st.DESTROYING, st.DESTROYED)


def test_deploying_cannot_jump_to_destroyed():
    assert not st.can_transition(st.DEPLOYING, st.DESTROYED)
    assert not st.can_transition(st.DRAFT, st.DEPLOYED)


def test_self_transition_always_allowed():
    for state in st.ALL_STATES:
        assert st.can_transition(state, state)


def test_design_editable_only_when_not_deploying():
    assert st.is_design_editable(st.DRAFT)
    assert st.is_design_editable(st.READY)
    assert not st.is_design_editable(st.DEPLOYING)
    assert not st.is_design_editable(st.DEPLOYED)
    assert not st.is_design_editable(st.DESTROYING)
