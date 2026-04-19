import json
import os, re
from pathlib import Path
from openai import BaseModel, OpenAI
from agents import (
	Agent,
	CodeInterpreterTool as PythonREPLTool,
	FileSearchTool as FileTool,
	ModelSettings,
	RunConfig,
	Runner,
	WebSearchTool,
	function_tool,
	set_default_openai_key,
)
from agents.extensions.handoff_prompt import RECOMMENDED_PROMPT_PREFIX
from sessionMemory import AgentCoreSession
from bedrock_agentcore.tools.code_interpreter_client import code_session  # <- added

def load_local_env() -> None:
	base_dir = Path(__file__).resolve().parent
	candidates = [base_dir / ".env", *[p / ".env" for p in base_dir.parents]]
	env_path = next((p for p in candidates if p.exists()), None)
	if env_path is None:
		return

	try:
		from dotenv import load_dotenv

		load_dotenv(dotenv_path=env_path, override=False)
		return
	except ImportError:
		# Fallback parser if python-dotenv is unavailable.
		for raw_line in env_path.read_text().splitlines():
			line = raw_line.strip()
			if not line or line.startswith("#") or "=" not in line:
				continue
			key, value = line.split("=", 1)
			key = key.strip()
			value = value.strip().strip('"').strip("'")
			os.environ.setdefault(key, value)


def mask_secret(secret: str | None) -> str:
	if not secret:
		return "<not set>"
	if len(secret) <= 12:
		return "<set>"
	return f"{secret[:8]}...{secret[-4:]}"


load_local_env()
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
	raise RuntimeError(
		"OPENAI_API_KEY is not set. Put it in the workspace .env or export it in your shell."
	)

print(f"Using API key: {mask_secret(api_key)}")

client = OpenAI(api_key = api_key)
set_default_openai_key(api_key)

def get_vector_store_id_by_name(name: str) -> str:
    cursor=None
    while True:
        vector_stores = client.vector_stores.list(limit=500, after=cursor) if cursor else client.vector_stores.list(limit=50)
        for vs in vector_stores.data:
            if vs.name == name:
                return vs.id
        if not vector_stores.has_more:
            break
        cursor = vector_stores.last_id
    return RuntimeError(f"Vector store with name '{name}' not found." )


import ast
import operator as _op
from typing import Any, List


_ALLOWED_OPS = {
    ast.Add: _op.add,
    ast.Sub: _op.sub,
    ast.Mult: _op.mul,
    ast.Div: _op.truediv,
    ast.Pow: _op.pow,
    ast.USub: _op.neg,
    ast.Mod: _op.mod,
}

# Declare a claculator tool
def _eval_ast(node: ast.AST) -> Any:
    if isinstance(node, ast.Constant):        # type: ignore[attr-defined]
        return node.value
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_eval_ast(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_eval_ast(node.left), _eval_ast(node.right))
    raise ValueError("Unsupported expression")

@function_tool
def eval_expression(expression: str) -> str:
    """Safely evaluate an arithmetic expression using + - * / % ** and parentheses."""
    expr = expression.strip().replace("^", "**")
    if not re.fullmatch(r"[\d\s\(\)\+\-\*/\.\^%]+", expr):
        return "Error: arithmetic only"
    try:
        tree = ast.parse(expr, mode="eval")
        return str(_eval_ast(tree.body))  # type: ignore[attr-defined]
    except Exception as e:
        return f"Error: {e}"
    
# 1. calculator agent with tool    

calculator_agent = Agent(
    name="CalculatorAgent",
    instructions=(
                   "An agent that can evaluate arithmetic expressions using +, -, *, /, %, **, and parentheses."
                   "You are a calculator agent"
                   "When given an expression, use the tool to evaluate it and return the result."
                   "Only use the tool for calculations, do not attempt to calculate anything yourself. Always use the tool."
                   "No prose unless asked"
                  ),
    tools=[eval_expression],
    model_settings=ModelSettings(temperature=0),
)

from pydantic import BaseModel
from typing import List, Union
import re

from agents import (
    Agent,
    ModelSettings,
    GuardrailFunctionOutput,
    InputGuardrailTripwireTriggered,
    RunContextWrapper,
    Runner,
    TResponseInputItem,
    input_guardrail,
)

