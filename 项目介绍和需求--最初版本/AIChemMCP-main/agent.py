# agent.py
import subprocess
import json
import sys
import time
from threading import Thread
from llm_client import OpenAI_LLM


class Agent:
    def __init__(self):
        self.servers = {}
        self.tools = {}
        self.history = []
        self.llm_client = OpenAI_LLM()

    def start_server(self, name: str, command: list):
        """Start a server subprocess and manage its IO pipes."""
        print(f"[AGENT] Starting server: {name}...")
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        self.servers[name] = {
            "process": process,
            "stdin": process.stdin,
            "stdout": process.stdout,
        }
        Thread(target=self._log_stderr, args=(name, process.stderr), daemon=True).start()
        print(f"[AGENT] Server '{name}' started.")

    def _log_stderr(self, name, stderr_pipe):
        """Print server stderr logs in a background thread."""
        for line in iter(stderr_pipe.readline, ''):
            print(f"[{name} LOG] {line.strip()}", file=sys.stderr)

    def discover_tools(self):
        """Read advertise messages from all started servers and build the tool table."""
        print("\n[AGENT] Discovering tools from all servers...")
        for name, server in self.servers.items():
            adv_line = server['stdout'].readline()
            adv_data = json.loads(adv_line)

            server_tools = adv_data.get("params", {}).get("server", {}).get("capabilities", {}).get("tools", [])
            for tool in server_tools:
                tool_name = tool['name']
                self.tools[tool_name] = tool
                self.tools[tool_name]['server_name'] = name
            print(f"[AGENT] Discovered {len(server_tools)} tools from '{name}'.")
        print(f"[AGENT] Tool discovery complete. Total tools available: {len(self.tools)}")

    def build_system_prompt(self) -> str:
        """Build a system prompt containing role, tool list and SOPs."""
        prompt = "# Role and Goal\n"
        prompt += "You are a top-level AI research chemist. Your task is to use automated laboratory tools safely and efficiently.\n\n"

        prompt += "# Available Tools\n---\n"
        for name, tool in self.tools.items():
            prompt += f"- Tool: {name}\n"
            prompt += f"  - Description: {tool['description']}\n"
            prompt += f"  - Parameters: {json.dumps(tool['parameters'])}\n"
        prompt += "---\n\n"

        prompt += "# SOPs & Best Practices\n"
        prompt += "When you need to execute an optimization task, a standard Bayesian optimization loop is recommended.\n"
        prompt += "1. Initialize if needed.\n"
        prompt += "2. Suggest the next experiment.\n"
        prompt += "3. Execute it through robotic tools.\n"
        prompt += "4. Observe and feed results back.\n"
        prompt += "5. Repeat until the goal is met.\n"

        return prompt

    def dispatch_tool_call(self, tool_call: dict) -> dict:
        """Dispatch a tool call to the correct server and return its response."""
        method = tool_call.get("method")
        if not method or method not in self.tools:
            return {"error": f"Tool '{method}' not found."}

        server_name = self.tools[method]['server_name']
        server = self.servers[server_name]

        request_id = int(time.time() * 1000)
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": tool_call.get("params", {}),
            "id": request_id
        }

        print(f"[AGENT] -> [{server_name}] {json.dumps(request)}")
        server['stdin'].write(json.dumps(request) + '\n')
        server['stdin'].flush()

        while True:
            response_line = server['stdout'].readline()
            if not response_line:
                return {"error": "Server connection closed."}
            response = json.loads(response_line)
            if response.get("id") == request_id:
                print(f"[AGENT] <- [{server_name}] {json.dumps(response)}")
                return response

    def build_planner_system_prompt(self) -> str:
        """Build the planner prompt."""
        prompt = "# Role and Goal\n"
        prompt += "You are an expert laboratory workflow planner. Build an ordered tool plan to satisfy the user's goal.\n\n"

        prompt += "# Available Tools\n---\n"
        for name, tool in self.tools.items():
            prompt += f"- {name}: {tool['description']}\n"
        prompt += "---\n\n"

        prompt += "# Task\n"
        prompt += "Analyze the user's goal and generate a full workflow plan, then submit it through `submit_workflow_plan`.\n"
        return prompt

    def plan_workflow(self, user_goal: str) -> list:
        """Planning stage: call the LLM to generate a multi-step plan."""
        print("\n[AGENT] Entering PLANNING stage...")
        system_prompt = self.build_planner_system_prompt()
        plan = self.llm_client.generate_plan(system_prompt, user_goal, self.tools)

        print("[AGENT] Plan generated successfully.")
        return plan

    def run(self):
        """Start the main interactive loop."""
        system_prompt = self.build_system_prompt()
        self.history.append({"role": "system", "content": system_prompt})

        print("\n--- Agent is Ready ---")
        print("System Prompt has been constructed. You can now interact with the agent.")
        print("Try typing: 'Please optimize the reaction yield.'")

        while True:
            user_input = input("\nYou: ")
            if user_input.lower() in ["exit", "quit"]:
                for server in self.servers.values():
                    server['process'].terminate()
                print("[AGENT] All servers terminated. Exiting.")
                break

            self.history.append({"role": "user", "content": user_input})

            print("[AGENT] Thinking with OpenAI...")
            llm_response = self.llm_client.get_decision(
                system_prompt,
                self.history,
                self.tools
            )
            print(f"[LLM] Thought: {llm_response.get('thought')}")
            self.history.append({"role": "assistant", "content": llm_response})

            if "tool_call" in llm_response:
                tool_call = llm_response['tool_call']
                print(f"[AGENT] Dispatching tool call: {tool_call.get('method')}")

                result = self.dispatch_tool_call(tool_call)
                self.history.append({"role": "tool_result", "content": result})
                print(f"[AGENT] Tool execution result: {result}")

                print("[AGENT] Thinking about the result...")
                next_llm_response = self.llm_client.get_decision(system_prompt, self.history, self.tools)
                print(f"[LLM] Next Thought: {next_llm_response.get('thought')}")
                if "speak" in next_llm_response:
                    print(f"\nAgent: {next_llm_response['speak']}")
            elif "speak" in llm_response:
                print(f"\nAgent: {llm_response['speak']}")


if __name__ == "__main__":
    agent = Agent()
    agent.start_server("BO_Server", ["python", "dummy_planner_servers/dummy_bo_server.py"])
    time.sleep(1)
    agent.discover_tools()
    user_goal = "I want to plan a Bayesian optimization workflow with three cycles."
    plan = agent.plan_workflow(user_goal)
    print(plan)
