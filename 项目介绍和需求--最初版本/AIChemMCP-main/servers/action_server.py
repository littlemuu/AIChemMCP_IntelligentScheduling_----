import sys
import json
from tools.action_server_tools import ActionServerTools


tool_manager = ActionServerTools()


def tool_robotic_reaction():
    return tool_manager.tool_robotic_reaction()


def tool_robotic_measurement():
    return tool_manager.tool_robotic_measurement()


def tool_robotic_characterization():
    return tool_manager.tool_robotic_characterization()


AVAILABLE_TOOLS_ACTION = {
    "robotic_reaction": tool_robotic_reaction,
    "robotic_measurement": tool_robotic_measurement,
    "robotic_characterization": tool_robotic_characterization,
}


def action_server_advertise_capabilities():
    """Advertise all robotic actions provided by the server."""
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
                            "description": "Command the robot to execute a chemical reaction and return a new sample id.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "recipe": {"type": "object", "description": "Reaction recipe."},
                                    "vessel_id": {"type": "string", "description": "Reaction vessel id."}
                                },
                                "required": ["recipe", "vessel_id"]
                            }
                        },
                        {
                            "name": "robotic_measurement",
                            "description": "Command the robot to perform a quick measurement such as yield or pH.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "sample_id": {"type": "string", "description": "Sample id."},
                                    "measurement_type": {"type": "string", "description": "Measurement type."}
                                },
                                "required": ["sample_id", "measurement_type"]
                            }
                        },
                        {
                            "name": "robotic_characterization",
                            "description": "Command the robot to run a characterization analysis such as HPLC or NMR.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "sample_id": {"type": "string", "description": "Sample id."},
                                    "analysis_method": {"type": "string", "description": "Analysis method."}
                                },
                                "required": ["sample_id", "analysis_method"]
                            }
                        }
                    ]
                }
            }
        }
    }
    print(json.dumps(adv_message), flush=True)
    print("--- [MCP Server] Robotic Action Server is ready. ---", file=sys.stderr, flush=True)


def action_server_main_loop():
    """Main loop: listen for and respond to host requests."""
    for line in sys.stdin:
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
                response = {"jsonrpc": "2.0", "error": {"code": -32601, "message": f"Method not found: {method_name}"},
                            "id": request_id}

            print(json.dumps(response), flush=True)
        except Exception as e:
            error_msg = {"code": -32603, "message": f"Internal error: {e}"}
            response = {"jsonrpc": "2.0", "error": error_msg, "id": request.get("id")}
            print(json.dumps(response), flush=True)
            print(f"--- [MCP Server] Critical Error: {e} ---", file=sys.stderr, flush=True)


if __name__ == "__main__":
    action_server_advertise_capabilities()
    action_server_main_loop()
