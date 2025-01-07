import streamlit as st
import google.generativeai as genai
from google.cloud import texttospeech
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# 기본 페이지 설정
st.set_page_config(
    page_title="디마불사 AI 고객상담 챗봇",
    page_icon="🤖",
    layout="centered"
)

# 제목
st.title("디마불사 AI 고객상담 챗봇")

try:
    # Google Sheets API 설정
    @st.cache_resource
    def init_google_sheets():
        SCOPES = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        credentials_dict = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, SCOPES)
        gc = gspread.authorize(creds)
        return gc.open_by_key(st.secrets["GOOGLE_SHEET_ID"]).sheet1

    # Gemini AI 설정
    @st.cache_resource
    def init_gemini():
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        return genai.GenerativeModel('gemini-pro')

    # TTS 설정
    @st.cache_resource
    def init_tts():
        return texttospeech.TextToSpeechClient()

    # 음성 생성 함수
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

    # 서비스 초기화
    sheet = init_google_sheets()
    model = init_gemini()
    tts_client = init_tts()

    # 세션 상태 초기화
    if 'messages' not in st.session_state:
        st.session_state.messages = []
        st.session_state.user_info = {}
        
        # 시작 메시지 추가
        welcome_msg = "어서 오세요. 디마불사 최규문입니다. 무엇이 궁금하세요, 제미나이가 저 대신 24시간 응답해 드립니다."
        st.session_state.messages.append({"role": "assistant", "content": welcome_msg})
        
        # 시작 메시지 음성 생성
        audio = generate_audio(welcome_msg)
        st.audio(audio, format='audio/mp3')

    # 채팅 메시지 표시
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    # 사용자 입력 처리
    if prompt := st.chat_input("궁금하신 내용을 입력해주세요..."):
        # 사용자 메시지 추가
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.chat_message("user").write(prompt)

        # 첫 질문인 경우
        if len(st.session_state.messages) == 2:
            keywords = ' '.join(prompt.split()[:3])
            query_msg = f"아, {keywords}에 대해 알고 싶으시군요. 답을 드리기 전에 미리 연락처를 남겨 주시면 필요한 고급 자료나 뉴스레터를 보내드립니다. 혹시 연락처를 먼저 남기시겠어요?"
            
            with st.chat_message("assistant"):
                st.write(query_msg)
                audio = generate_audio(query_msg)
                st.audio(audio, format='audio/mp3')
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("예"):
                        name = st.text_input("이름을 입력해주세요")
                        email = st.text_input("이메일 주소를 입력해주세요")
                        phone = st.text_input("휴대폰 번호를 입력해주세요")
                        if st.button("제출"):
                            st.session_state.user_info = {
                                'name': name,
                                'email': email,
                                'phone': phone
                            }
                            st.rerun()
                with col2:
                    if st.button("아니오"):
                        st.rerun()

        else:
            # AI 응답 생성
            response = model.generate_content(prompt).text
            
            # 응답 표시
            with st.chat_message("assistant"):
                st.write(response)
                audio = generate_audio(response)
                st.audio(audio, format='audio/mp3')
            
            # 대화 내용 저장
            sheet.append_row([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                st.session_state.user_info.get('name', ''),
                st.session_state.user_info.get('email', ''),
                st.session_state.user_info.get('phone', ''),
                prompt,
                response
            ])

except Exception as e:
    st.error(f"오류가 발생했습니다: {str(e)}")
