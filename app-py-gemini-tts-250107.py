import streamlit as st
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz
from google.cloud import texttospeech

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
                        data: base64data
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
            st.session_state.contact_info_saved = True

    except Exception as e:
        st.error(f"데이터 저장 중 오류 발생: {str(e)}")

def handle_yes_click():
    """[예] 버튼 클릭 시 즉시 실행"""
    st.session_state.button_pressed = True
    st.session_state.contact_step = 0
    message = "이름이 어떻게 되세요?"
    st.session_state.messages.append({"role": "assistant", "content": message})
    play_audio_message(message)
    st.session_state.focus = "name_input"
    st.rerun()

def handle_no_click():
    """[아니오] 버튼 클릭 시 즉시 실행"""
    st.session_state.button_pressed = True
    response = model.generate_content(st.session_state.initial_question).text
    st.session_state.messages.append({"role": "assistant", "content": response})
    play_audio_message(response)
    save_to_sheets(sheet, {
        'question': st.session_state.initial_question,
        'response': response
    }, st.session_state.initial_keywords)
    st.session_state.contact_step = None
    st.session_state.focus = "chat_input"
    st.rerun()

def handle_user_input(text):
    """사용자 입력 처리 통합 함수"""
    if len(st.session_state.messages) == 2 and not st.session_state.button_pressed:
        st.session_state.initial_question = text
        st.session_state.initial_keywords = extract_keywords(text)
        keywords = st.session_state.initial_keywords
        
        query_msg = f"아, {keywords}에 대해 궁금하시군요? 답변 드리기 전에 미리 연락처를 남겨 주시면 필요한 고급 자료나 뉴스레터를 보내드릴 수 있어요. 잠시만요!"
        st.session_state.messages.append({"role": "assistant", "content": query_msg})
        play_audio_message(query_msg)
        
        col1, col2 = st.columns(2)
        with col1:
            st.button("예", on_click=handle_yes_click, use_container_width=True)
        with col2:
            st.button("아니오", on_click=handle_no_click, use_container_width=True)
    
    elif not st.session_state.contact_step:
        response = model.generate_content(text).text
        st.session_state.messages.append({"role": "assistant", "content": response})
        play_audio_message(response)
        
        save_to_sheets(sheet, {
            'question': text,
            'response': response,
            'name': st.session_state.user_info.get('name', ''),
            'email': st.session_state.user_info.get('email', ''),
            'phone': st.session_state.user_info.get('phone', '')
        }, st.session_state.initial_keywords)

def handle_contact_confirm(choice):
    """연락처 확인 처리"""
    if choice == "yes":  # 수정하기
        st.session_state.button_pressed = False
        st.session_state.contact_step = 0
        message = "이름이 어떻게 되세요?"
        st.session_state.messages.append({"role": "assistant", "content": message})
        play_audio_message(message)
        st.session_state.focus = "name_input"
        st.rerun()
    else:  # 수정 안함
        st.session_state.button_pressed = True
        response = model.generate_content(st.session_state.initial_question).text
        st.session_state.messages.append({"role": "assistant", "content": response})
        play_audio_message(response)
        
        save_to_sheets(sheet, {
            'question': st.session_state.initial_question,
            'response': response,
            'name': st.session_state.user_info['name'],
            'email': st.session_state.user_info['email'],
            'phone': st.session_state.user_info['phone']
        }, st.session_state.initial_keywords)
        
        st.session_state.contact_step = None
        st.session_state.focus = "chat_input"
        st.rerun()

# 제목
st.title("디마불사 AI 고객상담 챗봇")

