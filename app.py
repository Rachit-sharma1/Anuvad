from flask import Flask, request, jsonify, render_template
from conversation_agent import process_voice_query
import base64
import logging

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.DEBUG)
app.logger.setLevel(logging.DEBUG)

@app.route('/')
def index():
    app.logger.debug("Serving index page")
    return render_template('index.html')

@app.route('/process_voice', methods=['POST'])
def process_voice():
    app.logger.debug("Received POST to /process_voice")
    if 'audio' not in request.files:
        app.logger.error("No audio file in request")
        return jsonify({'error': 'No audio file'}), 400
    audio_file = request.files['audio']
    audio_data = audio_file.read()
    app.logger.debug(f"Audio data length: {len(audio_data)} bytes")
    try:
        app.logger.debug("Calling process_voice_query")
        assistant_text, audio_b64, user_text, lang = process_voice_query(audio_data)
        app.logger.debug(
            "process_voice_query returned: "
            f"user_text length {len(user_text)}, assistant_text length {len(assistant_text)}, "
            f"lang {lang}, audio_b64 length {len(audio_b64) if audio_b64 else 0}"
        )
        return jsonify({'user': user_text, 'response': assistant_text, 'audio': audio_b64, 'lang': lang})
    except Exception as e:
        app.logger.error(f"Error in process_voice_query: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
