"""Action tools backed by the scheduling runtime."""

from scheduling import SchedulingRuntime


class ActionServerTools:
    def __init__(self):
        self.runtime = SchedulingRuntime()

    def _error_response(self, message, exc, input_payload):
        return {
            "ok": False,
            "message": message,
            "error": {
                "code": "INVALID_INPUT",
                "message": str(exc),
            },
            "input": input_payload,
            "runtime_status": self.runtime.get_runtime_status(),
        }

    def _safe_call(self, message, func, input_payload):
        try:
            return {
                "ok": True,
                "message": message,
                "result": func(),
                "runtime_status": self.runtime.get_runtime_status(),
            }
        except Exception as exc:
            return self._error_response(
                "Request was rejected by scheduling runtime.",
                exc,
                input_payload,
            )

    def tool_robotic_reaction(self, recipe=None, vessel_id=None, **_ignored):
        """Convert a reaction request into a scheduled task."""
        return self._safe_call(
            "Reaction task accepted by scheduling runtime.",
            lambda: self.runtime.submit_reaction(recipe=recipe, vessel_id=vessel_id),
            {"recipe": recipe, "vessel_id": vessel_id},
        )

    def tool_robotic_measurement(self, sample_id=None, measurement_type=None, **_ignored):
        """Convert a measurement request into a scheduled task."""
        return self._safe_call(
            "Measurement task accepted by scheduling runtime.",
            lambda: self.runtime.submit_measurement(
                sample_id=sample_id,
                measurement_type=measurement_type,
            ),
            {"sample_id": sample_id, "measurement_type": measurement_type},
        )

    def tool_robotic_characterization(self, sample_id=None, analysis_method=None, **_ignored):
        """Convert a characterization request into a scheduled task."""
        return self._safe_call(
            "Characterization task accepted by scheduling runtime.",
            lambda: self.runtime.submit_characterization(
                sample_id=sample_id,
                analysis_method=analysis_method,
            ),
            {"sample_id": sample_id, "analysis_method": analysis_method},
        )

    def tool_scheduler_status(self, **_ignored):
        """Return the current scheduler state snapshot."""
        return {
            "ok": True,
            "message": "Scheduler status snapshot.",
            "runtime_status": self.runtime.get_runtime_status(),
        }

    def tool_scheduler_advance(self, steps=1, **_ignored):
        """Advance the scheduler clock and expose new state transitions."""
        return self._safe_call(
            "Scheduler time advanced.",
            lambda: self.runtime.advance_time(steps=steps),
            {"steps": steps},
        )

    def tool_scheduler_run_until_complete(self, max_steps=1000, **_ignored):
        """Run the scheduler until all known tasks complete or the step budget is exhausted."""
        return self._safe_call(
            "Scheduler ran until completion or step budget.",
            lambda: self.runtime.run_until_all_complete(max_steps=max_steps),
            {"max_steps": max_steps},
        )
