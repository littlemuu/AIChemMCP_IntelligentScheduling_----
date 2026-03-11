# agent.py
import json
import subprocess
import sys
import time
from itertools import count
from threading import Thread

try:
    from llm_client import OpenAI_LLM
except Exception:
    OpenAI_LLM = None


class Agent:
    def __init__(self, enable_llm: bool = True):
        self.servers = {}
        self.tools = {}
        self.history = []
        self.llm_client = None
        self._request_ids = count(1)

        if enable_llm and OpenAI_LLM is not None:
            try:
                self.llm_client = OpenAI_LLM()
            except Exception as exc:
                print(f"[AGENT] LLM disabled: {exc}")

    def start_server(self, name: str, command: list):
        print(f"[AGENT] Starting server: {name}...")
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )
        self.servers[name] = {
            "process": process,
            "stdin": process.stdin,
            "stdout": process.stdout,
        }
        Thread(target=self._log_stderr, args=(name, process.stderr), daemon=True).start()
        print(f"[AGENT] Server '{name}' started.")

    def start_default_servers(self):
        self.start_server("BO_Server", ["python", "dummy_planner_servers/dummy_bo_server.py"])
        self.start_server("Action_Server", ["python", "servers/action_server.py"])

    def shutdown_servers(self):
        for server in self.servers.values():
            if server["process"].poll() is None:
                server["process"].terminate()

    def _log_stderr(self, name, stderr_pipe):
        for line in iter(stderr_pipe.readline, ""):
            print(f"[{name} LOG] {line.strip()}", file=sys.stderr)

    def discover_tools(self):
        print("\n[AGENT] Discovering tools from all servers...")
        for name, server in self.servers.items():
            adv_line = server["stdout"].readline()
            adv_data = json.loads(adv_line)

            server_tools = adv_data.get("params", {}).get("server", {}).get("capabilities", {}).get("tools", [])
            for tool in server_tools:
                tool_name = tool["name"]
                self.tools[tool_name] = tool
                self.tools[tool_name]["server_name"] = name
            print(f"[AGENT] Discovered {len(server_tools)} tools from '{name}'.")
        print(f"[AGENT] Tool discovery complete. Total tools available: {len(self.tools)}")

    def dispatch_tool_call(self, tool_call: dict) -> dict:
        method = tool_call.get("method")
        if not method or method not in self.tools:
            return {"error": f"Tool '{method}' not found."}

        server_name = self.tools[method]["server_name"]
        server = self.servers[server_name]
        request_id = next(self._request_ids)
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": tool_call.get("params", {}),
            "id": request_id,
        }

        print(f"[AGENT] -> [{server_name}] {json.dumps(request, ensure_ascii=False)}")
        server["stdin"].write(json.dumps(request, ensure_ascii=False) + "\n")
        server["stdin"].flush()

        while True:
            response_line = server["stdout"].readline()
            if not response_line:
                return {"error": "Server connection closed."}
            response = json.loads(response_line)
            if response.get("id") == request_id:
                print(f"[AGENT] <- [{server_name}] {json.dumps(response, ensure_ascii=False)}")
                return response

    def build_system_prompt(self) -> str:
        prompt = "# Role And Goal\n"
        prompt += "You are an AI laboratory orchestration agent.\n\n"
        prompt += "# Available Tools\n---\n"
        for name, tool in self.tools.items():
            prompt += f"- Tool: {name}\n"
            prompt += f"  - Description: {tool['description']}\n"
            prompt += f"  - Parameters: {json.dumps(tool['parameters'])}\n"
        prompt += "---\n"
        return prompt

    def execute_plan(self, plan: list) -> list:
        results = []
        for step in plan:
            result = self.dispatch_tool_call(step)
            results.append(
                {
                    "method": step.get("method"),
                    "params": step.get("params", {}),
                    "response": result,
                }
            )
        return results

    def demo_action_flow(self) -> list:
        demo_plan = [
            {
                "method": "robotic_reaction",
                "params": {
                    "recipe": {"name": "demo_reaction", "estimated_duration": 180},
                    "vessel_id": "vessel_A",
                },
            },
            {
                "method": "robotic_measurement",
                "params": {
                    "sample_id": "SAMPLE-0001",
                    "measurement_type": "yield",
                },
            },
            {
                "method": "scheduler_status",
                "params": {},
            },
            {
                "method": "scheduler_run_until_complete",
                "params": {"max_steps": 500},
            },
            {
                "method": "scheduler_status",
                "params": {},
            },
        ]
        return self.execute_plan(demo_plan)

    def plan_workflow(self, user_goal: str) -> list:
        if self.llm_client is None:
            raise RuntimeError("LLM client is not available.")
        print("\n[AGENT] Entering PLANNING stage...")
        system_prompt = self.build_system_prompt()
        plan = self.llm_client.generate_plan(system_prompt, user_goal, self.tools)
        print("[AGENT] Plan generated successfully.")
        return plan

    def run(self):
        if self.llm_client is None:
            raise RuntimeError("LLM client is not available.")

        system_prompt = self.build_system_prompt()
        self.history.append({"role": "system", "content": system_prompt})

        print("\n--- Agent is Ready ---")
        while True:
            user_input = input("\nYou: ")
            if user_input.lower() in ["exit", "quit"]:
                self.shutdown_servers()
                print("[AGENT] All servers terminated. Exiting.")
                break

            self.history.append({"role": "user", "content": user_input})
            llm_response = self.llm_client.get_decision(system_prompt, self.history, self.tools)
            print(f"[LLM] Thought: {llm_response.get('thought')}")
            self.history.append({"role": "assistant", "content": llm_response})

            if "tool_call" in llm_response:
                tool_call = llm_response["tool_call"]
                result = self.dispatch_tool_call(tool_call)
                self.history.append({"role": "tool_result", "content": result})
                print(f"[AGENT] Tool execution result: {result}")
            elif "speak" in llm_response:
                print(f"\nAgent: {llm_response['speak']}")


if __name__ == "__main__":
    agent = Agent(enable_llm=False)
    try:
        agent.start_default_servers()
        time.sleep(1)
        agent.discover_tools()
        demo_results = agent.demo_action_flow()
        print("\n[AGENT DEMO] End-to-end results:")
        print(json.dumps(demo_results, indent=2, ensure_ascii=False))
    finally:
        agent.shutdown_servers()
