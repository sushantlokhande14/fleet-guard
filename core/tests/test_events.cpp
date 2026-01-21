#include <gtest/gtest.h>

#include <cmath>

#include "fleetguard/events.hpp"
#include "fleetguard/math.hpp"

using namespace fg;

TEST(Events, ReversalCounterIgnoresSmallWiggles) {
  ReversalCounter rc(0.1);
  for (int i = 0; i < 200; ++i) rc.add(0.05 * std::sin(i * 0.3));
  EXPECT_EQ(rc.count(), 0);
  ReversalCounter big(0.1);
  for (int i = 0; i < 200; ++i) big.add(1.0 * std::sin(i * 0.3));  // ~9.5 cycles
  EXPECT_NEAR(big.count(), 19, 1);
}

TEST(Events, EpisodeNeedsMinimumDuration) {
  EpisodeDetector d("off_route", 2, 0.5);
  std::vector<Event> ev;
  double t = 0;
  for (; t < 1.0; t += 0.05) d.update(t, false, 0, ev);
  for (; t < 1.3; t += 0.05) d.update(t, true, 0.6, ev);  // 0.3 s: too short
  for (; t < 2.0; t += 0.05) d.update(t, false, 0, ev);
  EXPECT_TRUE(ev.empty());
  for (; t < 3.0; t += 0.05) d.update(t, true, 0.6 + (t - 2.0), ev);
  d.update(t, false, 0, ev);
  ASSERT_EQ(ev.size(), 1u);
  EXPECT_NEAR(ev[0].t, 2.0, 0.051);
  EXPECT_NEAR(ev[0].duration, 1.0, 0.06);
  EXPECT_NEAR(ev[0].value, 1.55, 0.06);
  EXPECT_EQ(ev[0].kind, "off_route");
}

TEST(Events, MinPeakAndFlush) {
  EpisodeDetector d("hard_brake", 2, 0.1, false);
  std::vector<Event> ev;
  d.update(0.0, true, -4.5, ev);
  d.update(0.05, true, -6.0, ev);
  d.update(0.1, true, -5.0, ev);
  d.flush(0.15, ev);
  ASSERT_EQ(ev.size(), 1u);
  EXPECT_DOUBLE_EQ(ev[0].value, -6.0);
  EXPECT_EQ(d.episodes(), 1);
}

TEST(Events, OscillationWindow) {
  OscillationDetector od(0.05, 4.0, 4);
  bool fired = false;
  // 0.2 Hz swing: two reversals per 5 s, never 4 in a 4 s window
  for (double t = 0; t < 30; t += 0.05) fired |= od.update(t, 0.2 * std::sin(2 * kPi * 0.2 * t));
  EXPECT_FALSE(fired);
  OscillationDetector fast(0.05, 4.0, 4);
  fired = false;
  for (double t = 0; t < 30; t += 0.05) fired |= fast.update(t, 0.2 * std::sin(2 * kPi * 0.8 * t));
  EXPECT_TRUE(fired);
}
