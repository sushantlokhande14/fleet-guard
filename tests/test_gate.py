import pytest

from fleetguard import cli, repo
from fleetguard.builds import Registry
from fleetguard.summary import campaign_markdown

pytestmark = pytest.mark.fgsim


@pytest.fixture
def env(db, db_url, fgsim, tmp_path, monkeypatch):
    repo.sync_builds(db, Registry(defaults=fgsim.defaults()))
    db.commit()
    monkeypatch.setenv("FG_DATABASE_URL", db_url)
    monkeypatch.setenv("FG_RUNS_DIR", str(tmp_path))
    return tmp_path


def test_gate_fails_on_regression_and_writes_summary(db, env, capsys):
    summary = env / "summary.md"
    code = cli.main(["gate", "--baseline", "drive-2.3.0", "--candidate", "drive-2.4.0-rc1", "--count", "140",
                     "--summary", str(summary), "--ui", "http://fleet.local:8080/"])
    assert code == 1
    md = summary.read_text()
    assert "drive-2.4.0-rc1 vs drive-2.3.0: **REGRESSION**" in md
    assert "| control_instability |" in md and "yes |" in md
    assert "](http://fleet.local:8080/failures/" in md
    assert md in capsys.readouterr().out


def test_gate_passes_identical_build(db, env):
    assert cli.main(["gate", "--baseline", "drive-2.3.0", "--candidate", "drive-2.3.0", "--count", "70"]) == 0


def test_summary_before_verdict(db):
    db.execute("INSERT INTO builds (name, overrides, params) VALUES ('a', '{}', '{}')")
    cid = db.execute("INSERT INTO campaigns (name, baseline, candidate, families, scenario_count)"
                     " VALUES ('x', 'a', 'a', ARRAY['s_curve'], 7) RETURNING id").fetchone()["id"]
    assert "Status: queued" in campaign_markdown(db, cid)
    with pytest.raises(LookupError):
        campaign_markdown(db, 999)
