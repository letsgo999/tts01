import streamlit as st
import google.generativeai as genai
from google.cloud import texttospeech
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import os
from dotenv import load_dotenv

# 디버그 모드 설정
DEBUG = True

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

def main():
    st.title("디마불사 AI 고객상담 챗봇")
    
    # 각 서비스 초기화
    sheet = init_google_sheet()
    model = init_gemini()
    tts_client = init_tts()
    
    if not all([sheet, model, tts_client]):
        st.error("일부 서비스 초기화에 실패했습니다. 로그를 확인해주세요.")
        return
    
    # 여기서 세션 상태 초기화
    if 'messages' not in st.session_state:
        st.session_state.messages = []
        st.session_state.user_info = {}
        st.session_state.show_contact_form = False
        st.session_state.contact_step = 0
        
        # 시작 메시지 추가
        welcome_msg = "어서 오세요. 디마불사 최규문입니다. 무엇이 궁금하세요, 제미나이가 저 대신 24시간 응답해 드립니다."
        st.session_state.messages.append({"role": "assistant", "content": welcome_msg})
    
    # 디버그 정보 표시
    if DEBUG:
        st.write("Debug Information:")
        st.write(f"Number of messages: {len(st.session_state.messages)}")
        st.write(f"Contact form visible: {st.session_state.show_contact_form}")
        st.write(f"Contact step: {st.session_state.contact_step}")
    
    # 나머지 챗봇 로직...
    
    # 메시지 표시
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

if __name__ == "__main__":
    main()
