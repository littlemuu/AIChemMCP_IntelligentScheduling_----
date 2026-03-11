import json
import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tools.action_server_tools import ActionServerTools


tool_manager = ActionServerTools()


def tool_robotic_reaction(**params):
    return tool_manager.tool_robotic_reaction(**params)


def tool_robotic_measurement(**params):
    return tool_manager.tool_robotic_measurement(**params)


def tool_robotic_characterization(**params):
    return tool_manager.tool_robotic_characterization(**params)


def tool_scheduler_status(**_params):
    return tool_manager.runtime.get_runtime_status()


def tool_scheduler_advance(**params):
    return tool_manager.tool_scheduler_advance(**params)


def tool_scheduler_run_until_complete(**params):
    return tool_manager.tool_scheduler_run_until_complete(**params)


AVAILABLE_TOOLS_ACTION = {
    "robotic_reaction": tool_robotic_reaction,
    "robotic_measurement": tool_robotic_measurement,
    "robotic_characterization": tool_robotic_characterization,
    "scheduler_status": tool_scheduler_status,
    "scheduler_advance": tool_scheduler_advance,
    "scheduler_run_until_complete": tool_scheduler_run_until_complete,
}


def action_server_advertise_capabilities():
    adv_message = {
        "jsonrpc": "2.0",
        "method": "protocol/advertise",
        "params": {
            "type": "server",
            "server": {
                "protocolVersion": "0.1.0",
                "displayName": "Robotic Action Server",
                "capabilities": {
                    "tools": [
                        {
                            "name": "robotic_reaction",
                            "description": "Submit a reaction task into the scheduling runtime.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "recipe": {
                                        "type": "object",
                                        "description": "Reaction recipe, including optional estimated_duration.",
                                    },
                                    "vessel_id": {
                                        "type": "string",
                                        "description": "Target vessel identifier for this reaction.",
                                    },
                                },
                                "required": ["recipe", "vessel_id"],
                            },
                        },
                        {
                            "name": "robotic_measurement",
                            "description": "Submit a measurement task into the scheduling runtime.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "sample_id": {"type": "string", "description": "Sample identifier."},
                                    "measurement_type": {
                                        "type": "string",
                                        "description": "Measurement type such as yield or ph.",
                                    },
                                },
                                "required": ["sample_id", "measurement_type"],
                            },
                        },
                        {
                            "name": "robotic_characterization",
                            "description": "Submit a characterization task into the scheduling runtime.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "sample_id": {"type": "string", "description": "Sample identifier."},
                                    "analysis_method": {
                                        "type": "string",
                                        "description": "Characterization method such as HPLC or NMR.",
                                    },
                                },
                                "required": ["sample_id", "analysis_method"],
                            },
                        },
                        {
                            "name": "scheduler_status",
                            "description": "Inspect the current scheduler runtime state.",
                            "parameters": {
                                "type": "object",
                                "properties": {},
                                "required": [],
                            },
                        },
                        {
                            "name": "scheduler_advance",
                            "description": "Advance scheduler time by a given number of steps.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "steps": {
                                        "type": "integer",
                                        "description": "Number of scheduler time steps to advance.",
                                    }
                                },
                                "required": [],
                            },
                        },
                        {
                            "name": "scheduler_run_until_complete",
                            "description": "Run the scheduler until all known tasks complete or max_steps is reached.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "max_steps": {
                                        "type": "integer",
                                        "description": "Maximum number of scheduler time steps to run.",
                                    }
                                },
                                "required": [],
                            },
                        },
                    ]
                },
            },
        },
    }
    print(json.dumps(adv_message), flush=True)
    print("--- [MCP Server] Robotic Action Server is ready. ---", file=sys.stderr, flush=True)


def action_server_main_loop():
    for line in sys.stdin:
        request = {}
        try:
            request = json.loads(line)
            request_id = request.get("id")
            method_name = request.get("method")
            params = request.get("params", {})

            if method_name in AVAILABLE_TOOLS_ACTION:
                tool_function = AVAILABLE_TOOLS_ACTION[method_name]
                result = tool_function(**params)
                response = {"jsonrpc": "2.0", "result": result, "id": request_id}
            else:
                response = {
                    "jsonrpc": "2.0",
                    "error": {"code": -32601, "message": f"Method not found: {method_name}"},
                    "id": request_id,
                }

            print(json.dumps(response), flush=True)
        except Exception as exc:
            error_msg = {"code": -32603, "message": f"Internal error: {exc}"}
            response = {"jsonrpc": "2.0", "error": error_msg, "id": request.get("id")}
            print(json.dumps(response), flush=True)
            print(f"--- [MCP Server] Critical Error: {exc} ---", file=sys.stderr, flush=True)


if __name__ == "__main__":
    action_server_advertise_capabilities()
    action_server_main_loop()
