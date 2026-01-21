#pragma once

#include <deque>
#include <string>
#include <vector>

#include "fleetguard/telemetry.hpp"

namespace fg {

// Counts direction reversals of a signal, ignoring wiggles smaller than `gap`
// (the steering-reversal-rate metric from driver behaviour studies).
class ReversalCounter {
 public:
  explicit ReversalCounter(double gap) : gap_(gap) {}
  // returns true when this sample completes a reversal
  bool add(double x);
  int count() const { return count_; }

 private:
  double gap_;
  bool init_ = false;
  int dir_ = 0;
  double lo_ = 0, hi_ = 0;
  int count_ = 0;
};

// Turns a per-tick condition into start/duration/peak events. An episode only
// becomes an event if it lasts at least `min_duration`.
class EpisodeDetector {
 public:
  EpisodeDetector(std::string kind, int severity, double min_duration, bool peak_is_max = true)
      : kind_(std::move(kind)), severity_(severity), min_duration_(min_duration), peak_is_max_(peak_is_max) {}

  void update(double t, bool active, double value, std::vector<Event>& out);
  void flush(double t, std::vector<Event>& out);  // close an open episode at the end of a drive
  int episodes() const { return episodes_; }

 private:
  void close(double t, std::vector<Event>& out);

  std::string kind_;
  int severity_;
  double min_duration_;
  bool peak_is_max_;
  bool open_ = false;
  double start_ = 0.0;
  double peak_ = 0.0;
  int episodes_ = 0;
};

// Signal is "oscillating" while at least `min_reversals` reversals fall inside
// the trailing window.
class OscillationDetector {
 public:
  OscillationDetector(double gap, double window_s, int min_reversals)
      : counter_(gap), window_(window_s), min_reversals_(min_reversals) {}
  bool update(double t, double x);
  int in_window() const { return static_cast<int>(times_.size()); }

 private:
  ReversalCounter counter_;
  double window_;
  int min_reversals_;
  std::deque<double> times_;
};

}  // namespace fg
