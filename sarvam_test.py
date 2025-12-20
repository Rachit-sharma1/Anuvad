import requests
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('SARVAM_API_KEY')
BASE_URL = os.getenv('BASE_URL', 'https://api.sarvam.ai')

def get_sarvam_response(query, model='sarvam-m'):
    url = f"{BASE_URL}/v1/chat/completions"
    headers = {
        'API-Subscription-Key': API_KEY,
        'Content-Type': 'application/json'
    }
    data = {
        'model': model,
        'messages': [
            {'role': 'user', 'content': query}
        ]
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        result = response.json()
        return result['choices'][0]['message']['content']
    else:
        raise Exception(f"Sarvam API error: {response.text}")

if __name__ == "__main__":
    sample_query = "What is the capital of France?"
    result = get_sarvam_response(sample_query)
    print(f"Query: {sample_query}")
    print(f"Response: {result}")
