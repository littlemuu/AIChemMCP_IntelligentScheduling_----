"""Action tools backed by the scheduling runtime."""

from scheduling import SchedulingRuntime


class ActionServerTools:
    def __init__(self):
        self.runtime = SchedulingRuntime()

    def tool_robotic_reaction(self, recipe, vessel_id):
        """Convert a reaction request into a scheduled task."""
        return {
            "message": "Reaction task accepted by scheduling runtime.",
            "result": self.runtime.submit_reaction(recipe=recipe, vessel_id=vessel_id),
            "runtime_status": self.runtime.get_runtime_status(),
        }

    def tool_robotic_measurement(self, sample_id, measurement_type):
        """Convert a measurement request into a scheduled task."""
        return {
            "message": "Measurement task accepted by scheduling runtime.",
            "result": self.runtime.submit_measurement(
                sample_id=sample_id,
                measurement_type=measurement_type,
            ),
            "runtime_status": self.runtime.get_runtime_status(),
        }

    def tool_robotic_characterization(self, sample_id, analysis_method):
        """Convert a characterization request into a scheduled task."""
        return {
            "message": "Characterization task accepted by scheduling runtime.",
            "result": self.runtime.submit_characterization(
                sample_id=sample_id,
                analysis_method=analysis_method,
            ),
            "runtime_status": self.runtime.get_runtime_status(),
        }

    def tool_scheduler_advance(self, steps=1):
        """Advance the scheduler clock and expose new state transitions."""
        return self.runtime.advance_time(steps=steps)

    def tool_scheduler_run_until_complete(self, max_steps=1000):
        """Run the scheduler until all known tasks complete or the step budget is exhausted."""
        return self.runtime.run_until_all_complete(max_steps=max_steps)
