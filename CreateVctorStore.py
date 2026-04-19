import os, re
from pathlib import Path
from openai import OpenAI
from agents import set_default_openai_api


def load_local_env() -> None:
	env_path = Path(__file__).resolve().parent / ".env"
	if not env_path.exists():
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


def mask_secret(secret: str) -> str:
	if len(secret) <= 12:
		return "<set>"
	return f"{secret[:8]}...{secret[-4:]}"


load_local_env()
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
	raise RuntimeError(
		"OPENAI_API_KEY is not set. Add it to .env or export it in your shell."
	)

print(f"Using API key: {mask_secret(api_key)}")
client = OpenAI(api_key = api_key)

CORPUS_PATH = "./data_lines.txt"

vs = client.vector_stores.create(
    name="my_vector_store",     
)

# 1) Upload to Files API
uploaded = client.files.create(
    file=open(CORPUS_PATH, "rb"),
    purpose="assistants",                # important
)

# 2) Attach & poll on the vector store
vs_file = client.vector_stores.files.create_and_poll(
    vector_store_id=vs.id,
    file_id=uploaded.id,
)
print("vs_file.status:", vs_file.status)
print("vs_file.last_error:", getattr(vs_file, "last_error", None))
