// fgsim: command-line front end of the Fleet Guard core.
#include <fstream>
#include <iostream>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>

#include "fleetguard/build_config.hpp"
#include "fleetguard/compare.hpp"
#include "fleetguard/io.hpp"
#include "fleetguard/scenario.hpp"
#include "fleetguard/sim.hpp"

namespace {

constexpr const char* kVersion = "0.1.0";

const char* kUsage = R"(usage: fgsim <command> [options]

commands:
  version                         print the core version
  families                        list scenario families
  defaults                        print the default build configuration
  scenario --family F --seed N    print a scenario description
           [--geometry]           include route geometry
  run --family F --seed N         drive one scenario, print the summary
      [--build FILE]              build config JSON (default: baseline)
      [--frames FILE]             write 10 Hz telemetry CSV
      [--events]                  include the event list in the output
  compare --family F --seed N     drive one scenario with two builds and diff them
          --baseline FILE --candidate FILE
          [--frames-prefix P]     write P.baseline.csv and P.candidate.csv
)";

struct Args {
  std::string command;
  std::map<std::string, std::string> opts;
  bool has(const std::string& k) const { return opts.count(k) > 0; }
  std::string get(const std::string& k, const std::string& def = "") const {
    auto it = opts.find(k);
    return it == opts.end() ? def : it->second;
  }
  std::string need(const std::string& k) const {
    if (!has(k)) throw std::invalid_argument("missing --" + k);
    return opts.at(k);
  }
};

Args parse(int argc, char** argv) {
  Args a;
  if (argc < 2) throw std::invalid_argument("no command");
  a.command = argv[1];
  for (int i = 2; i < argc; ++i) {
    std::string tok = argv[i];
    if (tok.rfind("--", 0) != 0) throw std::invalid_argument("unexpected argument: " + tok);
    tok = tok.substr(2);
    if (i + 1 < argc && std::string(argv[i + 1]).rfind("--", 0) != 0) {
      a.opts[tok] = argv[++i];
    } else {
      a.opts[tok] = "1";
    }
  }
  return a;
}

fg::BuildConfig load_build(const std::string& path) {
  if (path.empty()) return fg::BuildConfig{};
  std::ifstream in(path);
  if (!in) throw std::runtime_error("cannot open build file: " + path);
  return fg::build_from_json(nlohmann::json::parse(in));
}

void write_frames(const std::string& path, const std::vector<fg::Frame>& frames) {
  std::ofstream out(path);
  if (!out) throw std::runtime_error("cannot write " + path);
  out << fg::frame_csv_header() << '\n';
  for (const auto& f : frames) fg::write_frame_csv(out, f);
}

nlohmann::json drive_json(const fg::DriveResult& r, bool with_events) {
  nlohmann::json j = fg::summary_to_json(r.summary);
  if (with_events) {
    j["events"] = nlohmann::json::array();
    for (const auto& e : r.events) j["events"].push_back(fg::event_to_json(e));
  }
  return j;
}

int cmd_compare(const Args& a) {
  const fg::Scenario sc = fg::make_scenario(a.need("family"), std::stoull(a.need("seed")));
  const fg::BuildConfig base = load_build(a.need("baseline"));
  const fg::BuildConfig cand = load_build(a.need("candidate"));
  const fg::DriveResult rb = fg::run_drive(sc, base);
  const fg::DriveResult rc = fg::run_drive(sc, cand);
  if (a.has("frames-prefix")) {
    write_frames(a.get("frames-prefix") + ".baseline.csv", rb.frames);
    write_frames(a.get("frames-prefix") + ".candidate.csv", rc.frames);
  }
  nlohmann::json j;
  j["scenario"] = sc.describe();
  j["baseline"] = drive_json(rb, true);
  j["candidate"] = drive_json(rc, true);
  j["pair"] = fg::pair_to_json(fg::compare_drives(rb, rc));
  std::cout << j.dump() << '\n';
  return 0;
}

int cmd_run(const Args& a) {
  const fg::Scenario sc = fg::make_scenario(a.need("family"), std::stoull(a.need("seed")));
  const fg::BuildConfig build = load_build(a.get("build"));
  fg::SimOptions opt;
  opt.record_frames = a.has("frames");
  const fg::DriveResult r = fg::run_drive(sc, build, opt);

  if (a.has("frames")) write_frames(a.get("frames"), r.frames);
  std::cout << drive_json(r, a.has("events")).dump() << '\n';
  return 0;
}

}  // namespace

int main(int argc, char** argv) {
  try {
    const Args a = parse(argc, argv);
    if (a.command == "version") {
      std::cout << kVersion << '\n';
    } else if (a.command == "families") {
      for (const auto& f : fg::scenario_families()) std::cout << f << '\n';
    } else if (a.command == "defaults") {
      std::cout << fg::build_to_json(fg::BuildConfig{}).dump(2) << '\n';
    } else if (a.command == "scenario") {
      const fg::Scenario sc = fg::make_scenario(a.need("family"), std::stoull(a.need("seed")));
      nlohmann::json j = sc.describe();
      if (a.has("geometry")) j["geometry"] = sc.geometry();
      std::cout << j.dump() << '\n';
    } else if (a.command == "run") {
      return cmd_run(a);
    } else if (a.command == "compare") {
      return cmd_compare(a);
    } else if (a.command == "help" || a.command == "--help") {
      std::cout << kUsage;
    } else {
      throw std::invalid_argument("unknown command: " + a.command);
    }
  } catch (const std::exception& e) {
    std::cerr << "fgsim: " << e.what() << "\n\n" << kUsage;
    return 2;
  }
  return 0;
}
