#include "fleetguard/events.hpp"

#include <algorithm>

namespace fg {

bool ReversalCounter::add(double x) {
  if (!init_) {
    lo_ = hi_ = x;
    init_ = true;
    return false;
  }
  bool reversed = false;
  if (dir_ >= 0) {
    if (x > hi_) hi_ = x;
    if (hi_ - x > gap_) {
      if (dir_ > 0) {
        ++count_;
        reversed = true;
      }
      dir_ = -1;
      lo_ = x;
    }
  }
  if (dir_ <= 0) {
    if (x < lo_) lo_ = x;
    if (x - lo_ > gap_) {
      if (dir_ < 0) {
        ++count_;
        reversed = true;
      }
      dir_ = 1;
      hi_ = x;
    }
  }
  return reversed;
}

void EpisodeDetector::update(double t, bool active, double value, std::vector<Event>& out) {
  if (active) {
    if (!open_) {
      open_ = true;
      start_ = t;
      peak_ = value;
    } else {
      peak_ = peak_is_max_ ? std::max(peak_, value) : std::min(peak_, value);
    }
  } else if (open_) {
    close(t, out);
  }
}

void EpisodeDetector::flush(double t, std::vector<Event>& out) {
  if (open_) close(t, out);
}

void EpisodeDetector::close(double t, std::vector<Event>& out) {
  open_ = false;
  const double dur = t - start_;
  if (dur + 1e-9 < min_duration_) return;
  ++episodes_;
  Event e;
  e.t = start_;
  e.kind = kind_;
  e.severity = severity_;
  e.value = peak_;
  e.duration = dur;
  out.push_back(e);
}

bool OscillationDetector::update(double t, double x) {
  if (counter_.add(x)) times_.push_back(t);
  while (!times_.empty() && times_.front() < t - window_) times_.pop_front();
  return static_cast<int>(times_.size()) >= min_reversals_;
}

}  // namespace fg
