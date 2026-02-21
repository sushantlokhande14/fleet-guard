import pytest

from fleetguard.sim import Fgsim, FgsimError


@pytest.fixture(scope="session")
def fgsim() -> Fgsim:
    try:
        return Fgsim()
    except FgsimError:
        pytest.skip("fgsim binary not available")
