#pragma once

#include <cstdint>
#include <functional>
#include <string>
#include <vector>

#include "fleetguard/build_config.hpp"

namespace fg {

enum class FramePolicy { None, Flagged, All };

struct BatchOptions {
  std::vector<std::string> families;  // empty = all
  uint64_t seed_start = 0;
  uint64_t count = 0;  // scenarios; each one is driven by both builds
  BuildConfig baseline;
  BuildConfig candidate;
  int threads = 0;  // 0 = hardware concurrency
  std::string out_dir;
  FramePolicy frames = FramePolicy::Flagged;
  uint64_t max_frame_pairs = 500;  // cap on pairs whose telemetry is written
  uint64_t chunk = 1024;          // scenarios per write-out chunk
  std::function<void(uint64_t done, uint64_t total)> progress;
};

struct BatchStats {
  uint64_t scenarios = 0;
  uint64_t drives = 0;
  uint64_t flagged_pairs = 0;
  uint64_t frame_pairs_written = 0;
  uint64_t events = 0;
  double seconds = 0.0;
};

// Scenario i is family families[i % F] with seed seed_start + i / F, so every
// family gets a contiguous seed range. Output files (all in out_dir):
//   scenarios.jsonl  one scenario description per line
//   drives.jsonl     one drive summary per line (role = baseline | candidate)
//   events.jsonl     one event per line, keyed by scenario and role
//   pairs.jsonl      one pair comparison per scenario
//   frames.csv       10 Hz telemetry for flagged pairs (both roles)
//   manifest.json    options, counts and timing
// Output order is the scenario index order, independent of thread count.
BatchStats run_batch(const BatchOptions& opt);

}  // namespace fg
