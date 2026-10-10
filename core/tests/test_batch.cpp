#include <gtest/gtest.h>

#include <algorithm>
#include <filesystem>
#include <fstream>
#include <sstream>

#include "fleetguard/batch.hpp"

using namespace fg;
namespace fs = std::filesystem;

namespace {

std::string slurp(const fs::path& p) {
  std::ifstream in(p, std::ios::binary);
  std::stringstream ss;
  ss << in.rdbuf();
  return ss.str();
}

size_t lines(const fs::path& p) {
  const std::string s = slurp(p);
  return static_cast<size_t>(std::count(s.begin(), s.end(), '\n'));
}

fs::path tmpdir(const std::string& name) {
  fs::path p = fs::temp_directory_path() / ("fg_batch_" + name);
  fs::remove_all(p);
  return p;
}

BatchOptions small(const std::string& out, int threads) {
  BatchOptions o;
  o.families = {"urban_cut_in", "s_curve", "ped_crossing"};
  o.seed_start = 100;
  o.count = 24;
  o.threads = threads;
  o.chunk = 7;  // deliberately not a divisor
  o.out_dir = out;
  o.candidate.name = "rc";
  o.candidate.control.steer_gain = 1.6;
  return o;
}

}  // namespace

TEST(Batch, WritesEveryFile) {
  const fs::path d = tmpdir("files");
  BatchStats st = run_batch(small(d.string(), 2));
  EXPECT_EQ(st.scenarios, 24u);
  EXPECT_EQ(st.drives, 48u);
  EXPECT_EQ(lines(d / "scenarios.jsonl"), 24u);
  EXPECT_EQ(lines(d / "drives.jsonl"), 48u);
  EXPECT_EQ(lines(d / "pairs.jsonl"), 24u);
  EXPECT_EQ(lines(d / "events.jsonl"), st.events);
  EXPECT_TRUE(fs::exists(d / "manifest.json"));
  auto m = nlohmann::json::parse(slurp(d / "manifest.json"));
  EXPECT_EQ(m["drives"].get<int>(), 48);
  EXPECT_EQ(m["candidate"]["control"]["steer_gain"].get<double>(), 1.6);
}

TEST(Batch, FamiliesGetContiguousSeeds) {
  const fs::path d = tmpdir("seeds");
  run_batch(small(d.string(), 1));
  std::ifstream in(d / "scenarios.jsonl");
  std::string line;
  std::vector<std::string> ids;
  while (std::getline(in, line)) ids.push_back(nlohmann::json::parse(line)["id"]);
  EXPECT_EQ(ids[0], "urban_cut_in-100");
  EXPECT_EQ(ids[1], "s_curve-100");
  EXPECT_EQ(ids[2], "ped_crossing-100");
  EXPECT_EQ(ids[3], "urban_cut_in-101");
}

TEST(Batch, OutputIndependentOfThreadCount) {
  const fs::path a = tmpdir("t1"), b = tmpdir("t8");
  run_batch(small(a.string(), 1));
  run_batch(small(b.string(), 8));
  for (const char* f : {"scenarios.jsonl", "drives.jsonl", "events.jsonl", "pairs.jsonl", "frames.csv"}) {
    EXPECT_EQ(slurp(a / f), slurp(b / f)) << f;
  }
}

TEST(Batch, FramePolicyAndCap) {
  const fs::path none = tmpdir("none"), all = tmpdir("all"), capped = tmpdir("capped");
  BatchOptions o = small(none.string(), 4);
  o.frames = FramePolicy::None;
  EXPECT_EQ(run_batch(o).frame_pairs_written, 0u);
  EXPECT_EQ(lines(none / "frames.csv"), 1u);  // header only

  o = small(all.string(), 4);
  o.frames = FramePolicy::All;
  EXPECT_EQ(run_batch(o).frame_pairs_written, 24u);

  o = small(capped.string(), 4);
  o.frames = FramePolicy::All;
  o.max_frame_pairs = 3;
  EXPECT_EQ(run_batch(o).frame_pairs_written, 3u);
}

TEST(Batch, IdenticalBuildsFlagOnlyBaselineFailures) {
  const fs::path d = tmpdir("same");
  BatchOptions o = small(d.string(), 4);
  o.candidate = o.baseline;
  run_batch(o);
  std::ifstream in(d / "pairs.jsonl");
  std::string line;
  while (std::getline(in, line)) {
    auto p = nlohmann::json::parse(line);
    EXPECT_DOUBLE_EQ(p["lat_max_abs_diff"].get<double>(), 0.0);
    EXPECT_FALSE(p["outcome_changed"].get<bool>());
  }
}

TEST(Batch, RejectsUnknownFamily) {
  BatchOptions o = small(tmpdir("bad").string(), 1);
  o.families = {"moon_landing"};
  EXPECT_THROW(run_batch(o), std::invalid_argument);
}
