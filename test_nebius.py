import os
from openai import OpenAI

client = OpenAI(
    base_url="https://api.tokenfactory.nebius.com/v1/",
    api_key=os.environ["NEBIUS_API_KEY"],
)

MODEL = "nvidia/Nemotron-3_5-Lightning"

resp = client.chat.completions.create(
    model=MODEL,
    messages=[{"role": "user", "content": "In one sentence, what is git bisect?"}],
    max_tokens=300,
)
print(resp.choices[0].message.content)
print(resp.usage)