try:
    # 서비스 초기화
    @st.cache_resource
    def init_google_sheets():
        SCOPES = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        credentials_dict = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, SCOPES)
        gc = gspread.authorize(creds)
        return gc.open_by_key(st.secrets["GOOGLE_SHEET_ID"]).sheet1

    @st.cache_resource
    def init_gemini():
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        return genai.GenerativeModel('gemini-pro')

    sheet = init_google_sheets()
    model = init_gemini()

    # 세션 상태 초기화
    if 'messages' not in st.session_state:
        st.session_state.messages = []
        st.session_state.user_info = {}
        st.session_state.contact_step = None
        st.session_state.initial_question = None
        st.session_state.initial_keywords = None
        st.session_state.button_pressed = False
        st.session_state.focus = "chat_input"
        st.session_state.initial_user_msg = None
        st.session_state.initial_assistant_msg = None
        st.session_state.contact_info_saved = False
        st.session_state.audio_data = None

        welcome_msg = "어서 오세요. 디마불사 최규문입니다. 무엇이 궁금하세요, 제미나이가 저 대신 24시간 응답해 드립니다."
        st.session_state.messages.append({"role": "assistant", "content": welcome_msg})
        play_audio_message(welcome_msg)

    # 채팅 메시지 표시
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    # 연락처 수집 프로세스
    if st.session_state.contact_step is not None:
        if st.session_state.contact_step == 0:
            name = st.text_input("", key="name_input", on_change=handle_contact_input, args=(1,), placeholder="이름 입력")
            if st.session_state.focus == "name_input":
                js = """
                <script>
                    var input = window.parent.document.querySelector('input[data-testid="name_input"]');
                    input.focus();
                </script>
                """
                st.components.v1.html(js)

        elif st.session_state.contact_step == 1:
            email = st.text_input("", key="email_input", on_change=handle_contact_input, args=(2,), placeholder="이메일 입력")
            if st.session_state.focus == "email_input":
                js = """
                <script>
                    var input = window.parent.document.querySelector('input[data-testid="email_input"]');
                    input.focus();
                </script>
                """
                st.components.v1.html(js)

        elif st.session_state.contact_step == 2:
            phone = st.text_input("", key="phone_input", on_change=handle_contact_input, args=(3,), placeholder="전화번호 입력")
            if st.session_state.focus == "phone_input":
                js = """
                <script>
                    var input = window.parent.document.querySelector('input[data-testid="phone_input"]');
                    input.focus();
                </script>
                """
                st.components.v1.html(js)

        elif st.session_state.contact_step == "confirm":
            col1, col2 = st.columns(2)
            with col1:
                st.button("예", key="confirm_yes", on_click=lambda: handle_contact_confirm("yes"), use_container_width=True)
            with col2:
                st.button("아니오", key="confirm_no", on_click=lambda: handle_contact_confirm("no"), use_container_width=True)

    # 사용자 입력 처리
    elif st.session_state.contact_step is None:
        # 음성/텍스트 입력 선택 탭
        input_tab1, input_tab2 = st.tabs(["음성으로 질문하기", "텍스트로 질문하기"])
        

        with input_tab1:
            # 음성 녹음 컴포넌트
            st.components.v1.html(js_code, height=100)
            
            # 음성 데이터 처리
            if 'audio_data' in st.session_state and st.session_state.audio_data:
                audio_data = st.session_state.audio_data
                st.audio(audio_data, format='audio/wav')
                # 여기에 음성인식 API 연동 코드 추가 가능
                st.session_state.audio_data = None  # 처리 후 초기화
        
        with input_tab2:
            if prompt := st.chat_input("궁금하신 내용을 입력해주세요...", key="chat_input"):
                st.chat_message("user").write(prompt)
                st.session_state.messages.append({"role": "user", "content": prompt})
                handle_user_input(prompt)

        if st.session_state.focus == "chat_input":
            js = """
            <script>
            document.addEventListener('DOMContentLoaded', function() {
                var input = window.parent.document.querySelector("textarea[data-testid='chat_input']");
                if (input) {
                    input.focus();
                }
            });
            </script>
            """
            st.components.v1.html(js)

    # 자동 스크롤
    if st.session_state.messages:
        js = """
        <script>
            function scroll_to_bottom() {
                var elements = window.parent.document.querySelectorAll('.stChatMessage');
                if (elements.length > 0) {
                    elements[elements.length - 1].scrollIntoView();
                }
            }
            scroll_to_bottom();
        </script>
        """
        st.components.v1.html(js, height=0)

except Exception as e:
    st.error(f"오류가 발생했습니다: {str(e)}")
