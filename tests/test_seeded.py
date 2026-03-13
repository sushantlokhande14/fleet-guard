import collections

import pytest

from fleetguard import seeded
from fleetguard.builds import deep_merge


def test_catalog_shape():
    cats = collections.Counter(c.category for c in seeded.CASES)
    assert cats == {"perception_error": 10, "latency_spike": 10, "route_deviation": 10,
                    "control_instability": 10, "disengagement": 10}
    assert len(seeded.CONTROLS) == 10
    ids = [c.id for c in seeded.all_cases()]
    assert len(ids) == len(set(ids))
    assert seeded.get("latency_spike.spike_rate.severe").overrides == {"planner": {"spike_prob": 0.04}}
    with pytest.raises(KeyError):
        seeded.get("nope")


@pytest.mark.fgsim
def test_every_override_is_a_real_parameter(fgsim):
    # fgsim rejects unknown keys, so one short drive per case proves each override exists
    for case in seeded.all_cases():
        build = deep_merge({"name": case.id}, case.overrides)
        assert fgsim.run("s_curve", 1, build=build)["build"] == case.id
