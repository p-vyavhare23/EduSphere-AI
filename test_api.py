import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError(
        "GEMINI_API_KEY is missing. Check your .env file."
    )

client = genai.Client(api_key=api_key)

try:
    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents="Explain prompt engineering in two sentences."
    )

    print("Gemini API connected successfully!")
    print(response.text)

except Exception as error:
    print("Gemini API request failed.")
    print(f"Error: {error}")