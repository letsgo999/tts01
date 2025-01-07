import streamlit as st
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz

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

def extract_keywords(text):
    """핵심 키워드 추출 함수"""
    stop_words = ['은', '는', '이', '가', '을', '를', '에', '에서', '으로', '로', '하다', '입니다', '있다', '없다']
    words = text.split()
    keywords = [word for word in words if word not in stop_words][:2]
    return ' '.join(keywords)

def save_to_sheets(sheet, data, extracted_keywords=""):
    """구글 시트에 대화 내용 저장"""
    try:
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
            get_korean_time(),  # Datetime (한국 시간)
            extracted_keywords,  # Keyword
            data.get('question', ''),  # User Message
            data.get('response', ''),  # Assistant Message
            name,  # Name
            email,  # Email
            phone  # Phone
        ])
    except Exception as e:
        st.error(f"데이터 저장 중 오류 발생: {str(e)}")

def handle_yes_click():
    """[예] 버튼 클릭 시 즉시 실행"""
    st.session_state.button_pressed = True
    st.session_state.contact_step = 0
    st.session_state.messages.append({"role": "assistant", "content": "이름이 어떻게 되세요?"})
    st.session_state.focus = "name_input"

def handle_no_click():
    """[아니오] 버튼 클릭 시 즉시 실행"""
    st.session_state.button_pressed = True
    response = model.generate_content(st.session_state.initial_question).text
    st.session_state.messages.append({"role": "assistant", "content": response})
    save_to_sheets(sheet, {
        'question': st.session_state.initial_question,
        'response': response
    }, st.session_state.initial_keywords)
    st.session_state.contact_step = None  # 연락처 수집 종료

def handle_contact_input(next_step):
    """연락처 입력 처리"""
    focus_key = st.session_state.focus
    if focus_key in st.session_state and st.session_state[focus_key].strip():
        value = st.session_state[focus_key]
        # 사용자 입력을 대화창에 표시
        st.session_state.messages.append({"role": "user", "content": value})
        
        if next_step == 1:
            st.session_state.user_info['name'] = value
            st.session_state.messages.append({"role": "assistant", "content": "이메일 주소는 어떻게 되세요?"})
            st.session_state.contact_step = next_step
            st.session_state.focus = "email_input"  # 이메일 입력에 커서 자동 이동
        
        elif next_step == 2:
            st.session_state.user_info['email'] = value
            st.session_state.messages.append({"role": "assistant", "content": "휴대폰 번호는 어떻게 되세요?"})
            st.session_state.contact_step = next_step
            st.session_state.focus = "phone_input"  # 휴대폰번호 입력에 커서 자동 이동
        
        elif next_step == 3:
            st.session_state.user_info['phone'] = value
            confirm_msg = """
            연락처 정보를 알려주셔서 고맙습니다. 입력하신 내용에 틀린 곳이 있으면 지금 수정해 주세요. 수정하시겠어요?
            """
            st.session_state.messages.append({"role": "assistant", "content": confirm_msg})
            st.session_state.contact_step = "confirm"
            st.session_state.focus = None  # 커서 이동 중지 및 확인 버튼 표시

