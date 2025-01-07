import streamlit as st
import google.generativeai as genai
from google.cloud import texttospeech
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import os
from dotenv import load_dotenv

def init_google_sheet():
    """구글 시트 초기화 함수"""
    try:
        st.write("Initializing Google Sheets connection...")
        SCOPES = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        credentials_dict = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, SCOPES)
        gc = gspread.authorize(creds)
        sheet = gc.open_by_key(st.secrets["GOOGLE_SHEET_ID"]).sheet1
        st.success("Successfully connected to Google Sheets!")
        return sheet
    except Exception as e:
        st.error(f"Failed to initialize Google Sheets: {str(e)}")
        return None

def init_gemini():
    """Gemini AI 초기화 함수"""
    try:
        st.write("Initializing Gemini AI...")
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        model = genai.GenerativeModel('gemini-pro')
        st.success("Successfully connected to Gemini AI!")
        return model
    except Exception as e:
        st.error(f"Failed to initialize Gemini AI: {str(e)}")
        return None

def init_tts():
    """TTS 클라이언트 초기화 함수"""
    try:
        st.write("Initializing Text-to-Speech...")
        tts_client = texttospeech.TextToSpeechClient()
        st.success("Successfully initialized Text-to-Speech!")
        return tts_client
    except Exception as e:
        st.error(f"Failed to initialize Text-to-Speech: {str(e)}")
        return None

def generate_audio(tts_client, text):
    """TTS로 음성 생성"""
    try:
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
    except Exception as e:
        st.error(f"Failed to generate audio: {str(e)}")
        return None

def extract_keywords(text):
    """질문에서 키워드 추출"""
    words = text.split()
    return ' '.join(words[:3])

def save_to_sheets(sheet, data):
    """대화 내용을 구글 시트에 저장"""
    try:
        sheet.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            data.get('name', ''),
            data.get('email', ''),
            data.get('phone', ''),
            data.get('question', ''),
            data.get('response', '')
        ])
    except Exception as e:
        st.error(f"Failed to save to sheets: {str(e)}")

def main():
    st.title("디마불사 AI 고객상담 챗봇")
    
    # 서비스 초기화
    sheet = init_google_sheet()
    model = init_gemini()
    tts_client = init_tts()
    
    if not all([sheet, model, tts_client]):
        st.error("서비스 초기화에 실패했습니다. 로그를 확인해주세요.")
        return

    # 초기화 메시지 숨기기
    for key in ["Initializing Google Sheets connection...", 
                "Initializing Gemini AI...",
                "Initializing Text-to-Speech...",
                "Successfully connected to Google Sheets!",
                "Successfully connected to Gemini AI!",
                "Successfully initialized Text-to-Speech!"]:
        st.empty()
    
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
        audio_content = generate_audio(tts_client, welcome_msg)
        if audio_content:
            st.audio(audio_content, format='audio/mp3')
    
    # 메시지 이력 표시
    messages_container = st.container()
    with messages_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
    
    # 연락처 입력 폼
    if st.session_state.show_contact_form:
        contact_form = st.form(key='contact_form')
        with contact_form:
            if st.session_state.contact_step == 0:
                name = st.text_input("이름을 입력해주세요:")
                if st.form_submit_button("확인"):
                    st.session_state.user_info['name'] = name
                    st.session_state.contact_step = 1
                    st.rerun()
            elif st.session_state.contact_step == 1:
                email = st.text_input("이메일 주소를 입력해주세요:")
                if st.form_submit_button("확인"):
                    st.session_state.user_info['email'] = email
                    st.session_state.contact_step = 2
                    st.rerun()
            elif st.session_state.contact_step == 2:
                phone = st.text_input("휴대폰 번호를 입력해주세요:")
                if st.form_submit_button("확인"):
                    st.session_state.user_info['phone'] = phone
                    st.session_state.show_contact_form = False
                    st.session_state.contact_step = 3
                    st.rerun()
    
    # 사용자 입력 처리
    if prompt := st.chat_input("궁금하신 내용을 입력해주세요"):
        # 사용자 메시지 추가
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # 첫 질문인 경우 연락처 수집 여부 확인
        if len(st.session_state.messages) == 2:  # 시작 메시지 + 첫 질문
            keywords = extract_keywords(prompt)
            contact_query = f"아, {keywords}에 대해 알고 싶으시군요. 답을 드리기 전에 미리 연락처를 남겨 주시면 필요한 고급 자료나 뉴스레터를 보내드립니다. 혹시 연락처를 먼저 남기시겠어요?"
            st.session_state.messages.append({"role": "assistant", "content": contact_query})
            
            # 음성 생성 및 재생
            audio_content = generate_audio(tts_client, contact_query)
            if audio_content:
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
                    save_to_sheets(sheet, {
                        'question': prompt,
                        'response': response
                    })
                    
                    # 음성 생성 및 재생
                    audio_content = generate_audio(tts_client, response)
                    if audio_content:
                        st.audio(audio_content, format='audio/mp3')
                    st.rerun()
        
        # 일반 대화 처리
        elif not st.session_state.show_contact_form:
            response = model.generate_content(prompt).text
            st.session_state.messages.append({"role": "assistant", "content": response})
            
            # 응답 저장
            save_to_sheets(sheet, {
                'name': st.session_state.user_info.get('name', ''),
                'email': st.session_state.user_info.get('email', ''),
                'phone': st.session_state.user_info.get('phone', ''),
                'question': prompt,
                'response': response
            })
            
            # 음성 생성 및 재생
            audio_content = generate_audio(tts_client, response)
            if audio_content:
                st.audio(audio_content, format='audio/mp3')
            st.rerun()

if __name__ == "__main__":
    main()
