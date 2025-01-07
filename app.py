import streamlit as st
import google.generativeai as genai
from google.cloud import texttospeech
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import os
from dotenv import load_dotenv

# 초기 설정
def initialize_services():
    try:
        # Google Sheets API 설정
        SCOPES = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        credentials_dict = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, SCOPES)
        gc = gspread.authorize(creds)
        sheet = gc.open_by_key(st.secrets["GOOGLE_SHEET_ID"]).sheet1

        # Gemini AI 설정
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        model = genai.GenerativeModel('gemini-pro')

        # TTS 설정
        tts_client = texttospeech.TextToSpeechClient()

        return sheet, model, tts_client
    except Exception as e:
        st.error(f"서비스 초기화 중 오류가 발생했습니다: {str(e)}")
        return None, None, None

def generate_audio(tts_client, text):
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

def save_to_sheets(sheet, data):
    sheet.append_row([
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        data.get('name', ''),
        data.get('email', ''),
        data.get('phone', ''),
        data.get('question', ''),
        data.get('response', '')
    ])

def main():
    # 페이지 설정
    st.set_page_config(
        page_title="디마불사 AI 고객상담 챗봇",
        page_icon="🤖",
        layout="centered"
    )
    
    # 서비스 초기화 (한 번만 실행)
    if 'initialized' not in st.session_state:
        st.session_state.sheet, st.session_state.model, st.session_state.tts_client = initialize_services()
        st.session_state.initialized = True
    
    # 제목
    st.title("디마불사 AI 고객상담 챗봇")
    
    # 세션 상태 초기화
    if 'messages' not in st.session_state:
        st.session_state.messages = []
        st.session_state.user_info = {}
        st.session_state.show_contact_form = False
        
        # 시작 메시지 추가
        welcome_msg = "어서 오세요. 디마불사 최규문입니다. 무엇이 궁금하세요, 제미나이가 저 대신 24시간 응답해 드립니다."
        st.session_state.messages.append({"role": "assistant", "content": welcome_msg})
        
        # 시작 메시지 음성 생성
        try:
            audio = generate_audio(st.session_state.tts_client, welcome_msg)
            st.session_state.welcome_audio = audio
        except Exception as e:
            st.error(f"음성 생성 중 오류 발생: {str(e)}")
    
    # 시작 메시지 음성 재생 (한 번만)
    if 'welcome_audio' in st.session_state:
        st.audio(st.session_state.welcome_audio, format='audio/mp3')
        del st.session_state.welcome_audio
    
    # 채팅 메시지 표시
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
    
    # 연락처 입력 폼
    if st.session_state.show_contact_form:
        with st.form(key='contact_form'):
            name = st.text_input("이름")
            email = st.text_input("이메일")
            phone = st.text_input("휴대폰 번호")
            submit = st.form_submit_button("제출")
            
            if submit:
                st.session_state.user_info = {
                    'name': name,
                    'email': email,
                    'phone': phone
                }
                st.session_state.show_contact_form = False
                st.rerun()
    
    # 사용자 입력
    if prompt := st.chat_input("궁금하신 내용을 입력해주세요..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # 첫 질문인 경우
        if len(st.session_state.messages) == 2:
            keywords = ' '.join(prompt.split()[:3])
            query_msg = f"아, {keywords}에 대해 알고 싶으시군요. 답을 드리기 전에 미리 연락처를 남겨 주시면 필요한 고급 자료나 뉴스레터를 보내드립니다. 혹시 연락처를 먼저 남기시겠어요?"
            st.session_state.messages.append({"role": "assistant", "content": query_msg})
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("예"):
                    st.session_state.show_contact_form = True
                    st.rerun()
            with col2:
                if st.button("아니오"):
                    response = st.session_state.model.generate_content(prompt).text
                    st.session_state.messages.append({"role": "assistant", "content": response})
                    save_to_sheets(st.session_state.sheet, {'question': prompt, 'response': response})
                    audio = generate_audio(st.session_state.tts_client, response)
                    st.audio(audio, format='audio/mp3')
                    st.rerun()
        
        # 일반 대화
        else:
            response = st.session_state.model.generate_content(prompt).text
            st.session_state.messages.append({"role": "assistant", "content": response})
            save_to_sheets(st.session_state.sheet, {
                'name': st.session_state.user_info.get('name', ''),
                'email': st.session_state.user_info.get('email', ''),
                'phone': st.session_state.user_info.get('phone', ''),
                'question': prompt,
                'response': response
            })
            audio = generate_audio(st.session_state.tts_client, response)
            st.audio(audio, format='audio/mp3')
            st.rerun()

if __name__ == "__main__":
    main()