def handle_contact_confirm(choice):
    """연락처 확인 처리"""
    if choice == "yes": #수정하기
        # 연락처 수정을 위해 처음부터 다시 시작
        st.session_state.contact_step = 0
        st.session_state.messages.append({"role": "assistant", "content": "이름이 어떻게 되세요?"})
        st.session_state.focus = "name_input"
    elif choice == "no": #수정 안함
        # AI 응답 생성 및 저장
        response = model.generate_content(st.session_state.initial_question).text
        st.session_state.messages.append({"role": "assistant", "content": response})
        
        save_to_sheets(sheet, {
            'question': st.session_state.initial_question,
            'response': response,
            'name': st.session_state.user_info['name'],
            'email': st.session_state.user_info['email'],
            'phone': st.session_state.user_info['phone']
        }, st.session_state.initial_keywords)
        
        st.session_state.contact_step = None # 연락처 수집 종료

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
        st.session_state.focus = None
        
        # 시작 메시지 추가
        welcome_msg = "어서 오세요. 디마불사 최규문입니다. 무엇이 궁금하세요, 제미나이가 저 대신 24시간 응답해 드립니다."
        st.session_state.messages.append({"role": "assistant", "content": welcome_msg})

    # 각 입력 단계별 초기화
    if 'name_input' not in st.session_state:
        st.session_state.name_input = ""
    if 'email_input' not in st.session_state:
        st.session_state.email_input = ""
    if 'phone_input' not in st.session_state:
        st.session_state.phone_input = ""

    # 채팅 메시지 표시
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    # 연락처 수집 프로세스
    if st.session_state.contact_step is not None:
        if st.session_state.contact_step == 0:
            name = st.text_input("이름 입력", key="name_input", on_change=handle_contact_input, args=(1,))
            if "name_input" in st.session_state and st.session_state.focus == "name_input":
                js = f"""
                <script>
                    setTimeout(function() {{
                        document.querySelector('input[data-testid="name_input"]').focus();
                    }}, 100);
                </script>
                """
                st.components.v1.html(js, height=0)
        
        elif st.session_state.contact_step == 1:
            email = st.text_input("이메일 입력", key="email_input", on_change=handle_contact_input, args=(2,))
            if "email_input" in st.session_state and st.session_state.focus == "email_input":
                js = f"""
                    <script>
                        setTimeout(function() {{
                            document.querySelector('input[data-testid="email_input"]').focus();
                        }}, 100);
                    </script>
                    """
                st.components.v1.html(js, height=0)
        
        elif st.session_state.contact_step == 2:
            phone = st.text_input("전화번호 입력", key="phone_input", on_change=handle_contact_input, args=(3,))
            if "phone_input" in st.session_state and st.session_state.focus == "phone_input":
                js = f"""
                    <script>
                        setTimeout(function() {{
                            document.querySelector('input[data-testid="phone_input"]').focus();
                        }}, 100);
                    </script>
                    """
                st.components.v1.html(js, height=0)
        
        elif st.session_state.contact_step == "confirm":
            col1, col2 = st.columns(2)
            with col1:
                if st.button("예", key="confirm_yes", use_container_width=True):
                    handle_contact_confirm("yes")
            with col2:
                if st.button("아니오", key="confirm_no", use_container_width=True):
                    handle_contact_confirm("no")

    # 사용자 입력 처리
    if st.session_state.contact_step is None:
        if prompt := st.chat_input("궁금하신 내용을 입력해주세요..."):
            # 사용자 메시지 표시
            st.chat_message("user").write(prompt)
            st.session_state.messages.append({"role": "user", "content": prompt})
            
            # 첫 질문인 경우
            if len(st.session_state.messages) == 2 and not st.session_state.button_pressed:
                # 키워드 추출 및 초기 질문 저장
                st.session_state.initial_question = prompt
                st.session_state.initial_keywords = extract_keywords(prompt)
                keywords = st.session_state.initial_keywords
                
                # 연락처 요청 메시지 표시
                query_msg = f"아, {keywords}에 대해 궁금하시군요? 답변 드리기 전에 미리 연락처를 남겨 주시면 필요한 고급 자료나 뉴스레터를 보내드릴 수 있어요. 잠시만요!"
                st.chat_message("assistant").write(query_msg)
                st.session_state.messages.append({"role": "assistant", "content": query_msg})
                
                # 예/아니오 버튼 표시
                col1, col2 = st.columns(2)
                with col1:
                    st.button("예", on_click=handle_yes_click, use_container_width=True)
                with col2:
                    st.button("아니오", on_click=handle_no_click, use_container_width=True)
            
            # 일반 대화 처리
            elif not st.session_state.contact_step:
                response = model.generate_content(prompt).text
                st.chat_message("assistant").write(response)
                st.session_state.messages.append({"role": "assistant", "content": response})
                
                save_to_sheets(sheet, {
                    'question': prompt,
                    'response': response,
                    'name': st.session_state.user_info.get('name', ''),
                    'email': st.session_state.user_info.get('email', ''),
                    'phone': st.session_state.user_info.get('phone', '')
                }, st.session_state.initial_keywords)

    # 자동 포커스를 위한 JavaScript 추가
    # if 'focus' in st.session_state and st.session_state.focus:
    #     js = f"""
    #     <script>
    #         setTimeout(function() {{
    #             document.querySelector('input[data-testid="{st.session_state.focus}"]').focus();
    #         }}, 100);
    #     </script>
    #     """
    #     st.components.v1.html(js, height=0)

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
