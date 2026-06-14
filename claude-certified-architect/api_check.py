import sys
import anthropic
from dotenv import load_dotenv

# Force the terminal to accept unicode output


load_dotenv()
client = anthropic.Anthropic()

response = client.messages.create(
    model="claude-3-5-haiku-20241022",
    max_tokens=100,
    messages=[
        {"role": "user", "content": "Say hello in one word."}
    ]
)

# Extract text correctly from the response block object
print(response.content[0].text)