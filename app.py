import streamlit as st
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# 기본 페이지 설정
st.set_page_config(
    page_title="디마불사 AI 고객상담 챗봇",
    page_icon="🤖",
    layout="centered"
)

def extract_keywords(text):
    """핵심 키워드 추출 함수"""
    stop_words = ['은', '는', '이', '가', '을', '를', '에', '에서', '으로', '로', '하다', '입니다', '있다', '없다']
    words = text.split()
    keywords = [word for word in words if word not in stop_words][:2]
    return ' '.join(keywords)

def save_to_sheets(sheet, data, extracted_keywords=""):
    """구글 시트에 대화 내용 저장"""
    try:
        # 마지막 행의 사용자 정보 가져오기
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

        # 현재 사용자 정보 또는 이전 사용자 정보 사용
        name = data.get('name', '') or last_user_info['Name']
        email = data.get('email', '') or last_user_info['Email']
        phone = data.get('phone', '') or last_user_info['Phone']

        # 시트에 데이터 추가
        sheet.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  # Datetime
            extracted_keywords,                             # Keyword
            data.get('question', ''),                      # User Message
            data.get('response', ''),                      # Assistant Message
            name,                                          # Name
            email,                                         # Email
            phone                                          # Phone
        ])
    except Exception as e:
        st.error(f"데이터 저장 중 오류 발생: {str(e)}")

def handle_yes_click():
    """[예] 버튼 클릭 시 즉시 실행"""
    st.session_state.button_pressed = True
    st.session_state.contact_step = 0
    st.session_state.messages.append({"role": "assistant", "content": "이름이 어떻게 되세요?"})
    st.rerun()

def handle_no_click():
    """[아니오] 버튼 클릭 시 즉시 실행"""
    st.session_state.button_pressed = True
    response = model.generate_content(st.session_state.initial_question).text
    st.session_state.messages.append({"role": "assistant", "content": response})
    save_to_sheets(sheet, {
        'question': st.session_state.initial_question,
        'response': response
    }, st.session_state.initial_keywords)
    st.rerun()

def handle_contact_input(input_value, next_step, next_message=None):
    """연락처 입력 처리"""
    if input_value.strip():
        if next_step == 1:
            st.session_state.user_info['name'] = input_value
            next_msg = "이메일 주소는 어떻게 되세요?"
        elif next_step == 2:
            st.session_state.user_info['email'] = input_value
            next_msg = "휴대폰 번호는 어떻게 되세요?"
        elif next_step == 3:
            st.session_state.user_info['phone'] = input_value
            response = model.generate_content(st.session_state.initial_question).text
            st.session_state.messages.extend([
                {"role": "assistant", "content": "연락처 정보를 알려주셔서 고맙습니다. 그럼 앞서 질문하신 내용에 대해 답변드릴게요."},
                {"role": "assistant", "content": response}
            ])
            save_to_sheets(sheet, {
                'question': st.session_state.initial_question,
                'response': response,
                'name': st.session_state.user_info['name'],
                'email': st.session_state.user_info['email'],
                'phone': input_value
            }, st.session_state.initial_keywords)
            st.session_state.contact_step = None
        else:
            return
            
        if next_step != 3:
            st.session_state.contact_step = next_step
            st.session_state.messages.append({"role": "assistant", "content": next_msg})
        st.rerun()

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

    # 서비스 초기화
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
        
        # 시작 메시지 추가
        welcome_msg = "어서 오세요. 디마불사 최규문입니다. 무엇이 궁금하세요, 제미나이가 저 대신 24시간 응답해 드립니다."
        st.session_state.messages.append({"role": "assistant", "content": welcome_msg})

    # 채팅 메시지 표시
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    # 연락처 수집 프로세스
    if st.session_state.contact_step is not None:
        if st.session_state.contact_step == 0:
            value = st.text_input("이름 입력", key="name_input", label_visibility="collapsed")
            st.button("다음", key="name_next", on_click=handle_contact_input, 
                     args=(value, 1), use_container_width=True)
        
        elif st.session_state.contact_step == 1:
            value = st.text_input("이메일 입력", key="email_input", label_visibility="collapsed")
            st.button("다음", key="email_next", on_click=handle_contact_input, 
                     args=(value, 2), use_container_width=True)
        
        elif st.session_state.contact_step == 2:
            value = st.text_input("전화번호 입력", key="phone_input", label_visibility="collapsed")
            st.button("완료", key="phone_next", on_click=handle_contact_input, 
                     args=(value, 3), use_container_width=True)

    # 사용자 입력 처리
    if prompt := st.chat_input("궁금하신 내용을 입력해주세요..."):
        # 사용자 메시지 추가
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # 첫 질문인 경우
        if len(st.session_state.messages) == 2 and not st.session_state.button_pressed:
            st.session_state.initial_question = prompt
            st.session_state.initial_keywords = extract_keywords(prompt)
            
            keywords = st.session_state.initial_keywords
            query_msg = f"아, {keywords}에 대해 궁금하시군요? 답변 드리기 전에 미리 연락처를 남겨 주시면 필요한 고급 자료나 뉴스레터를 보내드립니다. 연락처를 남겨주시겠어요?"
            st.session_state.messages.append({"role": "assistant", "content": query_msg})
            
            # 버튼 표시
            col1, col2 = st.columns(2)
            with col1:
                st.button("예", on_click=handle_yes_click, use_container_width=True)
            with col2:
                st.button("아니오", on_click=handle_no_click, use_container_width=True)
            st.rerun()
        
        # 일반 대화
        elif not st.session_state.contact_step:
            response = model.generate_content(prompt).text
            st.session_state.messages.append({"role": "assistant", "content": response})
            
            save_to_sheets(sheet, {
                'question': prompt,
                'response': response,
                'name': st.session_state.user_info.get('name', ''),
                'email': st.session_state.user_info.get('email', ''),
                'phone': st.session_state.user_info.get('phone', '')
            })
            st.rerun()

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
