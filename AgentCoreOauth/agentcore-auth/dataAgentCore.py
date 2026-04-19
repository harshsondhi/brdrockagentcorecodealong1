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


data_agent = Agent(
    name="DataAgent",
    instructions=(
        f"{RECOMMENDED_PROMPT_PREFIX}\n"
        "You are Lt. Commander Data from Star Trek: TNG. Be precise and concise (≤3 sentences).\n"
        "Use file_search for questions about Commander Data, and web_search for current facts on the public web.\n"
        "If the user asks for arithmetic or numeric computation, HAND OFF to the Calculator agent."
    ),
    tools=[web_search, file_search],
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
        result = await Runner.run(data_agent, user_message)
        output = result.final_output
    except InputGuardrailTripwireTriggered as e:
        output = f"Input blocked by guardrail: {e}"
    except Exception as e:
        output = f"Error processing request: {e}"
        
    return {"result": output}    



if __name__ == "__main__":
    app.run()