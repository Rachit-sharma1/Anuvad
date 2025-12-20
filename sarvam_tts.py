import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('SARVAM_API_KEY')
BASE_URL = os.getenv('BASE_URL', 'https://api.sarvam.ai')
TTS_MODEL = os.getenv('TTS_MODEL', 'bulbul:v2')
STT_MODEL = os.getenv('STT_MODEL', 'saarika:v2.5')
TRANSLATE_MODEL = os.getenv('TRANSLATE_MODEL', 'sarvam-translate:v1')
DEFAULT_SPEAKER = os.getenv('DEFAULT_SPEAKER', 'Anushka')
RECORD_DURATION = int(os.getenv('RECORD_DURATION', '5'))

def detect_language(text):
    url = f'{BASE_URL}/text/identify-language'
    headers = {
        'API-Subscription-Key': API_KEY,
        'Content-Type': 'application/json'
    }
    data = {
        'input': text
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        result = response.json()
        return result.get('language_code'), result.get('script_code')
    else:
        raise Exception(f"Language detection failed: {response.text}")

def generate_tts(text, language, speaker=None, model=None):
    if speaker is None:
        speaker = DEFAULT_SPEAKER
    if model is None:
        model = TTS_MODEL
    url = f'{BASE_URL}/text-to-speech/convert'
    headers = {
        'API-Subscription-Key': API_KEY,
        'Content-Type': 'application/json'
    }
    data = {
        'language': language,
        'inputs': [text],
        'speaker': speaker,
        'model': model
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        result = response.json()
        return result
    else:
        raise Exception(f"TTS failed: {response.text}")

def translate_text(text, source_lang='auto', target_lang='en-IN', model=None):
    if model is None:
        model = TRANSLATE_MODEL
    url = f'{BASE_URL}/text/translate'
    headers = {
        'API-Subscription-Key': API_KEY,
        'Content-Type': 'application/json'
    }
    data = {
        'input': text,
        'source_language_code': source_lang,
        'target_language_code': target_lang,
        'model': model
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        result = response.json()
        return result.get('translated_text')
    else:
        raise Exception(f"Translation failed: {response.text}")

def transcribe_audio(audio_data, language_code='unknown', model=None):
    if model is None:
        model = STT_MODEL
    # audio_data is bytes of wav
    url = f'{BASE_URL}/speech-to-text'
    headers = {
        'API-Subscription-Key': API_KEY
    }
    files = {
        'file': ('audio.wav', audio_data, 'audio/wav')
    }
    data = {
        'language_code': language_code,
        'model': model
    }
    response = requests.post(url, headers=headers, files=files, data=data)
    if response.status_code == 200:
        result = response.json()
        return result.get('transcript'), result.get('language_code')
    else:
        raise Exception(f"STT failed: {response.text}")

def record_audio(duration=None, sample_rate=16000):
    import pyaudio
    import wave
    import io
    import webrtcvad
    
    vad = webrtcvad.Vad(3)  # Aggressive mode for better silence detection
    chunk_frames = int(sample_rate * 0.02)  # 20ms chunk
    silence_threshold = 1.0  # seconds of silence to stop
    max_record_time = 30  # max seconds to record
    
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paInt16, channels=1, rate=sample_rate, input=True, frames_per_buffer=chunk_frames)
    print("Listening for speech...")
    
    frames = []
    speech_started = False
    silence_duration = 0.0
    recorded_time = 0.0
    
    while recorded_time < max_record_time:
        data = stream.read(chunk_frames)
        recorded_time += 0.02
        
        try:
            is_speech = vad.is_speech(data, sample_rate)
        except:
            is_speech = False  # If VAD fails, treat as no speech
        
        if is_speech:
            if not speech_started:
                print("Speech detected, recording...")
                speech_started = True
            silence_duration = 0.0
            frames.append(data)
        elif speech_started:
            silence_duration += 0.02
            frames.append(data)
            if silence_duration >= silence_threshold:
                print("Silence detected, stopping recording.")
                break
        # If not speech_started, don't append, just listen
    
    stream.stop_stream()
    stream.close()
    p.terminate()
    
    if not frames:
        print("No speech detected.")
        return None
    
    # Convert to wav bytes
    buffer = io.BytesIO()
    wf = wave.open(buffer, 'wb')
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(sample_rate)
    wf.writeframes(b''.join(frames))
    wf.close()
    print(f"Recorded {len(frames) * 0.02:.1f} seconds of audio.")
    return buffer.getvalue()

def play_audio(base64_audio):
    import base64
    import winsound
    audio_bytes = base64.b64decode(base64_audio)
    with open('output.wav', 'wb') as f:
        f.write(audio_bytes)
    # Play on Windows
    winsound.PlaySound('output.wav', winsound.SND_FILENAME)

def conversation_loop():
    while True:
        audio_data = record_audio()
        transcript, detected_lang = transcribe_audio(audio_data)
        if not transcript:
            continue
        translated_text = translate_text(transcript, source_lang=detected_lang, target_lang='en-IN')
        # Translate back to detected_lang
        back_translated = translate_text(translated_text, source_lang='en-IN', target_lang=detected_lang)
        # TTS
        tts_result = generate_tts(back_translated, detected_lang)
        play_audio(tts_result['audio'])
        # JSON
        output_json = {
            'transcript': transcript,
            'detected_language': detected_lang,
            'translated_text': translated_text,
            'back_translated': back_translated,
            'tts_audio_base64': tts_result['audio']
        }
        print(json.dumps(output_json))

def main(text):
    detected_lang, script = detect_language(text)
    language_variable = detected_lang  # pass to variable
    tts_result = generate_tts(text, detected_lang)
    output_json = {
        'detected_text': text,
        'detected_language': detected_lang,
        'script': script,
        'tts_audio_base64': tts_result.get('audio')  # assuming the key is 'audio'
    }
    print(json.dumps(output_json))
    return output_json

if __name__ == '__main__':
    sample_text = "Hello, how are you?"
    main(sample_text)
