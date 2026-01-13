#include "fleetguard/path.hpp"

#include <algorithm>
#include <stdexcept>

namespace fg {

namespace {

// Menger curvature through three points, signed by turn direction.
double menger(Vec2 a, Vec2 b, Vec2 c) {
  const double ab = (b - a).norm(), bc = (c - b).norm(), ca = (a - c).norm();
  const double denom = ab * bc * ca;
  if (denom < 1e-9) return 0.0;
  return 2.0 * (b - a).cross(c - b) / denom;
}

}  // namespace

Path::Path(std::vector<Vec2> points) {
  // drop duplicate consecutive points, they break heading computation
  for (const auto& p : points) {
    if (pts_.empty() || distance(pts_.back(), p) > 1e-6) pts_.push_back(p);
  }
  if (pts_.size() < 2) throw std::invalid_argument("path needs at least two distinct points");

  s_.resize(pts_.size(), 0.0);
  for (size_t i = 1; i < pts_.size(); ++i) s_[i] = s_[i - 1] + distance(pts_[i - 1], pts_[i]);

  kappa_.resize(pts_.size(), 0.0);
  for (size_t i = 1; i + 1 < pts_.size(); ++i) kappa_[i] = menger(pts_[i - 1], pts_[i], pts_[i + 1]);
  if (pts_.size() > 2) {
    kappa_.front() = kappa_[1];
    kappa_.back() = kappa_[pts_.size() - 2];
  }
}

size_t Path::segment_index(double s) const {
  if (s <= 0.0) return 0;
  if (s >= length()) return pts_.size() - 2;
  auto it = std::upper_bound(s_.begin(), s_.end(), s);
  return static_cast<size_t>(std::distance(s_.begin(), it)) - 1;
}

Vec2 Path::point_at(double s) const {
  const size_t i = segment_index(s);
  const double seg = s_[i + 1] - s_[i];
  // extrapolate linearly past either end so callers can look beyond the route
  const double t = (s - s_[i]) / seg;
  return pts_[i] + (pts_[i + 1] - pts_[i]) * t;
}

double Path::heading_at(double s) const {
  const size_t i = segment_index(s);
  return (pts_[i + 1] - pts_[i]).angle();
}

double Path::curvature_at(double s) const {
  const size_t i = segment_index(s);
  const double t = clamp((s - s_[i]) / (s_[i + 1] - s_[i]), 0.0, 1.0);
  return lerp(kappa_[i], kappa_[i + 1], t);
}

double Path::max_abs_curvature(double s0, double s1, double step) const {
  double m = 0.0;
  for (double s = s0; s <= s1; s += step) m = std::max(m, std::fabs(curvature_at(s)));
  return m;
}

Projection Path::project(Vec2 p, size_t hint, size_t window) const {
  const size_t nseg = pts_.size() - 1;
  size_t lo = 0, hi = nseg;
  if (hint != npos) {
    lo = hint > window ? hint - window : 0;
    hi = std::min(nseg, hint + window + 1);
  }
  Projection best;
  double best_d2 = std::numeric_limits<double>::infinity();
  for (size_t i = lo; i < hi; ++i) {
    const Vec2 a = pts_[i], b = pts_[i + 1];
    const Vec2 ab = b - a;
    const double len2 = ab.norm2();
    double t = len2 > 0 ? (p - a).dot(ab) / len2 : 0.0;
    // allow the first and last segment to extend so points beyond the ends project sensibly
    const double tmin = (i == 0) ? -1e9 : 0.0;
    const double tmax = (i + 1 == nseg) ? 1e9 : 1.0;
    t = clamp(t, tmin, tmax);
    const Vec2 q = a + ab * t;
    const double d2 = (p - q).norm2();
    if (d2 < best_d2) {
      best_d2 = d2;
      best.segment = i;
      best.point = q;
      best.s = s_[i] + t * std::sqrt(len2);
      best.heading = ab.angle();
      best.lateral = sign(ab.cross(p - q)) * std::sqrt(d2);
    }
  }
  return best;
}

Path Path::offset(double lateral) const {
  std::vector<Vec2> out;
  out.reserve(pts_.size());
  for (size_t i = 0; i < pts_.size(); ++i) {
    // vertex normal from the averaged neighbouring segment directions
    const Vec2 prev = i > 0 ? (pts_[i] - pts_[i - 1]).normalized() : (pts_[1] - pts_[0]).normalized();
    const Vec2 next = i + 1 < pts_.size() ? (pts_[i + 1] - pts_[i]).normalized() : prev;
    const Vec2 dir = (prev + next).normalized();
    out.push_back(pts_[i] + dir.perp() * lateral);
  }
  return Path(std::move(out));
}

PathBuilder::PathBuilder(Vec2 start, double heading, double ds) : pos_(start), heading_(heading), ds_(ds) {
  pts_.push_back(start);
}

void PathBuilder::push(Vec2 p) { pts_.push_back(p); }

PathBuilder& PathBuilder::straight(double length) {
  const int n = std::max(1, static_cast<int>(std::ceil(length / ds_)));
  const Vec2 dir = Vec2::from_angle(heading_);
  const Vec2 start = pos_;
  for (int k = 1; k <= n; ++k) push(start + dir * (length * k / n));
  pos_ = start + dir * length;
  return *this;
}

PathBuilder& PathBuilder::arc(double radius, double angle) {
  const double arc_len = radius * std::fabs(angle);
  const int n = std::max(2, static_cast<int>(std::ceil(arc_len / ds_)));
  const double side = sign(angle);
  // centre sits on the inside of the turn
  const Vec2 centre = pos_ + Vec2::from_angle(heading_).perp() * (radius * side);
  const double a0 = (pos_ - centre).angle();
  for (int k = 1; k <= n; ++k) {
    const double a = a0 + angle * k / n;
    push(centre + Vec2::from_angle(a) * radius);
  }
  pos_ = pts_.back();
  heading_ = wrap_angle(heading_ + angle);
  return *this;
}

PathBuilder& PathBuilder::lane_shift(double length, double offset) {
  const int n = std::max(2, static_cast<int>(std::ceil(length / ds_)));
  const Vec2 fwd = Vec2::from_angle(heading_);
  const Vec2 left = fwd.perp();
  const Vec2 start = pos_;
  for (int k = 1; k <= n; ++k) {
    const double u = static_cast<double>(k) / n;
    const double lat = offset * 0.5 * (1.0 - std::cos(kPi * u));
    push(start + fwd * (length * u) + left * lat);
  }
  pos_ = pts_.back();
  return *this;
}

}  // namespace fg
