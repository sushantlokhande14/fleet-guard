#pragma once

#include <algorithm>
#include <cmath>

namespace fg {

constexpr double kPi = 3.14159265358979323846;
constexpr double kGravity = 9.81;

struct Vec2 {
  double x = 0.0;
  double y = 0.0;

  constexpr Vec2() = default;
  constexpr Vec2(double x_, double y_) : x(x_), y(y_) {}

  constexpr Vec2 operator+(Vec2 o) const { return {x + o.x, y + o.y}; }
  constexpr Vec2 operator-(Vec2 o) const { return {x - o.x, y - o.y}; }
  constexpr Vec2 operator*(double s) const { return {x * s, y * s}; }
  constexpr Vec2 operator/(double s) const { return {x / s, y / s}; }
  constexpr Vec2 operator-() const { return {-x, -y}; }
  Vec2& operator+=(Vec2 o) {
    x += o.x;
    y += o.y;
    return *this;
  }
  Vec2& operator-=(Vec2 o) {
    x -= o.x;
    y -= o.y;
    return *this;
  }

  constexpr double dot(Vec2 o) const { return x * o.x + y * o.y; }
  // z component of the 3D cross product; > 0 when o is to the left of *this
  constexpr double cross(Vec2 o) const { return x * o.y - y * o.x; }
  double norm() const { return std::hypot(x, y); }
  constexpr double norm2() const { return x * x + y * y; }
  Vec2 normalized() const {
    const double n = norm();
    return n > 1e-12 ? Vec2{x / n, y / n} : Vec2{0.0, 0.0};
  }
  // left-hand perpendicular
  constexpr Vec2 perp() const { return {-y, x}; }
  Vec2 rotated(double a) const {
    const double c = std::cos(a), s = std::sin(a);
    return {c * x - s * y, s * x + c * y};
  }
  double angle() const { return std::atan2(y, x); }

  static Vec2 from_angle(double a) { return {std::cos(a), std::sin(a)}; }
};

inline constexpr Vec2 operator*(double s, Vec2 v) { return v * s; }

inline double distance(Vec2 a, Vec2 b) { return (a - b).norm(); }

// wrap to [-pi, pi]
inline double wrap_angle(double a) { return std::remainder(a, 2.0 * kPi); }

inline double clamp(double v, double lo, double hi) { return std::min(std::max(v, lo), hi); }

inline double lerp(double a, double b, double t) { return a + (b - a) * t; }

inline double sign(double v) { return (v > 0.0) - (v < 0.0); }

inline double deg2rad(double d) { return d * kPi / 180.0; }

}  // namespace fg