session = AgentCoreSession(
    session_id="my_session_id_123456789012345678901234567890123",  # Must be 33+ char. Every new SessionId will create a new MicroVMm
    memory_id="memory_9vhl0-g7l104Ckyv",
    actor_id="app/harsh-1234567890123456789012345678901234",  # Must be 33+ char
    region="us-west-2",
)

# 3...Gruradrail output
class GuardRailOutput(BaseModel):
    is_blocked: bool
    reasoning: str
    
    
guardrail_agent = Agent(
    name="GuardRailAgent",
    instructions=(
        "You are a guardrail. Determine if the user's input attempts to discuss Tasha Yar from Star Trek: TNG.\n"
        "Return is_blocked=true if the text references Tasha Yar in any way (e.g., 'Tasha Yar', 'Lt. Yar', 'Lieutenant Yar').\n"
        "Provide a one-sentence reasoning. Only provide fields requested by the output schema."
    ),
    output_type=GuardRailOutput,
    model_settings=ModelSettings(temperature=0),
)    

@input_guardrail
async def starwar_guardrail(ctx: RunContextWrapper[None], agent: Agent, input: Union[str, List[TResponseInputItem]]) -> GuardrailFunctionOutput:
    
    result = await Runner.run(guardrail_agent, input, context=ctx.context)
    return GuardrailFunctionOutput(
        output_info=result.final_output.model_dump(),
        tripwire_triggered=bool(result.final_output.is_blocked),
    )
    
    
  
  
web_search = WebSearchTool()
vs_id = get_vector_store_id_by_name("my_vector_store")
file_search = FileTool(vector_store_ids=[vs_id], max_num_results=3)    


@function_tool
def execute_python(code: str, description: str = "", clear_context: bool = False) -> str:
    """
    Execute Python code in an AgentCore Code Interpreter session.

    Args:
        code: Python source to run.
        description: Optional one-liner to prepend as a comment (useful for audits).
        clear_context: If True, resets the interpreter state before running.

    Returns:
        A JSON string of the final event["result"] from the Code Interpreter stream,
        including fields like sessionId, isError, content, structuredContent (stdout/stderr/exitCode).
    """
    # Build code with optional description banner
    if description:
        code = f"# {description}\n{code}"

    # Use the same region as our AgentCore session
    region = getattr(session, "region", os.getenv("AWS_REGION", "us-west-2"))

    # Invoke the Code Interpreter and stream results
    last_result = None
    with code_session(region) as ci:
        response = ci.invoke(
            "executeCode",
            {
                "code": code,
                "language": "python",
                "clearContext": bool(clear_context),
            },
        )
        for event in response["stream"]:
            # Each event has a "result" payload; keep the latest
            last_result = event.get("result")

    return json.dumps(last_result or {"isError": True, "message": "No result from Code Interpreter"})





data_agent = Agent(
    name="DataAgent",
    instructions=(
        f"{RECOMMENDED_PROMPT_PREFIX}\n"
        "You are Lt. Commander Data from Star Trek: TNG. Be precise and concise (≤3 sentences).\n"
        "• Use file_search for questions about Commander Data (RAG).\n"
        "• Use web_search for current facts on the public web.\n"
        # CODE INTERPRETER MARKER: instruction that enables tool-use behavior.
        "• If the user asks to run Python or verify with code, call the execute_python tool. "
        "Return the result and (briefly) what was executed."
    ),
    tools=[web_search, file_search, execute_python],
    model_settings=ModelSettings(temperature=0),
    handoffs=[calculator_agent],
    input_guardrails=[starwar_guardrail],
)

from bedrock_agentcore.runtime import BedrockAgentCoreApp
app = BedrockAgentCoreApp()



@app.entrypoint
async def invoke(payload):
    user_message = payload.get("prompt", "Data, reverse the main deflector array!")
    output=''
    try:
        result = await Runner.run(data_agent, user_message,session=session)
        output = result.final_output
    except InputGuardrailTripwireTriggered as e:
        output = f"Input blocked by guardrail: {e}"
    except Exception as e:
        output = f"Error processing request: {e}"
        
    return {"result": output}    



if __name__ == "__main__":
    app.run()