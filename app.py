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
        
        # 시작 메시지 추가
        welcome_msg = "어서 오세요. 디마불사 최규문입니다. 무엇이 궁금하세요, 제미나이가 저 대신 24시간 응답해 드립니다."
        st.session_state.messages.append({"role": "assistant", "content": welcome_msg})

    # 연락처 수집 프로세스
    if st.session_state.contact_step is not None:
        if st.session_state.contact_step == 0:
            with st.chat_message("assistant"):
                st.write("이름이 어떻게 되세요?")
            name = st.text_input("이름 입력", key="name_input", label_visibility="collapsed")
            if st.button("다음"):
                if name.strip():
                    st.session_state.user_info['name'] = name
                    st.session_state.contact_step = 1
                    st.rerun()
        
        elif st.session_state.contact_step == 1:
            with st.chat_message("assistant"):
                st.write("이메일 주소는 어떻게 되세요?")
            email = st.text_input("이메일 입력", key="email_input", label_visibility="collapsed")
            if st.button("다음"):
                if email.strip():
                    st.session_state.user_info['email'] = email
                    st.session_state.contact_step = 2
                    st.rerun()
        
        elif st.session_state.contact_step == 2:
            with st.chat_message("assistant"):
                st.write("휴대폰 번호는 어떻게 되세요?")
            phone = st.text_input("전화번호 입력", key="phone_input", label_visibility="collapsed")
            if st.button("완료"):
                if phone.strip():
                    st.session_state.user_info['phone'] = phone
                    st.session_state.messages.append({"role": "assistant", "content": 
                        "연락처 정보를 알려주셔서 고맙습니다. 그럼 앞서 질문하신 내용에 대해 답변드릴게요."})
                    
                    # 저장된 초기 질문에 대한 응답 생성
                    response = model.generate_content(st.session_state.initial_question).text
                    st.session_state.messages.append({"role": "assistant", "content": response})
                    
                    # 대화 내용 저장
                    sheet.append_row([
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        st.session_state.user_info['name'],
                        st.session_state.user_info['email'],
                        st.session_state.user_info['phone'],
                        st.session_state.initial_question,
                        response
                    ])
                    
                    st.session_state.contact_step = None
                    st.rerun()

    # 채팅 메시지 표시
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    # 사용자 입력 처리
    if st.session_state.contact_step is None:
        if prompt := st.chat_input("궁금하신 내용을 입력해주세요..."):
            # 사용자 메시지 추가
            st.session_state.messages.append({"role": "user", "content": prompt})
            st.chat_message("user").write(prompt)

            # 첫 질문인 경우
            if len(st.session_state.messages) == 2:
                # 초기 질문 저장
                st.session_state.initial_question = prompt
                
                keywords = extract_keywords(prompt)
                query_msg = f"아, {keywords}에 대해 궁금하시군요? 답변 드리기 전에 미리 연락처를 남겨 주시면 필요한 고급 자료나 뉴스레터를 보내드립니다. 연락처를 남겨주시겠어요?"
                
                st.session_state.messages.append({"role": "assistant", "content": query_msg})
                with st.chat_message("assistant"):
                    st.write(query_msg)
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("예"):
                            st.session_state.contact_step = 0
                            st.rerun()
                    with col2:
                        if st.button("아니오"):
                            response = model.generate_content(prompt).text
                            st.session_state.messages.append({"role": "assistant", "content": response})
                            sheet.append_row([
                                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                '', '', '', prompt, response
                            ])
                            st.rerun()

            else:
                # AI 응답 생성
                response = model.generate_content(prompt).text
                st.session_state.messages.append({"role": "assistant", "content": response})
                
                # 대화 내용 저장
                sheet.append_row([
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    st.session_state.user_info.get('name', ''),
                    st.session_state.user_info.get('email', ''),
                    st.session_state.user_info.get('phone', ''),
                    prompt,
                    response
                ])
                st.rerun()

except Exception as e:
    st.error(f"오류가 발생했습니다: {str(e)}")
