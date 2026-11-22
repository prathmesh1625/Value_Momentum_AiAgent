"""Print the models your Groq key can use (Groq retires models from time to time)."""
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
for m in sorted(Groq().models.list().data, key=lambda m: m.id):
    print(m.id, getattr(m, "context_window", "?"))
