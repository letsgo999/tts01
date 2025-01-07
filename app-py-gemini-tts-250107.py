import streamlit as st
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz
from google.cloud import texttospeech
from google.cloud import speech_v1 as speech

# 기본 페이지 설정
st.set_page_config(
    page_title="디마불사 AI 고객상담 챗봇",
    page_icon="🤖",
    layout="centered"
)

def get_korean_time():
    """한국 시간 반환"""
    korean_tz = pytz.timezone('Asia/Seoul')
    kr_time = datetime.now(korean_tz)
    return kr_time.strftime("%Y-%m-%d %H:%M:%S")

def generate_tts(text, language_code="ko-KR"):
    """텍스트를 음성으로 변환"""
    try:
        client = texttospeech.TextToSpeechClient()
        synthesis_input = texttospeech.SynthesisInput(text=text)
        
        voice = texttospeech.VoiceSelectionParams(
            language_code=language_code,
            name="ko-KR-Standard-A",
            ssml_gender=texttospeech.SsmlVoiceGender.FEMALE
        )
        
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        )
        
        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )
        
        return response.audio_content
    except Exception as e:
        st.error(f"음성 생성 중 오류 발생: {str(e)}")
        return None

def play_audio_message(message):
    """메시지를 음성으로 재생"""
    audio_content = generate_tts(message)
    if audio_content:
        st.audio(audio_content, format='audio/mp3')

# 웹 음성인식을 위한 JavaScript
js_code = """
<script>
let mediaRecorder;
let audioChunks = [];

function setupRecorder() {
    if (!'mediaDevices' in navigator) {
        alert('음성 입력이 지원되지 않는 브라우저입니다.');
        return false;
    }
    
    navigator.mediaDevices.getUserMedia({ audio: true })
        .then(stream => {
            mediaRecorder = new MediaRecorder(stream);
            
            mediaRecorder.ondataavailable = (e) => {
                audioChunks.push(e.data);
            };
            
            mediaRecorder.onstop = () => {
                const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                audioChunks = [];
                const reader = new FileReader();
                reader.readAsDataURL(audioBlob);
                reader.onloadend = () => {
                    const base64data = reader.result;
                    // Streamlit으로 데이터 전송
                    window.parent.postMessage({
                        type: 'streamlit:setComponentValue',
                        data: base64data,
                        key: 'audio_data' // 추가된 key
                    }, '*');
                };
            };
        });
    return true;
}

function startRecording() {
    if (!mediaRecorder) {
        if (!setupRecorder()) return;
    }
    audioChunks = [];
    mediaRecorder.start();
    document.getElementById('recordButton').style.display = 'none';
    document.getElementById('stopButton').style.display = 'block';
}

function stopRecording() {
    mediaRecorder.stop();
    document.getElementById('recordButton').style.display = 'block';
    document.getElementById('stopButton').style.display = 'none';
}
</script>

<button id="recordButton" onclick="startRecording()" 
    style="padding: 10px 20px; background-color: #ff4b4b; color: white; border: none; border-radius: 5px; cursor: pointer;">
    🎤 음성 녹음 시작
</button>

<button id="stopButton" onclick="stopRecording()" 
    style="display: none; padding: 10px 20px; background-color: #4bb4ff; color: white; border: none; border-radius: 5px; cursor: pointer;">
    ⏹ 녹음 중지
</button>
"""

def extract_keywords(text):
    """핵심 키워드 추출 함수"""
    stop_words = ['은', '는', '이', '가', '을', '를', '에', '에서', '으로', '로', '하다', '입니다', '있다', '없다']
    words = text.split()
    keywords = [word for word in words if word not in stop_words][:2]
    return ' '.join(keywords)

def save_to_sheets(sheet, data, extracted_keywords=""):
    """구글 시트에 대화 내용 저장"""
    try:
        if st.session_state.contact_info_saved:
            return

        last_row = sheet.get_all_records()
        last_user_info = {
            'Name': '',
            'Email': '',
            'Phone': ''
        }
        if last_row:
            last_user_info = {
                'Name': last_row[-1]['Name'],
                'Email': last_row[-1]['Email'],
                'Phone': last_row[-1]['Phone']
            }

        name = data.get('name', '') or last_user_info['Name']
        email = data.get('email', '') or last_user_info['Email']
        phone = data.get('phone', '') or last_user_info['Phone']

        sheet.append_row([
            get_korean_time(),
            extracted_keywords,
            data.get('question', ''),
            data.get('response', ''),
            name,
            email,
            phone
        ])

        if name != '' and email != '' and phone != '':
            st.session_
