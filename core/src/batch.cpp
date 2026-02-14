#include "fleetguard/batch.hpp"

#include <atomic>
#include <chrono>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <thread>

#include "fleetguard/compare.hpp"
#include "fleetguard/io.hpp"
#include "fleetguard/scenario.hpp"
#include "fleetguard/sim.hpp"

namespace fg {

namespace {

// Everything one scenario produces, serialised by the worker thread.
struct Slot {
  std::string scenario;
  std::string drives;
  std::string events;
  std::string pair;
  bool flagged = false;
  uint64_t n_events = 0;
  std::vector<Frame> base_frames, cand_frames;
};

bool is_flagged(const DriveResult& b, const DriveResult& c, const PairMetrics& p) {
  if (b.summary.outcome != "completed" || c.summary.outcome != "completed") return true;
  if (p.first_divergence_s >= 0.0) return true;
  if (std::fabs(p.d_recall) > 0.02 || std::fabs(p.d_precision) > 0.02) return true;
  if (p.d_deadline_misses != 0 || p.d_hard_brakes != 0) return true;
  if (std::fabs(p.d_steer_reversal_rate) > 0.1 || std::fabs(p.d_accel_reversal_rate) > 0.1) return true;
  return false;
}

void append_events(std::string& out, const DriveResult& r, const char* role) {
  for (const auto& e : r.events) {
    nlohmann::json j = event_to_json(e);
    j["scenario_id"] = r.summary.scenario_id;
    j["role"] = role;
    j["build"] = r.summary.build;
    out += j.dump();
    out += '\n';
  }
}

void fill(Slot& slot, const std::string& family, uint64_t seed, const BatchOptions& opt) {
  const Scenario sc = make_scenario(family, seed);
  const DriveResult b = run_drive(sc, opt.baseline);
  const DriveResult c = run_drive(sc, opt.candidate);
  const PairMetrics p = compare_drives(b, c);
  slot.flagged = is_flagged(b, c, p);

  slot.scenario = sc.describe().dump() + "\n";
  nlohmann::json jb = summary_to_json(b.summary);
  jb["role"] = "baseline";
  nlohmann::json jc = summary_to_json(c.summary);
  jc["role"] = "candidate";
  slot.drives = jb.dump() + "\n" + jc.dump() + "\n";
  slot.events.clear();
  append_events(slot.events, b, "baseline");
  append_events(slot.events, c, "candidate");
  slot.n_events = b.events.size() + c.events.size();
  nlohmann::json jp = pair_to_json(p);
  jp["flagged"] = slot.flagged;
  slot.pair = jp.dump() + "\n";

  const bool keep = opt.frames == FramePolicy::All || (opt.frames == FramePolicy::Flagged && slot.flagged);
  if (keep) {
    slot.base_frames = b.frames;
    slot.cand_frames = c.frames;
  }
}

std::ofstream open_out(const std::filesystem::path& p) {
  std::ofstream f(p, std::ios::binary);
  if (!f) throw std::runtime_error("cannot write " + p.string());
  return f;
}

}  // namespace

BatchStats run_batch(const BatchOptions& opt_in) {
  BatchOptions opt = opt_in;
  if (opt.families.empty()) opt.families = scenario_families();
  for (const auto& f : opt.families) {
    if (!is_family(f)) throw std::invalid_argument("unknown scenario family: " + f);
  }
  if (opt.out_dir.empty()) throw std::invalid_argument("batch needs an output directory");
  int threads = opt.threads > 0 ? opt.threads : static_cast<int>(std::thread::hardware_concurrency());
  threads = std::max(1, threads);

  namespace fs = std::filesystem;
  fs::create_directories(opt.out_dir);
  const fs::path dir(opt.out_dir);
  auto f_scen = open_out(dir / "scenarios.jsonl");
  auto f_drives = open_out(dir / "drives.jsonl");
  auto f_events = open_out(dir / "events.jsonl");
  auto f_pairs = open_out(dir / "pairs.jsonl");
  auto f_frames = open_out(dir / "frames.csv");
  f_frames << "scenario_id,role," << frame_csv_header() << '\n';

  const auto t0 = std::chrono::steady_clock::now();
  BatchStats st;
  const uint64_t F = opt.families.size();
  std::vector<Slot> slots;

  for (uint64_t c0 = 0; c0 < opt.count; c0 += opt.chunk) {
    const uint64_t c1 = std::min(opt.count, c0 + opt.chunk);
    slots.assign(c1 - c0, Slot{});
    std::atomic<uint64_t> next{c0};
    std::vector<std::thread> pool;
    for (int k = 0; k < threads; ++k) {
      pool.emplace_back([&] {
        for (uint64_t i = next++; i < c1; i = next++) {
          fill(slots[i - c0], opt.families[i % F], opt.seed_start + i / F, opt);
        }
      });
    }
    for (auto& th : pool) th.join();

    for (auto& s : slots) {
      f_scen << s.scenario;
      f_drives << s.drives;
      f_events << s.events;
      f_pairs << s.pair;
      st.events += s.n_events;
      st.flagged_pairs += s.flagged ? 1 : 0;
      if (!s.base_frames.empty() && st.frame_pairs_written < opt.max_frame_pairs) {
        // the scenario id is the first field of the description line
        const std::string id = nlohmann::json::parse(s.scenario)["id"].get<std::string>();
        for (const auto& f : s.base_frames) {
          f_frames << id << ",baseline,";
          write_frame_csv(f_frames, f);
        }
        for (const auto& f : s.cand_frames) {
          f_frames << id << ",candidate,";
          write_frame_csv(f_frames, f);
        }
        st.frame_pairs_written++;
      }
    }
    st.scenarios = c1;
    st.drives = 2 * c1;
    if (opt.progress) opt.progress(c1, opt.count);
  }

  st.seconds = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
  nlohmann::json m;
  m["families"] = opt.families;
  m["seed_start"] = opt.seed_start;
  m["count"] = opt.count;
  m["threads"] = threads;
  m["baseline"] = build_to_json(opt.baseline);
  m["candidate"] = build_to_json(opt.candidate);
  m["scenarios"] = st.scenarios;
  m["drives"] = st.drives;
  m["flagged_pairs"] = st.flagged_pairs;
  m["frame_pairs_written"] = st.frame_pairs_written;
  m["events"] = st.events;
  m["seconds"] = st.seconds;
  m["drives_per_second"] = st.seconds > 0 ? st.drives / st.seconds : 0.0;
  auto f_manifest = open_out(dir / "manifest.json");
  f_manifest << m.dump(2) << '\n';
  return st;
}

}  // namespace fg
