import streamlit as st
from streamlit_audio_recorder import streamlit_audio_recorder
from conversation_agent import process_voice_query
import base64

st.title("Multilingual Voice Assistant for Indic Languages")

# Initialize session state for messages
if 'messages' not in st.session_state:
    st.session_state.messages = []

# Display chat messages
for msg in st.session_state.messages:
    with st.chat_message(msg['role']):
        st.write(msg['content'])

# Audio recorder component
st.write("Click the mic button to record your voice:")
audio_data = streamlit_audio_recorder(pause_threshold=2.0, sample_rate=16000)

if audio_data and len(audio_data) > 0:
    with st.spinner("Processing your voice..."):
        text, audio_b64 = process_voice_query(audio_data)
    
    # Add messages to session state
    st.session_state.messages.append({"role": "user", "content": f"You said: {text}"})
    st.session_state.messages.append({"role": "assistant", "content": text})
    
    # Play the TTS audio
    if audio_b64:
        audio_bytes = base64.b64decode(audio_b64)
        st.audio(audio_bytes, format='audio/wav')
    
    # Rerun to update the chat
    st.rerun()

st.write("---")
st.write("This assistant supports Indic languages, web search, file operations, and more.")
