import streamlit as st
import google.generativeai as genai
from google.cloud import texttospeech
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import os
from dotenv import load_dotenv
import json

# 환경변수 로드
load_dotenv()

# Gemini API 설정
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')

# Google Sheets API 설정
SCOPES = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
credentials_dict = st.secrets["gcp_service_account"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, SCOPES)
gc = gspread.authorize(creds)
sheet = gc.open_by_key(os.getenv('GOOGLE_SHEET_ID')).sheet1

# TTS 클라이언트 초기화
tts_client = texttospeech.TextToSpeechClient()

def extract_keywords(text):
    # 간단한 키워드 추출 로직
    # 실제 구현시에는 더 복잡한 NLP 기법을 사용할 수 있습니다
    words = text.split()
    return ' '.join(words[:3])  # 첫 3개 단어를 키워드로 사용

def generate_audio(text):
    synthesis_input = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(
        language_code="ko-KR",
        name="ko-KR-Standard-A",
        ssml_gender=texttospeech.SsmlVoiceGender.FEMALE
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3
    )
    response = tts_client.synthesize_speech(
        input=synthesis_input, voice=voice, audio_config=audio_config
    )
    return response.audio_content

def save_to_sheets(data):
    sheet.append_row([
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        data.get('name', ''),
        data.get('email', ''),
        data.get('phone', ''),
        data.get('question', ''),
        data.get('response', '')
    ])

def main():
    st.title("디마불사 AI 고객상담 챗봇")
    
    # 세션 상태 초기화
    if 'messages' not in st.session_state:
        st.session_state.messages = []
        st.session_state.user_info = {}
        st.session_state.show_contact_form = False
        st.session_state.contact_step = 0
        
        # 시작 메시지 추가
        welcome_msg = "어서 오세요. 디마불사 최규문입니다. 무엇이 궁금하세요, 제미나이가 저 대신 24시간 응답해 드립니다."
        st.session_state.messages.append({"role": "assistant", "content": welcome_msg})
        
        # 시작 메시지 음성 생성 및 재생
        audio_content = generate_audio(welcome_msg)
        st.audio(audio_content, format='audio/mp3')

    # 메시지 이력 표시
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # 연락처 입력 폼
    if st.session_state.show_contact_form:
        if st.session_state.contact_step == 0:
            st.text_input("이름을 입력해주세요:", key="name")
            if st.button("확인", key="name_btn"):
                st.session_state.user_info['name'] = st.session_state.name
                st.session_state.contact_step = 1
                st.rerun()
        
        elif st.session_state.contact_step == 1:
            st.text_input("이메일 주소를 입력해주세요:", key="email")
            if st.button("확인", key="email_btn"):
                st.session_state.user_info['email'] = st.session_state.email
                st.session_state.contact_step = 2
                st.rerun()
        
        elif st.session_state.contact_step == 2:
            st.text_input("휴대폰 번호를 입력해주세요:", key="phone")
            if st.button("확인", key="phone_btn"):
                st.session_state.user_info['phone'] = st.session_state.phone
                st.session_state.show_contact_form = False
                st.session_state.contact_step = 3
                st.rerun()

    # 사용자 입력 처리
    if prompt := st.chat_input("메시지를 입력하세요"):
        # 사용자 메시지 추가
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # 첫 질문인 경우 연락처 수집 여부 확인
        if len(st.session_state.messages) == 2:  # 시작 메시지 + 첫 질문
            keywords = extract_keywords(prompt)
            contact_query = f"아, {keywords}에 대해 알고 싶으시군요. 답을 드리기 전에 미리 연락처를 남겨 주시면 필요한 고급 자료나 뉴스레터를 보내드립니다. 혹시 연락처를 먼저 남기시겠어요?"
            st.session_state.messages.append({"role": "assistant", "content": contact_query})
            
            # 음성 생성 및 재생
            audio_content = generate_audio(contact_query)
            st.audio(audio_content, format='audio/mp3')
            
            # 예/아니오 버튼
            col1, col2 = st.columns(2)
            with col1:
                if st.button("예"):
                    st.session_state.show_contact_form = True
                    st.rerun()
            with col2:
                if st.button("아니오"):
                    response = model.generate_content(prompt).text
                    st.session_state.messages.append({"role": "assistant", "content": response})
                    
                    # 응답 저장
                    save_to_sheets({
                        'question': prompt,
                        'response': response
                    })
                    
                    # 음성 생성 및 재생
                    audio_content = generate_audio(response)
                    st.audio(audio_content, format='audio/mp3')
                    st.rerun()
        
        # 일반 대화 처리
        elif not st.session_state.show_contact_form:
            response = model.generate_content(prompt).text
            st.session_state.messages.append({"role": "assistant", "content": response})
            
            # 응답 저장
            save_to_sheets({
                'name': st.session_state.user_info.get('name', ''),
                'email': st.session_state.user_info.get('email', ''),
                'phone': st.session_state.user_info.get('phone', ''),
                'question': prompt,
                'response': response
            })
            
            # 음성 생성 및 재생
            audio_content = generate_audio(response)
            st.audio(audio_content, format='audio/mp3')
            st.rerun()

if __name__ == "__main__":
    main()
