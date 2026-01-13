#pragma once

#include <cstddef>
#include <limits>
#include <vector>

#include "fleetguard/math.hpp"

namespace fg {

struct Projection {
  double s = 0.0;        // arc length of the closest point
  double lateral = 0.0;  // signed distance, left of the path is positive
  double heading = 0.0;  // path heading at s
  size_t segment = 0;    // index of the segment holding the closest point
  Vec2 point;            // closest point on the path
};

// Densely sampled polyline with arc-length parameterisation.
class Path {
 public:
  static constexpr size_t npos = std::numeric_limits<size_t>::max();

  Path() = default;
  explicit Path(std::vector<Vec2> points);

  bool empty() const { return pts_.size() < 2; }
  double length() const { return s_.empty() ? 0.0 : s_.back(); }
  const std::vector<Vec2>& points() const { return pts_; }

  Vec2 point_at(double s) const;
  double heading_at(double s) const;
  Vec2 tangent_at(double s) const { return Vec2::from_angle(heading_at(s)); }
  Vec2 normal_at(double s) const { return tangent_at(s).perp(); }
  // signed curvature (1/m), positive when the path turns left
  double curvature_at(double s) const;
  double max_abs_curvature(double s0, double s1, double step = 2.0) const;

  // Closest point to p. With a hint (segment index from the previous call) only a
  // window of segments around it is searched, which keeps per-tick projection O(1).
  Projection project(Vec2 p, size_t hint = npos, size_t window = 30) const;

  // Path displaced sideways by `lateral` metres (left positive).
  Path offset(double lateral) const;

  size_t segment_index(double s) const;

 private:
  std::vector<Vec2> pts_;
  std::vector<double> s_;      // cumulative arc length at each vertex
  std::vector<double> kappa_;  // curvature at each vertex
};

// Builds a path from straights and arcs, sampled every `ds` metres.
class PathBuilder {
 public:
  explicit PathBuilder(Vec2 start = {0, 0}, double heading = 0.0, double ds = 1.0);

  PathBuilder& straight(double length);
  // positive angle turns left
  PathBuilder& arc(double radius, double angle);
  // smooth sideways shift of `offset` metres over `length` metres, heading restored at the end
  PathBuilder& lane_shift(double length, double offset);

  Vec2 position() const { return pos_; }
  double heading() const { return heading_; }
  Path build() const { return Path(pts_); }

 private:
  void push(Vec2 p);

  std::vector<Vec2> pts_;
  Vec2 pos_;
  double heading_;
  double ds_;
};

}  // namespace fg
