import os
from dotenv import load_dotenv
import requests
import json

load_dotenv()

API_KEY = os.getenv('SARVAM_API_KEY')
BASE_URL = os.getenv('BASE_URL', 'https://api.sarvam.ai')
MODEL = os.getenv('SARVAM_MODEL', 'sarvam-m')

def get_sarvam_response(query):
    url = f"{BASE_URL}/v1/chat/completions"
    headers = {
        'API-Subscription-Key': API_KEY,
        'Content-Type': 'application/json'
    }
    data = {
        'model': MODEL,
        'messages': [
            {'role': 'user', 'content': query}
        ],
        'temperature': 1,
        'max_tokens': 8192,
        'top_p': 1,
        'stream': True,
        'stop': None
    }
    response = requests.post(url, headers=headers, json=data, stream=True)
    if response.status_code == 200:
        result = ""
        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith('data: '):
                    data_str = line[6:]
                    if data_str == '[DONE]':
                        break
                    try:
                        chunk = json.loads(data_str)
                        content = chunk.get('choices', [{}])[0].get('delta', {}).get('content', '')
                        print(content, end="")
                        result += content
                    except:
                        pass
        print()  # newline
        return result
    else:
        raise Exception(f"Sarvam API error: {response.text}")

if __name__ == "__main__":
    sample_query = "What is the capital of France?"
    print(f"Query: {sample_query}")
    print("Response:", end=" ")
    result = get_sarvam_response(sample_query)
