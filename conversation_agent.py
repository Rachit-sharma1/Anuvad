import os
from dotenv import load_dotenv
import chromadb
import requests
import json
import openai
import logging
import time
import random
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

load_dotenv()

api_key = os.getenv('SARVAM_API_KEY')
base_url = os.getenv('BASE_URL', 'https://api.sarvam.ai')
openai_api_key = os.getenv('OPENAI_API_KEY')
openai_model = os.getenv('OPENAI_MODEL', 'gpt-4o')

SUPPORTED_LANG_CODES = {
    "as-IN", "bn-IN", "brx-IN", "doi-IN", "en-IN", "gu-IN", "hi-IN", "kn-IN", "kok-IN",
    "ks-IN", "mai-IN", "ml-IN", "mni-IN", "mr-IN", "ne-IN", "od-IN", "pa-IN", "sa-IN",
    "sat-IN", "sd-IN", "ta-IN", "te-IN", "ur-IN",
}

USER_STATE = {
    "profile": {},
    "contradictions": [],
}

def _load_json_file(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except Exception as e:
        logging.error(f"Failed to load JSON {path}: {e}")
        return None

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
_SCHEMES_PATH = os.path.join(_DATA_DIR, "schemes.json")
_PERSONAS_PATH = os.path.join(_DATA_DIR, "personas.json")
_TOOLS_PATH = os.path.join(_DATA_DIR, "tools.json")

_schemes_doc = _load_json_file(_SCHEMES_PATH) or {}
SCHEME_CATALOG = _schemes_doc.get("schemes", []) if isinstance(_schemes_doc, dict) else []

_personas_doc = _load_json_file(_PERSONAS_PATH) or {}
SWAYAM_PERSONA = None
if isinstance(_personas_doc, dict):
    SWAYAM_PERSONA = (_personas_doc.get("personas") or {}).get("swayam")

_tools_doc = _load_json_file(_TOOLS_PATH) or {}
TOOLS_SCHEMA = _tools_doc.get("tools", []) if isinstance(_tools_doc, dict) else []

SUPPORTED_TTS_SPEAKERS = {
    "anushka", "abhilash", "manisha", "vidya", "arya", "karun", "hitesh",
    "aditya", "ritu", "chirag", "priya", "neha", "rahul", "pooja", "rohan",
    "simran", "kavya", "sunita", "tara", "anirudh", "anjali", "ishaan", "ratan",
    "varun", "manan", "sumit", "roopa", "kabir", "aayan", "shubh",
}

# OpenAI client
client = openai.OpenAI(api_key=openai_api_key)

# Vector store for memory
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection(name="conversation_memory")

def openai_chat(messages, tools=None):
    logging.debug("Entering openai_chat")
    logging.debug(f"Messages: {messages}")
    logging.debug(f"Tools: {tools}")
    kwargs = {
        "model": openai_model,
        "messages": messages
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    response = client.chat.completions.create(**kwargs)
    logging.debug(f"OpenAI response: {response}")
    return response

# Tools
def web_search(query):
    logging.debug(f"Entering web_search with query: {query}")

    # ---- Rate-limit protection + caching (process-wide) ----
    # NOTE: Parallel requests generally increase rate-limits; we only do a guarded "race" when not in cooldown.
    if not hasattr(web_search, "_lock"):
        web_search._lock = threading.Lock()
        web_search._cache = {}  # query -> (ts, result_str)
        web_search._cooldown_until = 0.0
        web_search._last_request_ts = 0.0
        web_search._ratelimit_hits = 0

    now = time.time()
    cache_ttl_s = int(os.getenv("WEB_SEARCH_CACHE_TTL_SECONDS", "900"))
    min_interval_s = float(os.getenv("WEB_SEARCH_MIN_INTERVAL_SECONDS", "2.5"))
    cooldown_s = int(os.getenv("WEB_SEARCH_COOLDOWN_SECONDS", "120"))
    enable_race = os.getenv("WEB_SEARCH_PARALLEL_BACKEND_RACE", "0") == "1"

    qkey = query.strip().lower()
    with web_search._lock:
        cached = web_search._cache.get(qkey)
        if cached and (now - cached[0]) <= cache_ttl_s:
            logging.debug("web_search cache hit")
            return cached[1]

        if now < web_search._cooldown_until:
            retry_after = int(web_search._cooldown_until - now)
            msg = f"Web search temporarily rate-limited. Try again in ~{retry_after}s."
            logging.warning(msg)
            return msg

        # global throttle (single process)
        wait_s = (web_search._last_request_ts + min_interval_s) - now
        if wait_s > 0:
            time.sleep(wait_s)
        web_search._last_request_ts = time.time()

    try:
        max_results = int(os.getenv("SEARCH_MAX_RESULTS", "5"))
        timeout_s = float(os.getenv("SEARCH_SERVICE_TIMEOUT_SECONDS", "25"))
        service_url = os.getenv("SEARCH_SERVICE_URL", "http://127.0.0.1:5001/search")

        resp = requests.get(service_url, params={"q": query, "n": max_results}, timeout=timeout_s)
        if resp.status_code != 200:
            out = f"Search service error {resp.status_code}: {resp.text}"
        else:
            payload = resp.json() if resp.headers.get("content-type", "").lower().startswith("application/json") else {}
            results = payload.get("results", []) if isinstance(payload, dict) else []
            lines = []
            for r in results:
                if not isinstance(r, dict):
                    continue
                title = (r.get("title") or "").strip()
                url = (r.get("url") or "").strip()
                snippet = (r.get("snippet") or "").strip()
                if title or url:
                    lines.append(f"{title} - {url}".strip())
                if snippet:
                    lines.append(snippet)
            out = "\n".join(lines).strip() or "No results found"

        with web_search._lock:
            web_search._cache[qkey] = (time.time(), out)
            web_search._ratelimit_hits = 0
        return out
    except requests.exceptions.ConnectionError:
        msg = "Search service is not reachable. Start search_service.py and try again."
        logging.error(msg)
        return msg
    except Exception as e:
        logging.error(f"Search failed: {str(e)}")
        return f"Search failed: {str(e)}"

def create_file(path, content):
    logging.debug(f"Entering create_file with path: {path}, content length: {len(content)}")
    try:
        with open(path, 'w') as f:
            f.write(content)
        logging.debug("File created successfully")
        return "File created successfully"
    except Exception as e:
        logging.error(f"Error creating file: {str(e)}")
        return f"Error creating file: {str(e)}"

def read_file(path):
    logging.debug(f"Entering read_file with path: {path}")
    try:
        with open(path, 'r') as f:
            content = f.read()
        logging.debug(f"File content length: {len(content)}")
        return content
    except Exception as e:
        logging.error(f"Error reading file: {str(e)}")
        return f"Error reading file: {str(e)}"

def update_file(path, content):
    logging.debug(f"Entering update_file with path: {path}, content length: {len(content)}")
    try:
        with open(path, 'a') as f:
            f.write(content)
        logging.debug("File updated successfully")
        return "File updated successfully"
    except Exception as e:
        logging.error(f"Error updating file: {str(e)}")
        return f"Error updating file: {str(e)}"

def delete_file(path):
    logging.debug(f"Entering delete_file with path: {path}")
    try:
        os.remove(path)
        logging.debug("File deleted successfully")
        return "File deleted successfully"
    except Exception as e:
        logging.error(f"Error deleting file: {str(e)}")
        return f"Error deleting file: {str(e)}"

def sequential_think(query):
    logging.debug(f"Entering sequential_think with query: {query}")
    # Implement sequential thinking for deeper analysis
    result = f"Sequential thinking on '{query}': Let's break it down step by step. 1. Analyze the query. 2. Gather information. 3. Synthesize response. Conclusion: This requires deeper analysis and can be expanded."
    logging.debug(f"Sequential thinking result: {result}")
    return result

def scheme_catalog_search(query, language_code=None, max_results=5):
    logging.debug(f"Entering scheme_catalog_search with query: {query}, language_code: {language_code}")
    q = (query or "").strip().lower()
    hits = []
    for s in SCHEME_CATALOG:
        hay = " ".join([s.get("name", ""), s.get("description", ""), " ".join(s.get("tags", []))]).lower()
        if not q or q in hay:
            hits.append(s)
    if not hits and q:
        for s in SCHEME_CATALOG:
            if any(t.lower().find(q) >= 0 for t in s.get("tags", [])):
                hits.append(s)
    return hits[: int(max_results) if max_results else 5]

def eligibility_check(profile, scheme_id):
    logging.debug(f"Entering eligibility_check with scheme_id: {scheme_id}")
    profile = profile or {}
    scheme_id = (scheme_id or "").strip()
    scheme = next((s for s in SCHEME_CATALOG if s["id"] == scheme_id), None)
    if not scheme:
        return {"eligible": False, "reasons": ["योजना सापडली नाही."], "missing": []}

    missing = [f for f in scheme.get("required_fields", []) if profile.get(f) in (None, "", [])]
    if missing:
        return {"eligible": False, "reasons": [], "missing": missing}

    reasons = []
    eligible = True

    if scheme_id == "old_age_pension":
        try:
            age = int(profile.get("age"))
            if age < 60:
                eligible = False
                reasons.append("वय 60 वर्षांपेक्षा कमी आहे.")
        except Exception:
            eligible = False
            reasons.append("वय स्पष्ट नाही.")

    if scheme_id == "ujjwala":
        gender = str(profile.get("gender", "")).lower()
        if gender and ("female" not in gender and "स्त्री" not in gender and "महिला" not in gender):
            reasons.append("ही योजना प्रामुख्याने महिलांसाठी आहे; तरीही कुटुंब पात्रता तपासावी लागेल.")

    if scheme_id == "pmay":
        has_house = profile.get("has_pucca_house")
        if isinstance(has_house, str) and has_house.strip().lower() in ("yes", "होय", "आहे"):
            eligible = False
            reasons.append("आपल्याकडे पक्के घर असल्यास PMAY अंतर्गत अपात्रता असू शकते.")

    return {"eligible": eligible, "reasons": reasons, "missing": []}

def build_application_checklist(profile, scheme_id):
    logging.debug(f"Entering build_application_checklist with scheme_id: {scheme_id}")
    scheme = next((s for s in SCHEME_CATALOG if s["id"] == scheme_id), None)
    if not scheme:
        return "योजना सापडली नाही, चेकलिस्ट बनवता आली नाही."
    items = [
        f"योजना: {scheme['name']}",
        "ओळखपत्र: आधार/मतदार ओळखपत्र (OTP/PIN कधीही देऊ नका)",
        "पत्ता पुरावा",
        "बँक खाते तपशील",
        "उत्पन्न दाखला (लागू असल्यास)",
        "जात प्रमाणपत्र (लागू असल्यास)",
        "पासपोर्ट साईज फोटो",
    ]
    return "\n".join(items)

def _run_tool(tool_name, tool_args, detected_lang=None):
    logging.debug(f"Running tool {tool_name} with args keys: {list(tool_args.keys()) if isinstance(tool_args, dict) else 'not dict'}")
    try:
        if tool_name == "web_search":
            return web_search(tool_args.get("query", ""))
        if tool_name == "create_file":
            return create_file(tool_args.get("path", ""), tool_args.get("content", ""))
        if tool_name == "read_file":
            return read_file(tool_args.get("path", ""))
        if tool_name == "update_file":
            return update_file(tool_args.get("path", ""), tool_args.get("content", ""))
        if tool_name == "delete_file":
            return delete_file(tool_args.get("path", ""))
        if tool_name == "sequential_think":
            return sequential_think(tool_args.get("query", ""))
        if tool_name == "scheme_catalog_search":
            results = scheme_catalog_search(
                tool_args.get("query", ""),
                language_code=tool_args.get("language_code") or detected_lang,
                max_results=tool_args.get("max_results", 5),
            )
            return json.dumps(results, ensure_ascii=False)
        if tool_name == "eligibility_check":
            profile = tool_args.get("profile") or USER_STATE.get("profile") or {}
            result = eligibility_check(profile, tool_args.get("scheme_id", ""))
            return json.dumps(result, ensure_ascii=False)
        if tool_name == "build_application_checklist":
            profile = tool_args.get("profile") or USER_STATE.get("profile") or {}
            return build_application_checklist(profile, tool_args.get("scheme_id", ""))
        return "Unknown tool"
    except Exception as e:
        logging.error(f"Tool {tool_name} failed: {e}")
        return f"Tool {tool_name} failed: {str(e)}"

def translate_text(text, source_lang='auto', target_lang='en-IN', model=None):
    logging.debug(f"Entering translate_text with text length: {len(text)}, source: {source_lang}, target: {target_lang}")
    if model is None:
        model = os.getenv('TRANSLATE_MODEL', 'sarvam-translate:v1')
    if not text:
        return ""

    def _infer_lang_code_from_text(t: str) -> str:
        # Heuristic script-based inference for Sarvam translate (does not accept 'auto').
        # Prefer mr-IN for Devanagari because our system prompt/persona are Marathi.
        for ch in t:
            o = ord(ch)
            if 0x0900 <= o <= 0x097F:
                return "mr-IN"  # Devanagari
            if 0x0980 <= o <= 0x09FF:
                return "bn-IN"  # Bengali/Assamese
            if 0x0A00 <= o <= 0x0A7F:
                return "pa-IN"  # Gurmukhi
            if 0x0A80 <= o <= 0x0AFF:
                return "gu-IN"  # Gujarati
            if 0x0B00 <= o <= 0x0B7F:
                return "od-IN"  # Odia
            if 0x0B80 <= o <= 0x0BFF:
                return "ta-IN"  # Tamil
            if 0x0C00 <= o <= 0x0C7F:
                return "te-IN"  # Telugu
            if 0x0C80 <= o <= 0x0CFF:
                return "kn-IN"  # Kannada
            if 0x0D00 <= o <= 0x0D7F:
                return "ml-IN"  # Malayalam
            if 0x0600 <= o <= 0x06FF:
                return "ur-IN"  # Arabic/Urdu

        # ASCII-ish => English
        return "en-IN"

    if str(source_lang).strip().lower() in ("auto", "unknown", ""):
        source_lang = _infer_lang_code_from_text(text)

    # Sarvam translate models enforce input length limits (sarvam-translate:v1: 2000 chars).
    # Chunk the input conservatively to avoid 400 validation errors.
    max_chars = int(os.getenv("TRANSLATE_MAX_CHARS", "2000"))
    safe_max = max(200, min(max_chars, 2000))

    def _split_text_for_translate(t: str, max_len: int):
        t = " ".join(str(t).split())
        if len(t) <= max_len:
            return [t]
        chunks = []
        start = 0
        while start < len(t):
            end = min(start + max_len, len(t))
            if end == len(t):
                chunks.append(t[start:end])
                break
            window = t[start:end]
            cut = max(window.rfind(". "), window.rfind("? "), window.rfind("! "))
            if cut == -1:
                cut = window.rfind(" ")
            if cut == -1 or cut < int(max_len * 0.5):
                cut = len(window)
            chunks.append(t[start : start + cut].strip())
            start = start + cut
        return [c for c in chunks if c]

    url = f"{base_url}/translate"
    logging.debug(f"Translate URL: {url}")
    headers = {
        'API-Subscription-Key': api_key,
        'Content-Type': 'application/json'
    }

    parts = _split_text_for_translate(text, safe_max)
    translated_parts = []
    for idx, part in enumerate(parts, start=1):
        data = {
            'input': part,
            'source_language_code': source_lang,
            'target_language_code': target_lang,
            'model': model
        }
        logging.debug(f"Sending translate request chunk {idx}/{len(parts)} with length {len(part)}")
        response = requests.post(url, headers=headers, json=data)
        logging.debug(f"Translate response status: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            translated_parts.append(result.get('translated_text') or "")
        else:
            logging.error(f"Translation failed: {response.text}")
            raise Exception(f"Translation failed: {response.text}")
    return " ".join([p for p in translated_parts if p]).strip()

def transcribe_audio(audio_data, language_code='unknown', model=None):
    logging.debug("Entering transcribe_audio")
    if model is None:
        model = os.getenv('STT_MODEL', 'saarika:v2.5')
    logging.debug(f"STT Model: {model}, language_code: {language_code}")
    # audio_data is bytes of wav
    url = f"{base_url}/speech-to-text"
    logging.debug(f"STT URL: {url}")
    headers = {
        'API-Subscription-Key': api_key
    }
    # The browser sends webm/opus. Our local recorder sends wav. Detect quickly.
    if audio_data[:4] == b'RIFF':
        filename = 'audio.wav'
        mime = 'audio/wav'
    else:
        filename = 'audio.webm'
        mime = 'audio/webm'

    files = {
        'file': (filename, audio_data, mime)
    }
    data = {
        'language_code': language_code,
        'model': model
    }
    logging.debug(f"Sending STT request with data: {data}, audio length: {len(audio_data)}")
    response = requests.post(url, headers=headers, files=files, data=data)
    logging.debug(f"STT response status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        logging.debug(f"STT result: {result}")
        return result.get('transcript'), result.get('language_code')
    else:
        logging.error(f"STT failed: {response.text}")
        raise Exception(f"STT failed: {response.text}")

def record_audio(duration=None, sample_rate=16000):
    logging.debug("Entering record_audio")
    if duration is None:
        duration = int(os.getenv('RECORD_DURATION', '5'))
    logging.debug(f"Recording duration: {duration}, sample_rate: {sample_rate}")
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
    logging.debug("Audio stream opened")
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
        logging.debug("No speech detected")
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
    logging.debug(f"Recorded audio length: {len(buffer.getvalue())} bytes")
    print(f"Recorded {len(frames) * 0.02:.1f} seconds of audio.")
    return buffer.getvalue()

def play_audio(base64_audio):
    logging.debug("Entering play_audio")
    import base64
    import winsound
    audio_bytes = base64.b64decode(base64_audio)
    logging.debug(f"Decoded audio length: {len(audio_bytes)}")
    with open('output.wav', 'wb') as f:
        f.write(audio_bytes)
    # Play on Windows
    winsound.PlaySound('output.wav', winsound.SND_FILENAME)
    logging.debug("Audio played")

def _split_text_for_tts(text: str, max_chars: int = 500):
    # Prefer sentence boundaries; fall back to whitespace.
    if not text:
        return []

    text = " ".join(text.split())
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end == len(text):
            chunks.append(text[start:end])
            break

        window = text[start:end]
        cut = max(window.rfind(". "), window.rfind("? "), window.rfind("! "))
        if cut == -1:
            cut = window.rfind(" ")
        if cut == -1 or cut < int(max_chars * 0.5):
            cut = len(window)
        chunks.append(text[start : start + cut].strip())
        start = start + cut
    return [c for c in chunks if c]

def _concat_wav_base64(wav_b64_list):
    import base64
    import io
    import wave

    if not wav_b64_list:
        return ""

    params = None
    combined_frames = b""
    for i, audio_b64 in enumerate(wav_b64_list):
        try:
            wav_bytes = base64.b64decode(audio_b64)
            with io.BytesIO(wav_bytes) as wav_io:
                with wave.open(wav_io, 'rb') as wav_file:
                    if params is None:
                        params = wav_file.getparams()
                    else:
                        if wav_file.getparams()[:3] != params[:3]:
                            logging.error(
                                f"WAV params mismatch on chunk {i}: {wav_file.getparams()} vs {params}"
                            )
                            return wav_b64_list[0]
                    combined_frames += wav_file.readframes(wav_file.getnframes())
        except Exception as e:
            logging.error(f"Failed to decode/concat wav chunk {i}: {e}")
            return wav_b64_list[0]

    out = io.BytesIO()
    with wave.open(out, 'wb') as wf:
        wf.setnchannels(params.nchannels if params else 1)
        wf.setsampwidth(params.sampwidth if params else 2)
        wf.setframerate(params.framerate if params else 16000)
        wf.writeframes(combined_frames)
    return base64.b64encode(out.getvalue()).decode('utf-8')

def generate_tts(text, language, speaker=None, model=None):
    logging.debug(f"Entering generate_tts with text length: {len(text)}, language: {language}")
    if speaker is None:
        speaker = os.getenv('DEFAULT_SPEAKER', 'anushka')
    speaker = str(speaker).strip().lower()
    if speaker not in SUPPORTED_TTS_SPEAKERS:
        logging.warning(f"Unsupported TTS speaker '{speaker}', falling back to 'anushka'")
        speaker = 'anushka'
    if model is None:
        model = os.getenv('TTS_MODEL', 'bulbul:v2')

    # Sarvam expects BCP-47 language codes
    if language not in SUPPORTED_LANG_CODES:
        logging.warning(f"Unsupported/unknown language '{language}', falling back to en-IN")
        language = 'en-IN'

    chunks = _split_text_for_tts(text, max_chars=500)
    if not chunks:
        return {"audios": []}
    logging.debug(f"TTS chunks: {len(chunks)}")

    url = f'{base_url}/text-to-speech'
    headers = {
        'API-Subscription-Key': api_key,
        'Content-Type': 'application/json'
    }

    # Sarvam validates inputs list length; observed limit is 3 items.
    max_inputs_per_request = 3
    all_audios = []
    for i in range(0, len(chunks), max_inputs_per_request):
        batch = chunks[i:i + max_inputs_per_request]

        payload = {
            'language': language,
            'inputs': batch,
            'speaker': speaker,
            'model': model
        }

        logging.debug(f"Sending TTS request with batch size {len(batch)} (chunks {i}..{i+len(batch)-1})")
        resp = requests.post(url, headers=headers, json=payload)
        logging.debug(f"TTS response status: {resp.status_code}")
        if resp.status_code != 200:
            logging.error(f"TTS failed: {resp.text}")
            raise Exception(f"TTS failed: {resp.text}")

        try:
            data = resp.json()
        except Exception:
            # Sometimes a plain base64 string is returned
            all_audios.append(resp.text)
            continue

        audios = None
        if isinstance(data, dict):
            if 'audios' in data and isinstance(data['audios'], list):
                audios = data['audios']
            elif 'audio' in data:
                audios = [data['audio']]
            elif 'data' in data:
                audios = [data['data']]
        elif isinstance(data, str):
            audios = [data]

        if not audios:
            logging.error(f"TTS response missing audio data: {data}")
            raise Exception("TTS response missing audio data")

        all_audios.extend(audios)

    combined = _concat_wav_base64(all_audios)
    return {"audios": [combined]}

tools = TOOLS_SCHEMA if isinstance(TOOLS_SCHEMA, list) and TOOLS_SCHEMA else []

def store_memory(text):
    logging.debug(f"Entering store_memory with text length: {len(text)}")
    # Add to vector store
    collection.add(documents=[text], ids=[str(len(collection.get()['ids']) + 1)])
    logging.debug("Memory stored")

def retrieve_memory(query):
    logging.debug(f"Entering retrieve_memory with query: {query}")
    results = collection.query(query_texts=[query], n_results=3)
    mem = results['documents'][0] if results['documents'] else []
    logging.debug(f"Retrieved memory: {mem}")
    return mem

def load_system_prompt():
    logging.debug("Entering load_system_prompt")
    try:
        with open('system_prompt.txt', 'r', encoding='utf-8') as f:
            prompt = f.read().strip()
            logging.debug(f"Loaded system prompt: {prompt[:100]}...")
            return prompt
    except FileNotFoundError:
        logging.debug("system_prompt.txt not found, using default")
        return "You are a helpful multilingual assistant for Indic languages with access to web search, file operations, sequential thinking, and memory."

_PROMPT_EN_CACHE = {"src": None, "en": None}
_PERSONA_EN_CACHE = {"src": None, "en": None}

def _get_system_prompt_en():
    src = load_system_prompt()
    if _PROMPT_EN_CACHE["src"] == src and _PROMPT_EN_CACHE["en"]:
        return _PROMPT_EN_CACHE["en"]
    try:
        en = translate_text(src, source_lang='mr-IN', target_lang='en-IN')
    except Exception:
        en = src
    _PROMPT_EN_CACHE["src"] = src
    _PROMPT_EN_CACHE["en"] = en
    return en

def _get_persona_en(persona_obj):
    if not persona_obj:
        return ""
    src = json.dumps(persona_obj, ensure_ascii=False)
    if _PERSONA_EN_CACHE["src"] == src and _PERSONA_EN_CACHE["en"]:
        return _PERSONA_EN_CACHE["en"]
    try:
        en = translate_text(src, source_lang='mr-IN', target_lang='en-IN')
    except Exception:
        en = src
    _PERSONA_EN_CACHE["src"] = src
    _PERSONA_EN_CACHE["en"] = en
    return en

messages = [{"role": "system", "content": _get_system_prompt_en()}]

def process_voice_query(audio_data):
    logging.debug("Entering process_voice_query")
    logging.debug(f"Audio data length: {len(audio_data)}")
    transcript, lang = transcribe_audio(audio_data)
    logging.debug(f"Transcript: '{transcript}', Detected lang: {lang}")
    if not transcript:
        logging.debug("No transcript, returning")
        return "No speech detected", "", "", "en-IN"
    detected_lang = lang or 'en-IN'
    if detected_lang not in SUPPORTED_LANG_CODES:
        detected_lang = 'en-IN'

    user_input_native = transcript
    logging.debug(f"User input(native): '{user_input_native}', detected_lang: {detected_lang}")

    # Translate user input to English for the LLM (automatic, not fixed to any user language)
    try:
        if detected_lang == 'en-IN':
            user_input_en = user_input_native
        else:
            user_input_en = translate_text(user_input_native, source_lang=detected_lang, target_lang='en-IN')
    except Exception as e:
        logging.error(f"User->English translation failed: {e}; using raw transcript")
        user_input_en = user_input_native

    messages.append({"role": "user", "content": user_input_en})
    logging.debug(f"Messages count: {len(messages)}")

    # Memory is stored/retrieved in English for consistency with the LLM context
    memory = retrieve_memory(user_input_en)
    logging.debug(f"Memory retrieved: {len(memory)} items")
    if memory:
        messages.append({"role": "system", "content": f"Relevant past info: {' '.join(memory)}"})
        logging.debug("Added memory to messages")

    persona_str = _get_persona_en(SWAYAM_PERSONA)
    planner_messages = [
        {"role": "system", "content": _get_system_prompt_en()},
        {"role": "system", "content": f"Persona (Swayam): {persona_str}"},
        {"role": "system", "content": f"Current known profile (JSON): {json.dumps(USER_STATE['profile'], ensure_ascii=False)}"},
        {"role": "user", "content": user_input_en},
        {"role": "system", "content": "Planner: Respond ONLY in JSON. keys: extracted_profile (object), goal (string), missing_fields (array), search_query (string)."},
    ]

    plan_raw = openai_chat(planner_messages).choices[0].message.content or "{}"
    try:
        plan = json.loads(plan_raw)
    except Exception:
        plan = {"extracted_profile": {}, "goal": "", "missing_fields": [], "search_query": user_input_native, "chosen_language_code": detected_lang}

    extracted = plan.get("extracted_profile") if isinstance(plan.get("extracted_profile"), dict) else {}
    contradictions = []
    for k, v in extracted.items():
        if v in (None, ""):
            continue
        old = USER_STATE["profile"].get(k)
        if old not in (None, "") and str(old).strip() != str(v).strip():
            contradictions.append({"field": k, "old": old, "new": v})
        USER_STATE["profile"][k] = v
    if contradictions:
        USER_STATE["contradictions"].extend(contradictions)

    search_query_en = plan.get("search_query") or user_input_en
    # Scheme catalog currently contains Marathi fields, so translate the query to Marathi for matching.
    try:
        scheme_query_mr = translate_text(search_query_en, source_lang='en-IN', target_lang='mr-IN')
    except Exception:
        scheme_query_mr = search_query_en

    shortlisted = scheme_catalog_search(scheme_query_mr, language_code='mr-IN', max_results=5)
    checks = []
    for s in shortlisted:
        r = eligibility_check(USER_STATE["profile"], s["id"])
        checks.append({"scheme": s, "result": r})

    missing_all = set()
    for c in checks:
        for m in c["result"].get("missing", []) or []:
            missing_all.add(m)

    eval_messages = [
        {"role": "system", "content": _get_system_prompt_en()},
        {"role": "system", "content": f"Persona (Swayam): {persona_str}"},
        {"role": "system", "content": "Evaluator: Answer in English (for translation). Use Planner→Executor→Evaluator structure and be voice-friendly."},
        {"role": "system", "content": f"User language code (for translation later): {detected_lang}"},
        {"role": "system", "content": f"Goal: {plan.get('goal', '')}"},
        {"role": "system", "content": f"Contradictions: {json.dumps(USER_STATE['contradictions'][-3:], ensure_ascii=False)}"},
        {"role": "system", "content": f"Shortlisted schemes + results (may contain Marathi fields): {json.dumps(checks, ensure_ascii=False)}"},
        {"role": "system", "content": f"Missing fields: {json.dumps(sorted(list(missing_all)), ensure_ascii=False)}"},
        {"role": "user", "content": user_input_en},
    ]

    # Executor-style loop for tool calls (OpenAI may return tool_calls with empty content)
    response = openai_chat(eval_messages, tools=tools)
    msg = response.choices[0].message
    tool_loops = 0
    while getattr(msg, "tool_calls", None) and tool_loops < 5:
        tool_loops += 1
        eval_messages.append(msg)
        for tool_call in msg.tool_calls:
            try:
                args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
            except Exception:
                args = {}
            result = _run_tool(tool_call.function.name, args, detected_lang=detected_lang)
            eval_messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": result})
        response = openai_chat(eval_messages, tools=tools)
        msg = response.choices[0].message

    assistant_en = (getattr(msg, "content", None) or "").strip()
    if not assistant_en:
        assistant_en = "Sorry, I could not generate an answer. Please repeat your question."

    try:
        if detected_lang == 'en-IN':
            assistant_native = assistant_en
        else:
            assistant_native = translate_text(assistant_en, source_lang='en-IN', target_lang=detected_lang)
    except Exception as e:
        logging.error(f"English->User translation failed: {e}; using English")
        assistant_native = assistant_en

    messages.append({"role": "assistant", "content": assistant_en})

    logging.debug("Generating TTS")
    tts_result = generate_tts(assistant_native, detected_lang)
    audios = tts_result.get('audios') if isinstance(tts_result, dict) else None
    audio_base64 = audios[0] if audios else ""
    logging.debug(f"TTS audio length: {len(audio_base64) if isinstance(audio_base64, str) else 0}")

    store_memory(user_input_en + " " + assistant_en)
    logging.debug("Memory stored, returning")
    return assistant_native, audio_base64, user_input_native, detected_lang

def agent_loop():
    detected_lang = None
    while True:
        audio_data = record_audio()
        if audio_data is None:
            continue
        assistant_native, audio_b64, user_native, detected_lang = process_voice_query(audio_data)
        print(f"You said: {user_native}")
        print(f"Agent: {assistant_native}")
        if audio_b64:
            play_audio(audio_b64)

if __name__ == "__main__":
    agent_loop()
