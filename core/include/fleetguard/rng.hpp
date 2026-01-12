#pragma once

#include <cmath>
#include <cstdint>
#include <vector>

namespace fg {

// xoshiro256** seeded through splitmix64. We do not use <random> distributions
// because their output differs between standard libraries, and every drive has to
// replay bit-for-bit from (scenario seed, build) on any machine.
class Rng {
 public:
  explicit Rng(uint64_t seed) {
    uint64_t x = seed;
    for (auto& s : s_) s = splitmix64(x);
  }

  static uint64_t splitmix64(uint64_t& x) {
    uint64_t z = (x += 0x9E3779B97F4A7C15ULL);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
    return z ^ (z >> 31);
  }

  uint64_t next() {
    const uint64_t result = rotl(s_[1] * 5, 7) * 9;
    const uint64_t t = s_[1] << 17;
    s_[2] ^= s_[0];
    s_[3] ^= s_[1];
    s_[1] ^= s_[2];
    s_[0] ^= s_[3];
    s_[2] ^= t;
    s_[3] = rotl(s_[3], 45);
    return result;
  }

  // [0, 1)
  double uniform() { return static_cast<double>(next() >> 11) * 0x1.0p-53; }
  double uniform(double lo, double hi) { return lo + (hi - lo) * uniform(); }
  // inclusive range
  int uniform_int(int lo, int hi) {
    const uint64_t span = static_cast<uint64_t>(hi - lo) + 1;
    return lo + static_cast<int>(next() % span);
  }
  bool bernoulli(double p) { return uniform() < p; }

  double normal() {
    if (has_spare_) {
      has_spare_ = false;
      return spare_;
    }
    const double u1 = 1.0 - uniform();  // (0, 1]
    const double u2 = uniform();
    const double r = std::sqrt(-2.0 * std::log(u1));
    const double th = 2.0 * 3.14159265358979323846 * u2;
    spare_ = r * std::sin(th);
    has_spare_ = true;
    return r * std::cos(th);
  }
  double normal(double mean, double sd) { return mean + sd * normal(); }

  template <class T>
  const T& pick(const std::vector<T>& v) {
    return v[next() % v.size()];
  }

 private:
  static uint64_t rotl(uint64_t x, int k) { return (x << k) | (x >> (64 - k)); }

  uint64_t s_[4]{};
  double spare_ = 0.0;
  bool has_spare_ = false;
};

// Independent stream for a sub-system (scenario layout, sensor noise, planner timing).
// Keeping streams separate means a change to one build parameter never reshuffles
// the random numbers another subsystem sees.
inline uint64_t derive_seed(uint64_t seed, uint64_t stream) {
  uint64_t x = seed ^ (stream * 0xD1B54A32D192ED03ULL);
  return Rng::splitmix64(x);
}

namespace stream {
constexpr uint64_t kScenario = 1;
constexpr uint64_t kPerception = 2;
constexpr uint64_t kPlanner = 3;
constexpr uint64_t kPhantom = 4;
}  // namespace stream

}  // namespace fg
