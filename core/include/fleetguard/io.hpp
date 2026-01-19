#pragma once

#include <nlohmann/json.hpp>
#include <ostream>
#include <string>

#include "fleetguard/telemetry.hpp"

namespace fg {

// CSV column order for frames; the Python ingester relies on it.
const char* frame_csv_header();
void write_frame_csv(std::ostream& os, const Frame& f);

nlohmann::json summary_to_json(const DriveSummary& s);
nlohmann::json event_to_json(const Event& e);

}  // namespace fg
