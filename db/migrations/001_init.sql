-- Builds, campaigns and everything a campaign produces.

CREATE TABLE builds (
    name        text PRIMARY KEY,
    parent      text,
    description text NOT NULL DEFAULT '',
    overrides   jsonb NOT NULL,           -- what fgsim is given
    params      jsonb NOT NULL,           -- effective parameter set
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE campaigns (
    id                bigserial PRIMARY KEY,
    name              text NOT NULL,
    baseline          text NOT NULL REFERENCES builds(name),
    candidate         text NOT NULL REFERENCES builds(name),
    families          text[] NOT NULL,
    seed_start        bigint NOT NULL DEFAULT 0,
    scenario_count    integer NOT NULL CHECK (scenario_count > 0),
    status            text NOT NULL DEFAULT 'queued'
                      CHECK (status IN ('queued', 'running', 'ingesting', 'classifying', 'done', 'failed')),
    progress          real NOT NULL DEFAULT 0,
    error             text,
    sim_seconds       real,
    drives_per_second real,
    tags              jsonb NOT NULL DEFAULT '{}',
    created_at        timestamptz NOT NULL DEFAULT now(),
    started_at        timestamptz,
    finished_at       timestamptz
);
CREATE INDEX campaigns_status_idx ON campaigns (status, created_at);

CREATE TABLE scenarios (
    id              text PRIMARY KEY,     -- <family>-<seed>
    family          text NOT NULL,
    seed            bigint NOT NULL,
    weather         text NOT NULL,
    route_length_m  real NOT NULL,
    speed_limit_mps real NOT NULL,
    params          jsonb NOT NULL,
    UNIQUE (family, seed)
);

CREATE TABLE drives (
    id                  bigserial PRIMARY KEY,
    campaign_id         bigint NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    scenario_id         text NOT NULL REFERENCES scenarios(id),
    role                text NOT NULL CHECK (role IN ('baseline', 'candidate')),
    build               text NOT NULL,
    outcome             text NOT NULL,
    reason              text NOT NULL DEFAULT '',
    duration_s          real,
    distance_m          real,
    route_completion    real,
    mean_speed          real,
    cte_max             real,
    cte_rms             real,
    cte_p95             real,
    heading_err_max     real,
    jerk_rms            real,
    accel_min           real,
    lat_acc_max         real,
    steer_reversal_rate real,
    accel_reversal_rate real,
    min_ttc             real,
    min_gap             real,
    planner_p50_ms      real,
    planner_p99_ms      real,
    planner_max_ms      real,
    planner_cycles      integer,
    deadline_misses     integer,
    det_tp              integer,
    det_fn              integer,
    det_fp              integer,
    recall              real,
    precision           real,
    hard_brakes         integer,
    n_events            integer,
    UNIQUE (campaign_id, scenario_id, role)
);
CREATE INDEX drives_campaign_idx ON drives (campaign_id, role, outcome);

CREATE TABLE drive_events (
    id        bigserial PRIMARY KEY,
    drive_id  bigint NOT NULL REFERENCES drives(id) ON DELETE CASCADE,
    t         real NOT NULL,
    kind      text NOT NULL,
    severity  smallint NOT NULL,
    value     real,
    duration  real NOT NULL DEFAULT 0,
    detail    text NOT NULL DEFAULT ''
);
CREATE INDEX drive_events_drive_idx ON drive_events (drive_id, t);
CREATE INDEX drive_events_kind_idx ON drive_events (kind);

CREATE TABLE pairs (
    campaign_id           bigint NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    scenario_id           text NOT NULL REFERENCES scenarios(id),
    baseline_drive        bigint NOT NULL REFERENCES drives(id) ON DELETE CASCADE,
    candidate_drive       bigint NOT NULL REFERENCES drives(id) ON DELETE CASCADE,
    flagged               boolean NOT NULL,
    common_s              real,
    lat_mean_abs_diff     real,
    lat_max_abs_diff      real,
    speed_rmse            real,
    time_delta_s          real,
    first_divergence_s    real,
    first_divergence_t    real,
    outcome_changed       boolean NOT NULL,
    d_cte_max             real,
    d_jerk_rms            real,
    d_steer_reversal_rate real,
    d_accel_reversal_rate real,
    d_min_ttc             real,
    d_planner_p99_ms      real,
    d_recall              real,
    d_precision           real,
    d_deadline_misses     integer,
    d_hard_brakes         integer,
    PRIMARY KEY (campaign_id, scenario_id)
);
CREATE INDEX pairs_flagged_idx ON pairs (campaign_id) WHERE flagged;

-- 10 Hz telemetry, kept only for flagged pairs (fgsim decides which)
CREATE TABLE telemetry_frames (
    drive_id           bigint NOT NULL REFERENCES drives(id) ON DELETE CASCADE,
    t                  real NOT NULL,
    x                  real,
    y                  real,
    yaw                real,
    v                  real,
    a                  real,
    steer              real,
    steer_cmd          real,
    accel_cmd          real,
    s                  real,
    cte                real,
    heading_err        real,
    v_ref              real,
    target_speed       real,
    lead_id            integer,
    lead_gap           real,
    gt_gap             real,
    ttc                real,
    planner_latency_ms real,
    deadline_miss      smallint,
    n_tracks           smallint,
    n_relevant         smallint,
    n_missed           smallint,
    n_phantom          smallint,
    engaged            smallint,
    PRIMARY KEY (drive_id, t)
);
