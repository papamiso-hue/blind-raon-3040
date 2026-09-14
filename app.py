import streamlit as st
import streamlit.components.v1 as components
import re
import uuid
import math
import io
import json
import random
import requests
from datetime import datetime, timedelta, timezone
import pandas as pd
from supabase import create_client, Client
from pypdf import PdfReader

# 1. 스트림릿 기본 페이지 설정
st.set_page_config(
    page_title="블라인드 라온 - 3040 프라이빗 소셜 클럽",
    page_icon="💼",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# 2. PWA 모바일 웹앱 메타태그 주입
st.markdown("""
<head>
    <title>블라인드 라온</title>
    <meta name="apple-mobile-web-app-title" content="블라인드 라온">
    <meta name="application-name" content="블라인드 라온">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="mobile-web-app-capable" content="yes">
    <link rel="apple-touch-icon" href="https://images.unsplash.com/photo-1507679799987-c73779587ccf?w=192&auto=format&fit=crop">
    <link rel="icon" type="image/png" href="https://images.unsplash.com/photo-1507679799987-c73779587ccf?w=192&auto=format&fit=crop">
</head>
""", unsafe_allow_html=True)

# 3. 서비스 기본 상수
BRAND_NAME_KR = "블라인드 라온"
BRAND_NAME_EN = "BLIND RAON 3040"
SITE_URL = "https://blind-raon-3040-xtwjdberufkkgwje2abbzq.streamlit.app"
OG_IMAGE_URL = "https://images.unsplash.com/photo-1507679799987-c73779587ccf?q=80&w=1200&auto=format&fit=crop"
KAKAO_CHAT_URL = "https://open.kakao.com/o/sRas35Li"

ALIGO_API_KEY = "a2d6ej9asoilb20w66tmw6zw3qqp7shk"
ALIGO_USER_ID = "equivision"
ALIGO_SENDER = "01030383349"

# 4. 플랫폼 전용 맞춤법/오타 검증 규칙
PLATFORM_TYPO_RULES = {
    r"안녕하새요": "안녕하세요",
    r"결재": "결제(이용권/티켓 결제)",
    r"됍니다": "됩니다",
    r"되요": "돼요",
    r"뵈요": "봬요",
    r"몇일": "며칠",
    r"바램": "바람",
    r"어의없": "어이없",
    r"신용점숫": "신용점수"
}

def audit_text_typos(text: str):
    if not text:
        return []
    warnings = []
    for pattern, correct in PLATFORM_TYPO_RULES.items():
        if re.search(pattern, text):
            warnings.append(f"'{pattern}' ➡️ '{correct}'")
    return warnings

KOREA_REGIONS = {
    "서울특별시": [
        "강남구", "강동구", "강북구", "강서구", "관악구", "광진구", "구로구", "금천구",
        "노원구", "도봉구", "동대문구", "동작구", "마포구", "서대문구", "서초구", "성동구",
        "성북구", "송파구", "양천구", "영등포구", "용산구", "은평구", "종로구", "중구", "중랑구"
    ],
    "경기도": [
        "수원시 장안구", "수원시 권선구", "수원시 팔달구", "수원시 영통구",
        "성남시 수정구", "성남시 중원구", "성남시 분당구",
        "의정부시", "안양시 만안구", "안양시 동안구", "부천시 원미구", "부천시 소사구", "부천시 오정구",
        "광명시", "평택시", "동두천시", "안산시 상록구", "안산시 단원구", "고양시 덕양구", "고양시 일산동구", "고양시 일산서구",
        "과천시", "구리시", "남양주시", "오산시", "시흥시", "군포시", "의왕시", "하남시",
        "용인시 처인구", "용인시 기흥구", "용인시 수지구", "파주시", "이천시", "안성시", "김포시", "화성시",
        "광주시", "양주시", "포천시", "여주시", "연천군", "가평군", "양평군"
    ],
    "인천광역시": ["중구", "동구", "미추홀구", "연수구", "남동구", "부평구", "계양구", "서구", "강화군", "옹진군"],
    "부산광역시": ["중구", "서구", "동구", "영도구", "부산진구", "동래구", "남구", "북구", "해운대구", "사하구", "금정구", "강서구", "연제구", "수영구", "사상구", "기장군"],
    "대구광역시": ["중구", "동구", "서구", "남구", "북구", "수성구", "달서구", "달성군", "군위군"],
    "대전광역시": ["동구", "중구", "서구", "유성구", "대덕구"],
    "세종특별자치시": ["세종시 전역"]
}

CORE_QUESTIONS_3040 = {
    1: {
        "text": "1. 결혼 희망 시점 및 방향?",
        "options": ["1~2년 이내 확고한 결혼 희망", "2~3년 정도 진중한 연애 후 결정", "결혼에 얽매이지 않는 진지한 연인 관계", "비혼주의 / 각자 독립성 존중"]
    },
    2: {
        "text": "2. 자녀 계획에 대한 생각?",
        "options": ["결혼 후 자녀 계획 필수", "상호 협의 후 유연하게 결정", "딩크(DINK: 자녀 없이 둘만의 삶)", "상대방 의견에 전적으로 맞춤"]
    },
    3: {
        "text": "3. 신혼 거주지 마련 및 자산 관리?",
        "options": ["공동 자금 조성 및 부부 공동명의 매매", "각자 자산 독립 관리 + 공동 생활비 통장", "전세 시작 후 주택청약/재테크 공략", "상대방 또는 본인 보유 주택 입주"]
    },
    4: {
        "text": "4. 재테크 및 소비 성향?",
        "options": ["부동산/주식/가상자산 적극 투자형", "예적금/연금/ETF 중심 안정형", "자기계발·여행·취미를 위한 현재 중심 소비형", "계획적인 지출 통제 및 알뜰 저축형"]
    },
    5: {
        "text": "5. 생활 습관 및 라이프스타일 필터?",
        "options": ["비흡연 필수 + 음주는 가볍게 즐김", "비흡연 필수 + 술자리 전혀 안 함", "전자담배/흡연 양해 가능", "반려동물(반려견/묘) 친화적 환경 필수"]
    }
}

# --- 프리미엄 3040 리뉴얼 UI CSS (웹폰트 Pretendard 탑재 및 카드형 UI) ---
st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');

    .stApp {
        background: radial-gradient(circle at 50% 0%, #172554 0%, #090D16 60%, #05070B 100%) !important;
        color: #F8FAFC !important;
        font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, Roboto, sans-serif !important;
    }
    .block-container { 
        padding-top: 1.2rem !important; 
        padding-bottom: 4rem !important; 
        max-width: 520px !important; 
    }

    /* 상단 헤더 */
    .app-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 10px 0 16px 0;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        margin-bottom: 16px;
    }
    .app-brand {
        font-size: 1.25rem;
        font-weight: 900;
        letter-spacing: -0.5px;
        background: linear-gradient(90deg, #FFFFFF 0%, #93C5FD 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    /* 히어로 박스 */
    .hero-box {
        background: linear-gradient(160deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.8) 100%);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(96, 165, 250, 0.25);
        border-radius: 20px;
        padding: 24px 20px;
        text-align: center;
        margin-bottom: 1.2rem;
        box-shadow: 0 16px 36px -10px rgba(37, 99, 235, 0.25);
    }
    .hero-badge {
        display: inline-block;
        background: rgba(59, 130, 246, 0.15);
        border: 1px solid rgba(96, 165, 250, 0.4);
        color: #60A5FA !important;
        font-size: 0.72rem;
        font-weight: 800;
        letter-spacing: 1.5px;
        padding: 4px 14px;
        border-radius: 9999px;
        margin-bottom: 10px;
    }
    .hero-title {
        font-size: 1.9rem;
        font-weight: 900;
        line-height: 1.25;
        letter-spacing: -0.8px;
        color: #FFFFFF !important;
        margin-bottom: 8px;
    }
    .hero-subtitle {
        font-size: 0.92rem;
        font-weight: 500;
        color: #94A3B8 !important;
        line-height: 1.55;
    }

    /* 3중 검증 안내 카드 */
    .promise-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 8px;
        margin-bottom: 1.2rem;
    }
    .promise-card {
        background: rgba(15, 23, 42, 0.65);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 14px;
        padding: 12px 6px;
        text-align: center;
    }
    .promise-icon { font-size: 1.3rem; margin-bottom: 3px; }
    .promise-title { font-size: 0.8rem; font-weight: 800; color: #E2E8F0 !important; }
    .promise-desc { font-size: 0.68rem; color: #64748B !important; margin-top: 2px; }

    /* 대형 세로형 프로필 매칭 카드 (인스타/틴더 스타일) */
    .feed-card {
        position: relative;
        border-radius: 22px;
        overflow: hidden;
        margin-bottom: 1.6rem;
        background: #0F172A;
        border: 1px solid rgba(96, 165, 250, 0.2);
        box-shadow: 0 20px 30px -10px rgba(0, 0, 0, 0.6);
    }
    .feed-img-box {
        position: relative;
        width: 100%;
        height: 380px;
        overflow: hidden;
    }
    .feed-img-blur {
        width: 100%;
        height: 100%;
        object-fit: cover;
        filter: blur(10px) brightness(0.85);
        transform: scale(1.08);
    }
    .feed-img-clear {
        width: 100%;
        height: 100%;
        object-fit: cover;
    }
    .feed-overlay {
        position: absolute;
        bottom: 0;
        left: 0;
        right: 0;
        height: 60%;
        background: linear-gradient(to top, #0F172A 15%, transparent 100%);
        pointer-events: none;
    }
    .feed-blind-tag {
        position: absolute;
        top: 16px;
        left: 16px;
        background: rgba(15, 23, 42, 0.75);
        backdrop-filter: blur(8px);
        border: 1px solid rgba(255, 255, 255, 0.15);
        padding: 5px 12px;
        border-radius: 20px;
        font-size: 0.72rem;
        font-weight: 800;
        color: #93C5FD;
    }
    .feed-match-badge {
        position: absolute;
        top: 16px;
        right: 16px;
        background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%);
        padding: 6px 14px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 900;
        color: #FFFFFF;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.4);
    }
    .feed-content {
        padding: 16px 20px 20px 20px;
        margin-top: -24px;
        position: relative;
    }
    .feed-name-row {
        display: flex;
        align-items: baseline;
        gap: 8px;
        margin-bottom: 8px;
    }
    .feed-name {
        font-size: 1.45rem;
        font-weight: 900;
        color: #FFFFFF;
        letter-spacing: -0.5px;
    }
    .feed-age {
        font-size: 1.1rem;
        font-weight: 600;
        color: #94A3B8;
    }
    .badge-pill-job {
        background: rgba(59, 130, 246, 0.15);
        color: #93C5FD;
        border: 1px solid rgba(96, 165, 250, 0.3);
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.76rem;
        font-weight: 800;
    }
    .badge-pill-score {
        background: rgba(16, 185, 129, 0.15);
        color: #6EE7B7;
        border: 1px solid rgba(16, 185, 129, 0.3);
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.76rem;
        font-weight: 800;
    }
    .feed-intro {
        margin-top: 10px;
        font-size: 0.9rem;
        color: #CBD5E1;
        line-height: 1.5;
        font-style: italic;
    }

    /* 모던 탭 스타일 */
    div[data-baseweb="tab-list"] {
        background-color: rgba(15, 23, 42, 0.8) !important;
        padding: 5px;
        border-radius: 14px;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        margin-bottom: 1.4rem;
        gap: 4px;
    }
    div[data-baseweb="tab"] {
        flex: 1;
        height: 44px;
        border-radius: 10px !important;
        background-color: transparent !important;
        color: #64748B !important;
        font-weight: 800 !important;
        font-size: 0.92rem !important;
        border: none !important;
    }
    div[data-baseweb="tab"][aria-selected="true"] {
        background: #2563EB !important;
        color: #FFFFFF !important;
        box-shadow: 0 4px 14px rgba(37, 99, 235, 0.35);
    }
    div[data-baseweb="tab-border"] { display: none !important; }

    /* 입력창 및 버튼 */
    div[data-baseweb="input"] {
        background-color: rgba(15, 23, 42, 0.9) !important;
        border: 1.5px solid #1E293B !important;
        border-radius: 12px !important;
    }
    div[data-baseweb="input"]:focus-within {
        border-color: #3B82F6 !important;
        box-shadow: 0 0 0 1px #3B82F6 !important;
    }
    div[data-baseweb="input"] input { color: #FFFFFF !important; }

    .stButton>button { 
        width: 100%; 
        border-radius: 12px; 
        font-weight: 800; 
        height: 3.4rem;
        font-size: 1.05rem;
        letter-spacing: -0.3px;
        border: none !important;
        background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%) !important;
        color: #FFFFFF !important;
        box-shadow: 0 6px 18px rgba(37, 99, 235, 0.35);
        transition: transform 0.1s ease;
    }
    .stButton>button:active { transform: scale(0.98); }

    #MainMenu, footer, header { visibility: hidden !important; }
    </style>
""", unsafe_allow_html=True)

SUPABASE_URL = "https://xxiagepuzmukwcdnurhg.supabase.co"
SUPABASE_KEY = "sb_publishable_CCbsSoMbvLYh1y4xJ2zYEA_XxisldNn"

@st.cache_resource
def get_supabase_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = get_supabase_client()

def send_aligo_sms(receiver_phone, auth_code):
    try:
        url = "https://apis.aligo.in/send/"
        payload = {
            "key": ALIGO_API_KEY,
            "user_id": ALIGO_USER_ID,
            "sender": ALIGO_SENDER,
            "receiver": receiver_phone,
            "msg": f"[{BRAND_NAME_KR}] 본인인증 번호는 [{auth_code}] 입니다. (타인 유출 주의)",
            "testmode_yn": "N"
        }
        res = requests.post(url, data=payload, timeout=6)
        if res.status_code == 200 and res.json().get("result_code") == "1":
            return True, "인증번호가 발송되었습니다."
        return False, "인증문자 발송 실패"
    except Exception as e:
        return False, f"SMS 오류: {e}"

def send_aligo_notice_sms(receiver_phone, text_message):
    try:
        url = "https://apis.aligo.in/send/"
        payload = {
            "key": ALIGO_API_KEY,
            "user_id": ALIGO_USER_ID,
            "sender": ALIGO_SENDER,
            "receiver": receiver_phone,
            "msg": f"[{BRAND_NAME_KR}] {text_message}",
            "testmode_yn": "N"
        }
        requests.post(url, data=payload, timeout=6)
    except Exception:
        pass

DEFAULT_AVATARS = {
    "남": "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?q=80&w=600&auto=format&fit=crop",
    "여": "https://images.unsplash.com/photo-1494790108377-be9c29b29330?q=80&w=600&auto=format&fit=crop"
}

if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "user_info" not in st.session_state:
    st.session_state.user_info = None
if "sms_auth_code" not in st.session_state:
    st.session_state.sms_auth_code = None
if "sms_verified_phone" not in st.session_state:
    st.session_state.sms_verified_phone = None
if "sms_is_verified" not in st.session_state:
    st.session_state.sms_is_verified = False

# --- 1. 로그인 / 신규 가입 화면 ---
if not st.session_state.user_id:
    st.markdown(f"""
        <div class="hero-box">
            <div class="hero-badge">🔒 3040 PRIVATE BLIND CLUB</div>
            <div class="hero-title">💼 {BRAND_NAME_KR}</div>
            <div class="hero-subtitle">가벼운 만남은 지치고, 결정사는 부담스러운 3040을 위한<br>
            <strong style="color:#93C5FD;">직장·소득·신용 3중 검증 기반 프라이빗 매칭</strong></div>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("""
        <div class="promise-grid">
            <div class="promise-card">
                <div class="promise-icon">🛡️</div>
                <div class="promise-title">직장·소득 검증</div>
                <div class="promise-desc">명함/원천징수/750점+</div>
            </div>
            <div class="promise-card">
                <div class="promise-icon">🚫</div>
                <div class="promise-title">직장·지인 완벽차단</div>
                <div class="promise-desc">회사 동료 상호 미노출</div>
            </div>
            <div class="promise-card">
                <div class="promise-icon">🔒</div>
                <div class="promise-title">블라인드 프로필</div>
                <div class="promise-desc">상호 수락 시 얼굴 공개</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    tab_login, tab_join = st.tabs(["🔑 정회원 로그인", "📝 신규 프로필 등록"])

    with tab_login:
        login_name = st.text_input("성명", key="l_name")
        login_phone = st.text_input("휴대폰 번호 (- 제외 숫자만)", placeholder="01012345678", key="l_phone")
        login_pwd = st.text_input("간편 비밀번호 (4~6자리)", type="password", key="l_pwd")

        if st.button("안심 본인인증 로그인", key="btn_login"):
            clean_p = re.sub(r'[^0-9]', '', login_phone.strip())
            if not login_name.strip() or not clean_p or not login_pwd.strip():
                st.error("성명, 휴대폰 번호, 비밀번호를 모두 입력해 주세요.")
            else:
                res = supabase.table("users").select("*")\
                    .eq("name", login_name.strip())\
                    .eq("phone", clean_p)\
                    .eq("password", login_pwd.strip())\
                    .execute()
                if res.data:
                    u = res.data[0]
                    if u.get("is_suspended"):
                        st.error("🚫 제재 조치된 계정입니다. 고객센터로 문의해 주세요.")
                    else:
                        now_utc = datetime.now(timezone.utc).isoformat()
                        supabase.table("users").update({"last_login_at": now_utc}).eq("id", u["id"]).execute()
                        u["last_login_at"] = now_utc
                        st.session_state.user_id = u["id"]
                        st.session_state.user_info = u
                        st.rerun()
                else:
                    st.error("일치하는 회원 정보를 찾을 수 없습니다.")

    with tab_join:
        st.markdown("##### 👤 기본 인적사항 (만 28~45세 대상)")
        j_name = st.text_input("실명", key="j_name")
        
        col_p1, col_p2 = st.columns([2.5, 1.2])
        with col_p1:
            j_phone = st.text_input("휴대폰 번호 (- 제외)", placeholder="01012345678", key="j_phone")
        with col_p2:
            st.write("")
            btn_sms = st.button("인증번호 발송", key="btn_sms")

        clean_jp = re.sub(r'[^0-9]', '', j_phone.strip())
        if btn_sms:
            if len(clean_jp) < 10:
                st.error("올바른 휴대폰 번호를 입력해 주세요.")
            else:
                dup = supabase.table("users").select("id").eq("phone", clean_jp).execute().data
                if dup:
                    st.error("이미 등록된 휴대폰 번호입니다.")
                else:
                    code = str(random.randint(100000, 999999))
                    st.session_state.sms_auth_code = code
                    st.session_state.sms_verified_phone = clean_jp
                    st.session_state.sms_is_verified = False
                    send_aligo_sms(clean_jp, code)
                    st.success("문자로 발송된 6자리 인증번호를 입력해 주세요.")

        if st.session_state.sms_auth_code:
            c_code, c_btn = st.columns([2.5, 1.2])
            with c_code:
                in_code = st.text_input("인증번호 6자리", key="in_sms_code")
            with c_btn:
                st.write("")
                if st.button("인증 확인", key="btn_confirm_sms"):
                    if in_code.strip() == st.session_state.sms_auth_code:
                        st.session_state.sms_is_verified = True
                        st.success("✅ 휴대폰 인증이 완료되었습니다.")
                    else:
                        st.error("인증번호가 일치하지 않습니다.")

        j_pwd = st.text_input("간편 비밀번호 (4~6자리)", type="password", key="j_pwd")
        j_gender = st.radio("성별", ["남", "여"], horizontal=True, key="j_gender")
        j_age = st.number_input("나이 (만 나이)", 28, 45, 34, key="j_age")

        r_col1, r_col2 = st.columns(2)
        with r_col1:
            j_sido = st.selectbox("활동 광역시·도", list(KOREA_REGIONS.keys()), index=0, key="j_sido")
        with r_col2:
            j_sigungu = st.selectbox("시·군·구", KOREA_REGIONS[j_sido], index=0, key="j_sigungu")
        j_region = f"{j_sido} {j_sigungu}"

        st.markdown("##### 💼 커리어 및 신용 인증 (배지 부여)")
        j_job = st.text_input("직장명 및 직무", placeholder="예: 네이버 서비스기획 / 삼일회계법인 회계사", key="j_job")
        job_typos = audit_text_typos(j_job)
        if job_typos:
            st.caption(f"💡 표현 교정 안내: {', '.join(job_typos)}")

        j_intro = st.text_area("한 줄 자기소개 (가치관 및 지향하는 인연)", value="진중하고 품격 있는 인연을 희망합니다.", key="j_intro")
        intro_typos = audit_text_typos(j_intro)
        if intro_typos:
            st.caption(f"💡 소개글 맞춤법 안내: {', '.join(intro_typos)}")

        j_credit = st.number_input("공인 신용점수 (750점 이상 필수)", 0, 1000, 830, key="j_credit")
        j_doc = st.file_uploader("직장/소득/신용 증빙 서류 첨부 (명함, 사원증, 토스 신용캡처 등)", type=["jpg", "png", "pdf"], key="j_doc")

        st.markdown("##### 🎯 3040 필수 가치관 5대 문답")
        a1 = st.radio(CORE_QUESTIONS_3040[1]["text"], CORE_QUESTIONS_3040[1]["options"], key="jq_1")
        a2 = st.radio(CORE_QUESTIONS_3040[2]["text"], CORE_QUESTIONS_3040[2]["options"], key="jq_2")
        a3 = st.radio(CORE_QUESTIONS_3040[3]["text"], CORE_QUESTIONS_3040[3]["options"], key="jq_3")
        a4 = st.radio(CORE_QUESTIONS_3040[4]["text"], CORE_QUESTIONS_3040[4]["options"], key="jq_4")
        a5 = st.radio(CORE_QUESTIONS_3040[5]["text"], CORE_QUESTIONS_3040[5]["options"], key="jq_5")

        agree_terms = st.checkbox("[필수] 3040 프라이빗 소셜 클럽 이용약관 및 증빙서류 확인 즉시 영구 파기에 동의합니다.", key="agree_terms")

        if st.button("신원 검증 신청 및 가입 완료", key="btn_submit_join"):
            if not agree_terms:
                st.error("필수 이용약관에 동의해 주세요.")
            elif not j_name.strip():
                st.error("성명을 입력해 주세요.")
            elif not st.session_state.sms_is_verified or st.session_state.sms_verified_phone != clean_jp:
                st.error("휴대폰 SMS 인증을 완료해 주세요.")
            elif len(j_pwd.strip()) < 4:
                st.error("비밀번호는 최소 4자리 이상이어야 합니다.")
            elif j_credit < 750:
                st.error("입회 기준 미달: 블라인드 라온은 공인 신용점수 750점 이상만 승인됩니다.")
            elif not j_doc:
                st.error("신원 및 커리어/신용 증빙 서류를 첨부해 주세요.")
            else:
                doc_ext = j_doc.name.split(".")[-1].lower()
                doc_name = f"verify_{clean_jp}_{uuid.uuid4().hex[:6]}.{doc_ext}"
                try:
                    supabase.storage.from_("credit-docs").upload(
                        doc_name, 
                        j_doc.read(), 
                        {"content-type": "application/pdf" if doc_ext == "pdf" else f"image/{doc_ext}"}
                    )
                    doc_url = f"{SUPABASE_URL}/storage/v1/object/public/credit-docs/{doc_name}"
                    now_utc = datetime.now(timezone.utc).isoformat()

                    new_u = supabase.table("users").insert({
                        "name": j_name.strip(),
                        "phone": clean_jp,
                        "password": j_pwd.strip(),
                        "gender": j_gender,
                        "age": int(j_age),
                        "region": j_region,
                        "credit_score": int(j_credit),
                        "credit_doc_url": doc_url,
                        "credit_status": "PENDING",
                        "is_verified": False,
                        "ticket_count": 3,
                        "is_vip": False,
                        "blocked_phones": [],
                        "last_login_at": now_utc,
                        "job": j_job.strip() if j_job else "전문직/대기업",
                        "hobbies": "취미 및 여가",
                        "intro": j_intro.strip(),
                        "is_admin": False,
                        "is_suspended": False
                    }).execute().data[0]

                    uid = new_u["id"]
                    supabase.table("user_answers").insert([
                        {"user_id": uid, "question_num": 1, "answer_value": a1},
                        {"user_id": uid, "question_num": 2, "answer_value": a2},
                        {"user_id": uid, "question_num": 3, "answer_value": a3},
                        {"user_id": uid, "question_num": 4, "answer_value": a4},
                        {"user_id": uid, "question_num": 5, "answer_value": a5}
                    ]).execute()

                    st.session_state.user_id = uid
                    st.session_state.user_info = new_u
                    st.success("🎉 서류 제출 및 가입이 완료되었습니다! 웰컴 티켓 3장이 지급되었습니다.")
                    st.rerun()
                except Exception as e:
                    st.error(f"가입 처리 중 오류 발생: {e}")

# --- 2. 메인 대시보드 화면 ---
else:
    me = st.session_state.user_info

    st.markdown(f"""
        <div class="app-header">
            <div class="app-brand">💼 {BRAND_NAME_KR}</div>
            <div style="font-size:0.8rem; font-weight:800; color:#38BDF8;">🎟️ 티켓 {me.get('ticket_count', 0)}장</div>
        </div>
    """, unsafe_allow_html=True)

    with st.expander("🚫 아는 사람 / 직장 동료 번호 차단 관리"):
        curr_blocks = me.get("blocked_phones") or []
        b_input = st.text_input("차단할 휴대폰 번호 (- 제외)", placeholder="예: 01098765432", key="in_block_p")
        if st.button("차단 목록에 등록"):
            clean_bp = re.sub(r'[^0-9]', '', b_input.strip())
            if len(clean_bp) >= 10 and clean_bp not in curr_blocks:
                curr_blocks.append(clean_bp)
                supabase.table("users").update({"blocked_phones": curr_blocks}).eq("id", me["id"]).execute()
                me["blocked_phones"] = curr_blocks
                st.session_state.user_info = me
                st.success(f"{clean_bp} 번호가 상호 차단되었습니다.")
                st.rerun()

    tabs_main = st.tabs(["✨ 추천 피드", "📬 신청 보관함", "👤 내 프로필"])

    my_ans_data = supabase.table("user_answers").select("question_num, answer_value").eq("user_id", me["id"]).execute().data
    my_answers = {item["question_num"]: item["answer_value"] for item in my_ans_data}

    with tabs_main[0]:
        target_gender = "여" if me["gender"] == "남" else "남"
        raw_candidates = supabase.table("users").select("*").eq("gender", target_gender).eq("is_suspended", False).execute().data

        my_blocked_set = set(me.get("blocked_phones") or [])
        my_phone = me.get("phone", "")

        candidates = []
        for cand in raw_candidates:
            c_phone = cand.get("phone", "")
            c_blocked = set(cand.get("blocked_phones") or [])
            if c_phone in my_blocked_set or my_phone in c_blocked:
                continue
            candidates.append(cand)

        sent_reqs = supabase.table("match_requests").select("receiver_id, status").eq("sender_id", me["id"]).execute().data
        sent_dict = {req["receiver_id"]: req["status"] for req in sent_reqs}

        if not candidates:
            st.info("현재 활동 중인 추천 회원이 없습니다.")
        else:
            cand_scores = []
            for cand in candidates:
                c_ans_data = supabase.table("user_answers").select("question_num, answer_value").eq("user_id", cand["id"]).execute().data
                c_answers = {item["question_num"]: item["answer_value"] for item in c_ans_data}
                
                common_keys = set(my_answers.keys()).intersection(set(c_answers.keys()))
                score = int((sum(1 for k in common_keys if my_answers[k] == c_answers[k]) / len(common_keys)) * 100) if common_keys else 0
                cand_scores.append((cand, c_answers, common_keys, score))

            cand_scores.sort(key=lambda x: x[3], reverse=True)

            for cand, c_answers, common_keys, score in cand_scores:
                c_img = cand.get("photo_url") or DEFAULT_AVATARS.get(cand["gender"])
                intro_txt = cand.get("intro") or "가치관과 라이프스타일이 통하는 소중한 인연을 기다립니다."

                st.markdown(f"""
                    <div class="feed-card">
                        <div class="feed-img-box">
                            <img src="{c_img}" class="feed-img-blur">
                            <div class="feed-overlay"></div>
                            <div class="feed-blind-tag">🔒 블라인드 보호 중</div>
                            <div class="feed-match-badge">{score}% 매칭</div>
                        </div>
                        <div class="feed-content">
                            <div class="feed-name-row">
                                <span class="feed-name">{cand['name'][0]}*님</span>
                                <span class="feed-age">{cand['age']}세 · {cand['region'].split()[0]}</span>
                            </div>
                            <div style="display:flex; gap:6px; flex-wrap:wrap; margin-bottom:10px;">
                                <span class="badge-pill-job">💼 {cand.get('job', '전문직/대기업')}</span>
                                <span class="badge-pill-score">🛡️ 신용 {cand['credit_score']}점</span>
                            </div>
                            <div class="feed-intro">"{intro_txt}"</div>
                        </div>
                    </div>
                """, unsafe_allow_html=True)

                with st.expander("🔍 5대 가치관 상세 대조표"):
                    for q_num in sorted(list(CORE_QUESTIONS_3040.keys())):
                        q_text = CORE_QUESTIONS_3040[q_num]["text"]
                        m_val = my_answers.get(q_num, "미응답")
                        c_val = c_answers.get(q_num, "미응답")
                        is_match = (m_val == c_val)
                        match_label = "🟢 일치" if is_match else "⚪ 상이"
                        st.markdown(f"**[{match_label}] {q_text}**")
                        st.caption(f"• 내 답변: {m_val} | 상대방: {c_val}")

                req_status = sent_dict.get(cand["id"])
                if req_status == "PENDING":
                    st.button(f"⏳ 대화 수락 대기중 ({cand['name'][0]}*님)", key=f"feed_btn_{cand['id']}", disabled=True)
                elif req_status == "ACCEPTED":
                    st.success("🎉 매칭 성공! 보관함에서 선명한 원본 사진을 확인하세요.")
                else:
                    if st.button("💌 대화 신청 (티켓 1장 차감)", key=f"feed_btn_{cand['id']}"):
                        if me.get("ticket_count", 0) <= 0:
                            st.error("티켓이 부족합니다.")
                        else:
                            supabase.table("users").update({"ticket_count": me["ticket_count"] - 1}).eq("id", me["id"]).execute()
                            supabase.table("match_requests").insert({
                                "sender_id": me["id"],
                                "receiver_id": cand["id"],
                                "status": "PENDING",
                                "payment_status": "PAID"
                            }).execute()
                            send_aligo_notice_sms(cand["phone"], f"{me['name'][0]}* 님으로부터 가치관 기반 대화 신청이 도착했습니다.")
                            st.rerun()
                st.write("")

    with tabs_main[1]:
        inbox_1, inbox_2 = st.tabs(["내가 보낸 신청", "나에게 온 신청"])
        
        with inbox_1:
            sent_list = supabase.table("match_requests").select("*").eq("sender_id", me["id"]).execute().data
            if not sent_list:
                st.caption("보낸 신청이 없습니다.")
            else:
                for req in sent_list:
                    rcv = supabase.table("users").select("*").eq("id", req["receiver_id"]).execute().data[0]
                    if req["status"] == "ACCEPTED":
                        st.success(f"🎉 **{rcv['name']}** 님과 매칭되어 블라인드가 해제되었습니다!")
                        r_img = rcv.get("photo_url") or DEFAULT_AVATARS.get(rcv["gender"])
                        st.markdown(f"""
                            <div class="feed-card">
                                <div class="feed-img-box">
                                    <img src="{r_img}" class="feed-img-clear">
                                </div>
                            </div>
                        """, unsafe_allow_html=True)
                        st.write(f"📞 안심 연락처: **{rcv['phone']}** | 💼 직장: **{rcv.get('job')}**")
                        st.markdown(f'<a href="tel:{rcv["phone"]}">📞 바로 전화 걸기</a>', unsafe_allow_html=True)
                    else:
                        st.write(f"• **{rcv['name'][0]}*님**에게 보낸 신청 | 상태: `{req['status']}`")

        with inbox_2:
            rcv_list = supabase.table("match_requests").select("*").eq("receiver_id", me["id"]).execute().data
            if not rcv_list:
                st.caption("도착한 신청이 없습니다.")
            else:
                for req in rcv_list:
                    snd = supabase.table("users").select("*").eq("id", req["sender_id"]).execute().data[0]
                    st.markdown(f"**{snd['name'][0]}*님** ({snd['gender']} · {snd['age']}세 · {snd.get('job')})")
                    if req["status"] == "ACCEPTED":
                        st.success("🤝 대화 수락 완료! 블라인드가 해제되었습니다.")
                        s_img = snd.get("photo_url") or DEFAULT_AVATARS.get(snd["gender"])
                        st.markdown(f"""
                            <div class="feed-card">
                                <div class="feed-img-box">
                                    <img src="{s_img}" class="feed-img-clear">
                                </div>
                            </div>
                        """, unsafe_allow_html=True)
                        st.write(f"📞 안심 연락처: **{snd['phone']}**")
                    elif req["status"] == "PENDING":
                        col_ac, col_re = st.columns(2)
                        with col_ac:
                            if st.button("수락 및 얼굴 공개", key=f"ac_{req['id']}"):
                                supabase.table("match_requests").update({"status": "ACCEPTED"}).eq("id", req["id"]).execute()
                                send_aligo_notice_sms(snd["phone"], f"{me['name'][0]}* 님이 대화를 수락했습니다. 프로필 블라인드가 해제되었습니다.")
                                st.rerun()
                        with col_re:
                            if st.button("거절", key=f"re_{req['id']}"):
                                supabase.table("match_requests").update({"status": "REJECTED"}).eq("id", req["id"]).execute()
                                st.rerun()
                    st.divider()

    with tabs_main[2]:
        my_avatar = me.get("photo_url") or DEFAULT_AVATARS.get(me["gender"])
        st.markdown(f"""
            <div style="text-align:center; padding:10px 0 20px 0;">
                <img src="{my_avatar}" style="width:110px; height:110px; border-radius:50%; object-fit:cover; border:3px solid #3B82F6;">
                <h3 style="margin:10px 0 4px 0; color:#FFFFFF;">{me['name']} ({me['gender']} · {me['age']}세)</h3>
                <div style="font-size:0.85rem; color:#94A3B8;">📍 {me['region']} | 💼 {me.get('job')}</div>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("##### ✏️ 직장 및 소개글 수정")
        edit_job = st.text_input("직장명 및 직무 수정", value=me.get("job", ""), key="edit_job")
        job_errs = audit_text_typos(edit_job)
        if job_errs:
            st.caption(f"💡 권장 수정: {', '.join(job_errs)}")

        edit_intro = st.text_area("한 줄 소개 수정", value=me.get("intro", ""), key="edit_intro")
        intro_errs = audit_text_typos(edit_intro)
        if intro_errs:
            st.caption(f"💡 권장 수정: {', '.join(intro_errs)}")

        if st.button("프로필 정보 업데이트"):
            supabase.table("users").update({
                "job": edit_job.strip(),
                "intro": edit_intro.strip()
            }).eq("id", me["id"]).execute()
            me["job"] = edit_job.strip()
            me["intro"] = edit_intro.strip()
            st.session_state.user_info = me
            st.success("프로필 정보가 수정되었습니다.")
            st.rerun()

        st.markdown("---")
        st.markdown("##### 📸 프로필 사진 등록")
        new_avatar = st.file_uploader("사진 파일 선택 (JPG, PNG)", type=["jpg", "png", "jpeg"], key="up_avatar")
        if new_avatar and st.button("사진 등록 및 저장"):
            f_ext = new_avatar.name.split(".")[-1].lower()
            fname = f"avatar_3040_{me['id']}_{uuid.uuid4().hex[:6]}.{f_ext}"
            supabase.storage.from_("avatars").upload(fname, new_avatar.read(), {"content-type": f"image/{f_ext}"})
            url = f"{SUPABASE_URL}/storage/v1/object/public/avatars/{fname}"
            supabase.table("users").update({"photo_url": url}).eq("id", me["id"]).execute()
            me["photo_url"] = url
            st.session_state.user_info = me
            st.success("사진이 등록되었습니다. 매칭 전에는 블라인드 보호가 자동 적용됩니다.")
            st.rerun()

    st.markdown("---")
    if st.button("로그아웃"):
        st.session_state.user_id = None
        st.session_state.user_info = None
        st.rerun()
