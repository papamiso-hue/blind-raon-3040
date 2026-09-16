import streamlit as st
import streamlit.components.v1 as components
import re
import uuid
import math
import io
import json
import random
import hashlib
import requests
from datetime import datetime, timedelta, timezone
import pandas as pd
from supabase import create_client, Client
from pypdf import PdfReader
from kakao_auth import get_kakao_login_url, get_kakao_user_info

# 1. 스트림릿 기본 페이지 설정
st.set_page_config(
    page_title="블라인드 라온 - 3040 프라이빗 소셜 클럽",
    page_icon="💼",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# 2. PWA 모바일 전용 앱 아이콘 & 브랜드명 주입
manifest_3040 = {
    "name": "블라인드 라온",
    "short_name": "블라인드라온",
    "start_url": "/",
    "display": "standalone",
    "background_color": "#0A0A0C",
    "theme_color": "#1F190B",
    "icons": [
        {
            "src": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=192&auto=format&fit=crop",
            "sizes": "192x192",
            "type": "image/png"
        },
        {
            "src": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=512&auto=format&fit=crop",
            "sizes": "512x512",
            "type": "image/png"
        }
    ]
}
manifest_3040_json = json.dumps(manifest_3040)

st.markdown(f"""
    <head>
        <title>블라인드 라온</title>
        <meta name="apple-mobile-web-app-title" content="블라인드 라온">
        <meta name="application-name" content="블라인드 라온">
        <meta name="apple-mobile-web-app-capable" content="yes">
        <meta name="mobile-web-app-capable" content="yes">
        <meta name="theme-color" content="#1F190B">
        <link rel="apple-touch-icon" href="https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=192&auto=format&fit=crop">
        <link rel="icon" type="image/png" href="https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=192&auto=format&fit=crop">
    </head>
    <script>
        const manifestBlob = new Blob([`{manifest_3040_json}`], {{type: 'application/json'}});
        const manifestURL = URL.createObjectURL(manifestBlob);
        let manifestLink = document.querySelector("link[rel='manifest']");
        if (!manifestLink) {{
            manifestLink = document.createElement('link');
            manifestLink.rel = 'manifest';
            document.head.appendChild(manifestLink);
        }}
        manifestLink.href = manifestURL;
        document.title = "블라인드 라온";
    </script>
""", unsafe_allow_html=True)

# 3. 서비스 기본 상수 및 보안 Secrets 연동
BRAND_NAME_KR = "블라인드 라온"
BRAND_NAME_EN = "BLIND RAON 3040"
SITE_URL = "https://blind-raon-3040-xtwjdberufkkgwje2abbzq.streamlit.app"
OG_IMAGE_URL = "https://images.unsplash.com/photo-1534528741775-53994a69daeb?q=80&w=1200&auto=format&fit=crop"
KAKAO_CHAT_URL = "https://open.kakao.com/o/sRas35Li"

ALIGO_API_KEY = st.secrets["ALIGO_API_KEY"]
ALIGO_USER_ID = st.secrets["ALIGO_USER_ID"]
ALIGO_SENDER = st.secrets["ALIGO_SENDER"]

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

def hash_password(pwd: str) -> str:
    if not pwd:
        return ""
    return hashlib.sha256(pwd.strip().encode("utf-8")).hexdigest()

BANK_INFO = {
    "bank": "카카오뱅크",
    "account": "3333-01-2345678",
    "holder": "라온(소셜클럽)"
}

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
        "text": "1. 결혼관 및 만남의 최종 지향점?",
        "options": ["1~2년 이내 진지한 결혼 희망", "자연스럽게 연애 후 결혼 고려", "비혼주의 또는 자유로운 연애", "취미와 가치관을 공유할 소울메이트"]
    },
    2: {
        "text": "2. 맞벌이 및 가사 분담에 대한 생각?",
        "options": ["맞벌이 필수 + 가사/육아 공평 분담", "한쪽 집중형 외벌이 지향", "상황에 따른 유연한 상호 협력", "외주 서비스 적극 활용 및 효율 중시"]
    },
    3: {
        "text": "3. 자산 형성 및 재테크 관심도?",
        "options": ["부동산/주식 등 적극적 투자 및 자산 증식", "예적금 중심의 안정적 자산 운용", "현재의 삶과 소비를 즐기는 편", "배우자와 함께 새로운 재테크 설계"]
    },
    4: {
        "text": "4. 주말 및 여가시간 소비 패턴?",
        "options": ["맛집 투어, 여행, 카페 등 밖에서의 데이트", "집에서 영화, 요리, 휴식을 즐기는 집돌이/집순이", "테니스, 골프, 헬스 등 운동/자기계발", "각자의 취미를 존중하며 유연한 시간 배분"]
    },
    5: {
        "text": "5. 음주 성향 및 라이프스타일?",
        "options": ["분위기 있는 와인/위스키/가벼운 반주 선호", "비음주 또는 거의 마시지 않음", "친구·지인들과 활발한 술자리 선호", "상대방의 성향에 맞춤 가능"]
    }
}

st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');

    .stApp {
        background: radial-gradient(circle at 50% 0%, #172033 0%, #0A0D14 60%, #050608 100%) !important;
        color: #F8FAFC !important;
        font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }

    .stLinkButton > a {
        background-color: #FEE500 !important;
        color: #191919 !important;
        font-weight: 900 !important;
        font-size: 1.15rem !important;
        border-radius: 14px !important;
        height: 3.6rem !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        border: none !important;
        box-shadow: 0 4px 14px rgba(254, 229, 0, 0.4) !important;
        margin-bottom: 12px !important;
    }

    .block-container { 
        padding-top: 1.2rem !important; 
        padding-bottom: 4rem !important; 
        max-width: 520px !important; 
    }

    .app-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 10px 0 16px 0;
        border-bottom: 1px solid rgba(59, 130, 246, 0.2);
        margin-bottom: 16px;
    }
    .app-brand {
        font-size: 1.3rem;
        font-weight: 900;
        letter-spacing: -0.5px;
        background: linear-gradient(90deg, #60A5FA 0%, #3B82F6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    .hero-box {
        background: linear-gradient(160deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.9) 100%);
        backdrop-filter: blur(16px);
        border: 1px solid rgba(96, 165, 250, 0.35);
        border-radius: 20px;
        padding: 26px 20px;
        text-align: center;
        margin-bottom: 1.2rem;
        box-shadow: 0 16px 36px -10px rgba(37, 99, 235, 0.25);
    }
    .hero-badge {
        display: inline-block;
        background: rgba(59, 130, 246, 0.15);
        border: 1px solid rgba(96, 165, 250, 0.45);
        color: #93C5FD !important;
        font-size: 0.76rem;
        font-weight: 800;
        letter-spacing: 1.5px;
        padding: 5px 16px;
        border-radius: 9999px;
        margin-bottom: 10px;
    }
    .hero-title {
        font-size: 2.05rem;
        font-weight: 900;
        line-height: 1.25;
        letter-spacing: -0.8px;
        color: #FFFFFF !important;
        margin-bottom: 8px;
    }
    .hero-subtitle {
        font-size: 0.95rem;
        font-weight: 600;
        color: #E2E8F0 !important;
        line-height: 1.6;
    }

    .promise-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 8px;
        margin-bottom: 1.2rem;
    }
    .promise-card {
        background: rgba(15, 23, 42, 0.7);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 14px;
        padding: 14px 6px;
        text-align: center;
    }
    .promise-icon { font-size: 1.4rem; margin-bottom: 4px; }
    .promise-title { font-size: 0.85rem; font-weight: 800; color: #F8FAFC !important; }
    .promise-desc { font-size: 0.72rem; color: #94A3B8 !important; margin-top: 2px; }

    .senior-card {
        position: relative;
        border-radius: 22px;
        overflow: hidden;
        margin-bottom: 1.6rem;
        background: #0F172A;
        border: 1px solid rgba(59, 130, 246, 0.3);
        box-shadow: 0 20px 30px -10px rgba(0, 0, 0, 0.7);
    }
    .senior-img-box {
        position: relative;
        width: 100%;
        height: 390px;
        overflow: hidden;
    }
    .senior-img-blur {
        width: 100%;
        height: 100%;
        object-fit: cover;
        filter: blur(10px) brightness(0.85);
        transform: scale(1.08);
    }
    .senior-img-clear {
        width: 100%;
        height: 100%;
        object-fit: cover;
    }
    .senior-overlay {
        position: absolute;
        bottom: 0;
        left: 0;
        right: 0;
        height: 60%;
        background: linear-gradient(to top, #0F172A 15%, transparent 100%);
        pointer-events: none;
    }
    .senior-blind-tag {
        position: absolute;
        top: 16px;
        left: 16px;
        background: rgba(15, 23, 42, 0.85);
        backdrop-filter: blur(8px);
        border: 1px solid rgba(96, 165, 250, 0.4);
        padding: 6px 14px;
        border-radius: 20px;
        font-size: 0.76rem;
        font-weight: 800;
        color: #93C5FD;
    }
    .senior-match-badge {
        position: absolute;
        top: 16px;
        right: 16px;
        background: linear-gradient(135deg, #3B82F6 0%, #1D4ED8 100%);
        padding: 7px 16px;
        border-radius: 20px;
        font-size: 0.88rem;
        font-weight: 900;
        color: #FFFFFF;
        box-shadow: 0 4px 14px rgba(37, 99, 235, 0.4);
    }
    .senior-content {
        padding: 16px 20px 22px 20px;
        margin-top: -24px;
        position: relative;
    }
    .senior-name-row {
        display: flex;
        align-items: baseline;
        gap: 8px;
        margin-bottom: 8px;
    }
    .senior-name {
        font-size: 1.55rem;
        font-weight: 900;
        color: #FFFFFF;
        letter-spacing: -0.5px;
    }
    .senior-age {
        font-size: 1.15rem;
        font-weight: 700;
        color: #CBD5E1;
    }
    .badge-pill-gold {
        background: rgba(59, 130, 246, 0.15);
        color: #93C5FD;
        border: 1px solid rgba(59, 130, 246, 0.35);
        padding: 5px 12px;
        border-radius: 6px;
        font-size: 0.80rem;
        font-weight: 800;
    }
    .badge-pill-credit {
        background: rgba(16, 185, 129, 0.15);
        color: #6EE7B7;
        border: 1px solid rgba(16, 185, 129, 0.3);
        padding: 5px 12px;
        border-radius: 6px;
        font-size: 0.80rem;
        font-weight: 800;
    }
    .senior-intro {
        margin-top: 12px;
        font-size: 0.94rem;
        color: #E2E8F0;
        line-height: 1.6;
        word-break: keep-all;
    }

    .shop-card {
        background: #0F172A;
        border: 1.5px solid rgba(59, 130, 246, 0.25);
        border-radius: 16px;
        padding: 18px 20px;
        margin-bottom: 14px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .shop-card.featured {
        border-color: #3B82F6;
        background: linear-gradient(145deg, #1E293B 0%, #0F172A 100%);
        box-shadow: 0 4px 20px rgba(37, 99, 235, 0.25);
    }
    .shop-title { font-size: 1.1rem; font-weight: 900; color: #FFFFFF; margin-bottom: 4px; }
    .shop-desc { font-size: 0.82rem; color: #94A3B8; }
    .shop-price { font-size: 1.3rem; font-weight: 900; color: #93C5FD; text-align: right; }
    .shop-badge { display: inline-block; background: #2563EB; color: #FFFFFF; font-size: 0.68rem; font-weight: 800; padding: 2px 8px; border-radius: 4px; margin-bottom: 4px; }
    .bank-box { background: rgba(30, 41, 59, 0.6); border: 1px dashed rgba(96, 165, 250, 0.4); border-radius: 14px; padding: 18px; text-align: center; margin: 16px 0; }

    div[data-baseweb="tab-list"] {
        background-color: rgba(15, 23, 42, 0.85) !important;
        padding: 5px;
        border-radius: 14px;
        border: 1px solid rgba(59, 130, 246, 0.25) !important;
        margin-bottom: 1.4rem;
        gap: 4px;
    }
    div[data-baseweb="tab"] {
        flex: 1;
        height: 46px;
        border-radius: 10px !important;
        background-color: transparent !important;
        color: #94A3B8 !important;
        font-weight: 800 !important;
        font-size: 0.92rem !important;
        border: none !important;
    }
    div[data-baseweb="tab"][aria-selected="true"] {
        background: linear-gradient(135deg, #3B82F6 0%, #1D4ED8 100%) !important;
        color: #FFFFFF !important;
        box-shadow: 0 4px 14px rgba(37, 99, 235, 0.35);
    }
    div[data-baseweb="tab-border"] { display: none !important; }

    div[data-baseweb="input"] {
        background-color: rgba(15, 23, 42, 0.95) !important;
        border: 1.5px solid #334155 !important;
        border-radius: 12px !important;
    }
    div[data-baseweb="input"]:focus-within {
        border-color: #3B82F6 !important;
        box-shadow: 0 0 0 1px #3B82F6 !important;
    }
    div[data-baseweb="input"] input { color: #FFFFFF !important; font-size: 0.95rem; }

    .stButton>button { 
        width: 100%; 
        border-radius: 12px; 
        font-weight: 800; 
        height: 3.5rem; 
        font-size: 1.1rem; 
        letter-spacing: -0.3px; 
        border: none !important; 
        background: linear-gradient(135deg, #3B82F6 0%, #2563EB 100%) !important; 
        color: #FFFFFF !important; 
        box-shadow: 0 6px 18px rgba(37, 99, 235, 0.35); 
        transition: transform 0.1s ease; 
    }
    .stButton>button:active { transform: scale(0.98); }

    #MainMenu, footer, header { visibility: hidden !important; }
    </style>
""", unsafe_allow_html=True)

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
    "남": "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?q=80&w=600&auto=format&fit=crop",
    "여": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?q=80&w=600&auto=format&fit=crop"
}

# 세션 상태 초기화
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "user_info" not in st.session_state:
    st.session_state.user_info = None
if "kakao_user" not in st.session_state:
    st.session_state.kakao_user = None

if "sms_auth_code" not in st.session_state:
    st.session_state.sms_auth_code = None
if "sms_verified_phone" not in st.session_state:
    st.session_state.sms_verified_phone = None
if "sms_is_verified" not in st.session_state:
    st.session_state.sms_is_verified = False
if "sms_send_count_3040" not in st.session_state:
    st.session_state.sms_send_count_3040 = 0
if "sms_last_sent_at_3040" not in st.session_state:
    st.session_state.sms_last_sent_at_3040 = None

if "reset_sms_code_3040" not in st.session_state:
    st.session_state.reset_sms_code_3040 = None
if "reset_verified_phone_3040" not in st.session_state:
    st.session_state.reset_verified_phone_3040 = None
if "reset_target_uid_3040" not in st.session_state:
    st.session_state.reset_target_uid_3040 = None

# 🌟 카카오 인증 콜백 처리 (1회용 코드 즉시 제거로 KOE320 방지)
params = st.query_params
if "code" in params and not st.session_state.user_id:
    kakao_code = params.get("code")
    k_user = get_kakao_user_info(kakao_code)
    
    st.query_params.clear()
    
    if k_user:
        st.session_state.kakao_user = k_user
        kakao_id_str = str(k_user["id"])
        
        # 기존 가입 여부 확인
        res = supabase.table("users").select("*").eq("kakao_id", kakao_id_str).execute()
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
            # 신규 회원이면 등록 폼으로 화면 갱신
            st.rerun()

# --- 1. 로그인 / 신규 가입 화면 ---
if not st.session_state.user_id:
    st.markdown(f"""
        <div class="hero-box">
            <div class="hero-badge">💼 3040 PRIVATE SOCIAL CLUB</div>
            <div class="hero-title">🌟 {BRAND_NAME_KR}</div>
            <div class="hero-subtitle">진중한 가치관과 커리어를 갖춘 3040 싱글을 위한<br>
            <strong style="color:#93C5FD;">신용·직장 검증 기반 프라이빗 매칭</strong></div>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("""
        <div class="promise-grid">
            <div class="promise-card">
                <div class="promise-icon">🛡️</div>
                <div class="promise-title">신용·소득 검증</div>
                <div class="promise-desc">철저한 증빙 서류 심사</div>
            </div>
            <div class="promise-card">
                <div class="promise-icon">🚫</div>
                <div class="promise-title">지인 번호 완벽차단</div>
                <div class="promise-desc">직장/지인 안심 미노출</div>
            </div>
            <div class="promise-card">
                <div class="promise-icon">🔒</div>
                <div class="promise-title">블라인드 프로필</div>
                <div class="promise-desc">상호 수락 시 프로필 공개</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # 카카오 인증 신규 회원인 경우 안내 배너 및 탭 순서 자동 전환
    if st.session_state.kakao_user:
        k_nick = st.session_state.kakao_user.get("nickname", "회원")
        st.success(f"🎉 **{k_nick}**님, 카카오 본인 확인이 완료되었습니다!\n\n블라인드 라온 회원 심사를 위해 아래에서 기본 정보와 서류를 제출해 주세요.")
        tab_join, tab_login = st.tabs(["📝 신규 프로필 등록 (카카오 연동)", "🔑 기존 정회원 로그인"])
    else:
        kakao_login_url = get_kakao_login_url()
        st.link_button(
            "💬 카카오 계정으로 간편 시작",
            url=kakao_login_url,
            use_container_width=True
        )
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
                hashed_input = hash_password(login_pwd)
                res = supabase.table("users").select("*").eq("name", login_name.strip()).eq("phone", clean_p).execute()

                if res.data:
                    u = res.data[0]
                    stored_pwd = u.get("password", "")
                    if stored_pwd == hashed_input or stored_pwd == login_pwd.strip():
                        if u.get("is_suspended"):
                            st.error("🚫 제재 조치된 계정입니다. 고객센터로 문의해 주세요.")
                        else:
                            now_utc = datetime.now(timezone.utc).isoformat()
                            update_data = {"last_login_at": now_utc}
                            if stored_pwd != hashed_input:
                                update_data["password"] = hashed_input
                                
                            supabase.table("users").update(update_data).eq("id", u["id"]).execute()
                            u["last_login_at"] = now_utc
                            st.session_state.user_id = u["id"]
                            st.session_state.user_info = u
                            st.rerun()
                    else:
                        st.error("비밀번호가 일치하지 않습니다.")
                else:
                    st.error("일치하는 회원 정보를 찾을 수 없습니다.")

        with st.expander("🔑 비밀번호를 잊으셨나요? (간편 재설정)"):
            st.caption("가입 시 등록한 성명과 휴대폰 번호로 인증 후 새 비밀번호를 설정할 수 있습니다.")
            f_name = st.text_input("가입 성명", key="f_name_3040")
            col_fp1, col_fp2 = st.columns([2.5, 1.2])
            with col_fp1:
                f_phone = st.text_input("가입 휴대폰 번호", placeholder="01012345678", key="f_phone_3040")
            with col_fp2:
                st.write("")
                btn_find_sms = st.button("인증문자 발송", key="btn_find_sms_3040")

            clean_fp = re.sub(r'[^0-9]', '', f_phone.strip())
            if btn_find_sms:
                if not f_name.strip() or len(clean_fp) < 10:
                    st.error("성명과 휴대폰 번호를 정확히 입력해 주세요.")
                else:
                    chk = supabase.table("users").select("id").eq("name", f_name.strip()).eq("phone", clean_fp).execute().data
                    if not chk:
                        st.error("등록된 회원 정보가 존재하지 않습니다.")
                    else:
                        code = str(random.randint(100000, 999999))
                        st.session_state.reset_sms_code_3040 = code
                        st.session_state.reset_verified_phone_3040 = clean_fp
                        st.session_state.reset_target_uid_3040 = chk[0]["id"]
                        send_aligo_sms(clean_fp, code)
                        st.success("인증번호가 발송되었습니다. 아래에 입력해 주세요.")

            if st.session_state.reset_sms_code_3040:
                in_fcode = st.text_input("문자 인증번호 6자리", key="in_find_code_3040")
                new_reset_pwd = st.text_input("새로운 간편 비밀번호 (4~6자리)", type="password", key="new_reset_pwd_3040")
                
                if st.button("새 비밀번호로 변경 및 저장", key="btn_do_reset_3040"):
                    if in_fcode.strip() != st.session_state.reset_sms_code_3040:
                        st.error("인증번호가 일치하지 않습니다.")
                    elif len(new_reset_pwd.strip()) < 4:
                        st.error("비밀번호는 최소 4자리 이상이어야 합니다.")
                    else:
                        supabase.table("users").update({
                            "password": hash_password(new_reset_pwd)
                        }).eq("id", st.session_state.reset_target_uid_3040).execute()
                        st.session_state.reset_sms_code_3040 = None
                        st.session_state.reset_target_uid_3040 = None
                        st.success("🎉 비밀번호가 안전하게 재설정되었습니다! 새 비밀번호로 로그인해 주세요.")

    with tab_join:
        st.markdown("##### 👤 기본 인적사항 (만 28~49세 대상)")
        
        default_name = ""
        if st.session_state.kakao_user:
            default_name = st.session_state.kakao_user.get("nickname", "")
            st.caption(f"💬 카카오 프로필 연동 중: **{default_name}**")

        j_name = st.text_input("실명", value=default_name, key="j_name")
        
        col_p1, col_p2 = st.columns([2.5, 1.2])
        with col_p1:
            j_phone = st.text_input("휴대폰 번호 (- 제외)", placeholder="01012345678", key="j_phone")
        with col_p2:
            st.write("")
            btn_sms = st.button("인증번호 발송", key="btn_sms")

        clean_jp = re.sub(r'[^0-9]', '', j_phone.strip())
        if btn_sms:
            now_ts = datetime.now().timestamp()
            if len(clean_jp) < 10:
                st.error("올바른 휴대폰 번호를 입력해 주세요.")
            elif st.session_state.sms_send_count_3040 >= 3:
                st.error("🚨 인증번호 발송 허용 횟수(3회)를 초과했습니다. 잠시 후 다시 시도해 주세요.")
            elif st.session_state.sms_last_sent_at_3040 and (now_ts - st.session_state.sms_last_sent_at_3040 < 60):
                remaining = int(60 - (now_ts - st.session_state.sms_last_sent_at_3040))
                st.warning(f"⏳ {remaining}초 후에 다시 요청할 수 있습니다. 문자가 도착할 때까지 기다려 주세요.")
            else:
                dup = supabase.table("users").select("id").eq("phone", clean_jp).execute().data
                if dup:
                    st.error("이미 등록된 휴대폰 번호입니다.")
                else:
                    code = str(random.randint(100000, 999999))
                    st.session_state.sms_auth_code = code
                    st.session_state.sms_verified_phone = clean_jp
                    st.session_state.sms_is_verified = False
                    st.session_state.sms_last_sent_at_3040 = now_ts
                    st.session_state.sms_send_count_3040 += 1
                    send_aligo_sms(clean_jp, code)
                    st.success(f"문자로 발송된 6자리 인증번호를 입력해 주세요. (발송 횟수: {st.session_state.sms_send_count_3040}/3회)")

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
        j_age = st.number_input("나이 (만 나이)", 28, 49, 36, key="j_age")

        r_col1, r_col2 = st.columns(2)
        with r_col1:
            j_sido = st.selectbox("활동 광역시·도", list(KOREA_REGIONS.keys()), index=0, key="j_sido")
        with r_col2:
            j_sigungu = st.selectbox("시·군·구", KOREA_REGIONS[j_sido], index=0, key="j_sigungu")
        j_region = f"{j_sido} {j_sigungu}"

        st.markdown("##### 💼 커리어 및 라이프스타일")
        j_job = st.text_input("직업 또는 직장/전문분야", placeholder="예: IT 대기업 개발자 / 금융 공기업 / 스타트업 대표 / 전문직", key="j_job")
        job_typos = audit_text_typos(j_job)
        if job_typos:
            st.caption(f"💡 표현 교정 안내: {', '.join(job_typos)}")

        j_hobbies = st.text_input("취미 및 여가 생활", placeholder="예: 러닝, 골프, 와인, 전시회, 맛집 투어", key="j_hobbies")
        hobby_typos = audit_text_typos(j_hobbies)
        if hobby_typos:
            st.caption(f"💡 표현 교정 안내: {', '.join(hobby_typos)}")

        j_intro = st.text_area("인연에게 전하고 싶은 말씀", value="서로의 커리어와 가치관을 존중하며 긍정적인 에너지를 나눌 수 있는 분을 찾습니다.", key="j_intro")
        intro_typos = audit_text_typos(j_intro)
        if intro_typos:
            st.caption(f"💡 소개글 맞춤법 안내: {', '.join(intro_typos)}")

        st.markdown("##### 🛡️ 신용 검증 기준")
        req_score = 800 if j_gender == "남" else 650
        st.caption(f"ℹ️ {j_gender}성 입회 기준: 공인 신용점수 {req_score}점 이상")
        j_credit = st.number_input(f"공인 신용점수 ({req_score}점 이상 필수)", 0, 1000, 830 if j_gender == "남" else 770, key="j_credit")
        j_doc = st.file_uploader("신원·소득 증빙 서류 첨부 (재직증명서, 신용리포트, 소득금액증명 중 택1)", type=["jpg", "png", "pdf"], key="j_doc")

        st.markdown("##### 🎯 3040 필수 가치관 5대 문답")
        a1 = st.radio(CORE_QUESTIONS_3040[1]["text"], CORE_QUESTIONS_3040[1]["options"], key="jq_1")
        a2 = st.radio(CORE_QUESTIONS_3040[2]["text"], CORE_QUESTIONS_3040[2]["options"], key="jq_2")
        a3 = st.radio(CORE_QUESTIONS_3040[3]["text"], CORE_QUESTIONS_3040[3]["options"], key="jq_3")
        a4 = st.radio(CORE_QUESTIONS_3040[4]["text"], CORE_QUESTIONS_3040[4]["options"], key="jq_4")
        a5 = st.radio(CORE_QUESTIONS_3040[5]["text"], CORE_QUESTIONS_3040[5]["options"], key="jq_5")

        agree_terms = st.checkbox("[필수] 블라인드 라온 이용약관 및 증빙서류 확인 즉시 파기에 동의합니다.", key="agree_terms")

        if st.button("신원 검증 신청 및 가입 완료", key="btn_submit_join"):
            if not agree_terms:
                st.error("필수 이용약관에 동의해 주세요.")
            elif not j_name.strip():
                st.error("성명을 입력해 주세요.")
            elif not st.session_state.sms_is_verified or st.session_state.sms_verified_phone != clean_jp:
                st.error("휴대폰 SMS 인증을 완료해 주세요.")
            elif len(j_pwd.strip()) < 4:
                st.error("비밀번호는 최소 4자리 이상이어야 합니다.")
            elif j_credit < req_score:
                st.error(f"입회 기준 미달: 블라인드 라온은 {j_gender}성 기준 {req_score}점 이상만 승인됩니다.")
            elif not j_doc:
                st.error("신원 및 신용 증빙 서류를 첨부해 주세요.")
            else:
                doc_ext = j_doc.name.split(".")[-1].lower()
                doc_name = f"verify_{clean_jp}_{uuid.uuid4().hex[:6]}.{doc_ext}"
                try:
                    supabase.storage.from_("credit-docs").upload(
                        doc_name, 
                        j_doc.read(), 
                        {"content-type": "application/pdf" if doc_ext == "pdf" else f"image/{doc_ext}"}
                    )
                    now_utc = datetime.now(timezone.utc).isoformat()

                    kakao_id_val = str(st.session_state.kakao_user["id"]) if st.session_state.kakao_user else None
                    kakao_photo_val = st.session_state.kakao_user.get("profile_image") if st.session_state.kakao_user else None

                    user_data = {
                        "name": j_name.strip(),
                        "phone": clean_jp,
                        "password": hash_password(j_pwd),
                        "gender": j_gender,
                        "age": int(j_age),
                        "region": j_region,
                        "credit_score": int(j_credit),
                        "credit_doc_url": doc_name,
                        "credit_status": "PENDING",
                        "is_verified": False,
                        "ticket_count": 3,
                        "is_vip": False,
                        "blocked_phones": [],
                        "last_login_at": now_utc,
                        "job": j_job.strip() if j_job else "전문직/회사원",
                        "hobbies": j_hobbies.strip() if j_hobbies else "여가 생활",
                        "intro": j_intro.strip(),
                        "is_admin": False,
                        "is_suspended": False
                    }
                    if kakao_id_val:
                        user_data["kakao_id"] = kakao_id_val
                    if kakao_photo_val:
                        user_data["photo_url"] = kakao_photo_val

                    new_u = supabase.table("users").insert(user_data).execute().data[0]

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
    my_tickets = me.get('ticket_count', 0)

    h_col1, h_col2 = st.columns([2.5, 1.5])
    with h_col1:
        st.markdown(f'<div class="app-brand">🌟 {BRAND_NAME_KR}</div>', unsafe_allow_html=True)
    with h_col2:
        st.markdown(f"""
            <div style="text-align:right; margin-top:4px;">
                <span style="font-size:0.92rem; font-weight:900; color:#60A5FA;">🎟️ {my_tickets}장</span>
            </div>
        """, unsafe_allow_html=True)

    with st.expander("🚫 아는 사람 / 지인 번호 차단 관리"):
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

    tabs_main = st.tabs(["✨ 추천 피드", "📬 신청 보관함", "💳 티켓 충전", "👤 내 프로필"])

    my_ans_data = supabase.table("user_answers").select("question_num, answer_value").eq("user_id", me["id"]).execute().data
    my_answers = {item["question_num"]: item["answer_value"] for item in my_ans_data}

    # --- TAB 1: 추천 피드 ---
    with tabs_main[0]:
        target_gender = "여" if me["gender"] == "남" else "남"
        raw_candidates = supabase.table("users").select("*")\
            .eq("gender", target_gender)\
            .gte("age", 28)\
            .lte("age", 49)\
            .eq("is_suspended", False)\
            .execute().data

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
                intro_txt = cand.get("intro") or "서로를 존중하고 아껴줄 소중한 인연을 기다립니다."

                st.markdown(f"""
                    <div class="senior-card">
                        <div class="senior-img-box">
                            <img src="{c_img}" class="senior-img-blur">
                            <div class="senior-overlay"></div>
                            <div class="senior-blind-tag">🔒 블라인드 보호</div>
                            <div class="senior-match-badge">{score}% 일치</div>
                        </div>
                        <div class="senior-content">
                            <div class="senior-name-row">
                                <span class="senior-name">{cand['name'][0]}*님</span>
                                <span class="senior-age">{cand['age']}세 · {cand['region'].split()[0]}</span>
                            </div>
                            <div style="display:flex; gap:6px; flex-wrap:wrap; margin-bottom:10px;">
                                <span class="badge-pill-gold">💼 {cand.get('job', '직장 인증')}</span>
                                <span class="badge-pill-credit">🛡️ 신용 {cand['credit_score']}점</span>
                            </div>
                            <div class="senior-intro">"{intro_txt}"</div>
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
                    st.button(f"⏳ 수락 대기중 ({cand['name'][0]}*님)", key=f"feed_btn_{cand['id']}", disabled=True)
                elif req_status == "ACCEPTED":
                    st.success("🎉 매칭 성공! 보관함에서 선명한 사진과 연락처를 확인하세요.")
                else:
                    if st.button(f"💌 대화 신청하기 (티켓 1장)", key=f"feed_btn_{cand['id']}"):
                        if my_tickets <= 0:
                            st.error("🚨 보유 티켓이 부족합니다. 상단의 [💳 티켓 충전] 탭에서 충전 후 이용해 주세요.")
                        else:
                            supabase.table("users").update({"ticket_count": my_tickets - 1}).eq("id", me["id"]).execute()
                            me["ticket_count"] = my_tickets - 1
                            st.session_state.user_info = me
                            supabase.table("match_requests").insert({
                                "sender_id": me["id"],
                                "receiver_id": cand["id"],
                                "status": "PENDING",
                                "payment_status": "PAID"
                            }).execute()
                            send_aligo_notice_sms(cand["phone"], f"{me['name'][0]}* 님으로부터 가치관 기반 대화 신청이 도착했습니다.")
                            st.rerun()

                st.caption("ℹ️ 대화 신청 시 티켓 1장이 사용되며, 상대방 거절/72시간 미응답 시 티켓은 자동 반환됩니다. (미사용 티켓 7일 이내 100% 환불)")
                st.write("")

    # --- TAB 2: 신청 보관함 ---
    with tabs_main[1]:
        pending_sent = supabase.table("match_requests")\
            .select("*")\
            .eq("sender_id", me["id"])\
            .eq("status", "PENDING")\
            .execute().data
            
        now_dt = datetime.now(timezone.utc)
        restored_count = 0
        
        for req in pending_sent:
            created_str = req.get("created_at")
            if created_str:
                try:
                    clean_ts = created_str.split(".")[0].replace("Z", "")
                    created_dt = datetime.fromisoformat(clean_ts).replace(tzinfo=timezone.utc)
                    if now_dt - created_dt > timedelta(hours=72):
                        supabase.table("match_requests").update({"status": "EXPIRED"}).eq("id", req["id"]).execute()
                        restored_count += 1
                except Exception:
                    continue

        if restored_count > 0:
            new_ticket_val = me.get("ticket_count", 0) + restored_count
            supabase.table("users").update({"ticket_count": new_ticket_val}).eq("id", me["id"]).execute()
            me["ticket_count"] = new_ticket_val
            st.session_state.user_info = me
            st.info(f"💡 72시간 동안 응답이 없는 신청 {restored_count}건이 자동 취소되어 티켓 {restored_count}장이 정상 반환되었습니다.")

        inbox_1, inbox_2 = st.tabs(["내가 보낸 신청", "나에게 온 신청"])
        
        with inbox_1:
            sent_list = supabase.table("match_requests").select("*").eq("sender_id", me["id"]).execute().data
            if not sent_list:
                st.caption("보낸 신청이 없습니다.")
            else:
                for req in sent_list:
                    rcv = supabase.table("users").select("*").eq("id", req["receiver_id"]).execute().data[0]
                    if req["status"] == "ACCEPTED":
                        st.success(f"🎉 **{rcv['name']}** 님과 매칭이 성사되었습니다!")
                        r_img = rcv.get("photo_url") or DEFAULT_AVATARS.get(rcv["gender"])
                        st.markdown(f"""
                            <div class="senior-card">
                                <div class="senior-img-box">
                                    <img src="{r_img}" class="senior-img-clear">
                                </div>
                            </div>
                        """, unsafe_allow_html=True)
                        st.write(f"📞 안심 연락처: **{rcv['phone']}** | 💼 직장/경력: **{rcv.get('job')}**")
                        st.markdown(f'<a href="tel:{rcv["phone"]}">📞 바로 전화 걸기</a>', unsafe_allow_html=True)
                    elif req["status"] == "REJECTED":
                        st.write(f"• **{rcv['name'][0]}*님**이 신청을 정중히 사양하여 **티켓 1장이 즉시 반환**되었습니다.")
                    elif req["status"] == "EXPIRED":
                        st.write(f"• **{rcv['name'][0]}*님**의 72시간 미응답으로 자동 취소되어 **티켓 1장이 반환**되었습니다.")
                    else:
                        st.write(f"• **{rcv['name'][0]}*님**에게 보낸 신청 | 상태: `수락 대기중`")

        with inbox_2:
            rcv_list = supabase.table("match_requests").select("*").eq("receiver_id", me["id"]).execute().data
            if not rcv_list:
                st.caption("도착한 신청이 없습니다.")
            else:
                for req in rcv_list:
                    snd = supabase.table("users").select("*").eq("id", req["sender_id"]).execute().data[0]
                    st.markdown(f"**{snd['name'][0]}*님** ({snd['gender']} · {snd['age']}세 · {snd.get('job')})")
                    if req["status"] == "ACCEPTED":
                        st.success("🤝 대화 수락 완료! 연락처가 공개되었습니다.")
                        s_img = snd.get("photo_url") or DEFAULT_AVATARS.get(snd["gender"])
                        st.markdown(f"""
                            <div class="senior-card">
                                <div class="senior-img-box">
                                    <img src="{s_img}" class="senior-img-clear">
                                </div>
                            </div>
                        """, unsafe_allow_html=True)
                        st.write(f"📞 안심 연락처: **{snd['phone']}**")
                    elif req["status"] == "PENDING":
                        col_ac, col_re = st.columns(2)
                        with col_ac:
                            if st.button("수락 및 연락처 공유", key=f"ac_{req['id']}"):
                                supabase.table("match_requests").update({"status": "ACCEPTED"}).eq("id", req["id"]).execute()
                                send_aligo_notice_sms(snd["phone"], f"{me['name'][0]}* 님이 대화를 수락했습니다. 안심 연락처를 확인하세요.")
                                st.rerun()
                        with col_re:
                            if st.button("거절", key=f"re_{req['id']}"):
                                supabase.table("match_requests").update({"status": "REJECTED"}).eq("id", req["id"]).execute()
                                cur_sender_ticket = snd.get("ticket_count", 0)
                                supabase.table("users").update({"ticket_count": cur_sender_ticket + 1}).eq("id", snd["id"]).execute()
                                send_aligo_notice_sms(snd["phone"], "보내신 대화 신청이 정중히 사양되었으며, 사용하신 티켓 1장이 정상 복구되었습니다.")
                                st.success("거절 의사를 전달하였으며, 신청자에게 티켓이 안전하게 반환되었습니다.")
                                st.rerun()
                    st.divider()

    # --- TAB 3: 티켓 충전소 ---
    with tabs_main[2]:
        st.markdown(f"""
            <div style="text-align:center; padding: 10px 0 16px 0;">
                <h3 style="color:#FFFFFF; margin-bottom:4px;">💼 프라이빗 멤버십 충전</h3>
                <div style="font-size:0.9rem; color:#94A3B8;">현재 회원님의 보유 티켓: <strong style="color:#93C5FD; font-size:1.05rem;">{my_tickets}장</strong></div>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("""
            <div class="shop-card">
                <div>
                    <div class="shop-title">🎟️ 1회 대화 신청권</div>
                    <div class="shop-desc">원하는 회원 1명에게 매칭 신청</div>
                </div>
                <div class="shop-price">30,000원</div>
            </div>
            
            <div class="shop-card featured">
                <div>
                    <span class="shop-badge">⭐ 가장 많은 선택</span>
                    <div class="shop-title">🌟 3회 실속 패키지</div>
                    <div class="shop-desc">3회 신청 (회당 약 26,000원 / 11% 할인)</div>
                </div>
                <div class="shop-price">80,000원</div>
            </div>

            <div class="shop-card">
                <div>
                    <span class="shop-badge" style="background:#1E40AF;">👑 VIP 추천</span>
                    <div class="shop-title">👑 5회 VIP 전담 패키지</div>
                    <div class="shop-desc">5회 신청 + 매칭 매니저 우선 주선</div>
                </div>
                <div class="shop-price">130,000원</div>
            </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
            <div class="bank-box">
                <div style="font-size:0.85rem; color:#E2E8F0; font-weight:700;">🏦 무통장 안심 입금 계좌</div>
                <div style="font-size:1.15rem; font-weight:900; color:#93C5FD; margin:6px 0;">{BANK_INFO['bank']} {BANK_INFO['account']}</div>
                <div style="font-size:0.82rem; color:#94A3B8;">예금주: {BANK_INFO['holder']} (입금자명: <strong>{me['name']}</strong>)</div>
            </div>
        """, unsafe_allow_html=True)

        st.info("💡 입금 후 아래 **[카카오톡 1:1 입금 확인]** 버튼을 누르시고 성함을 남겨주시면, 담당 매니저가 즉시 확인 후 티켓을 충전해 드립니다.")
        
        st.markdown(f"""
            <a href="{KAKAO_CHAT_URL}" target="_blank" style="text-decoration:none;">
                <div style="background:#FEE500; color:#191919; text-align:center; padding:15px; border-radius:12px; font-weight:900; font-size:1.05rem; box-shadow:0 4px 14px rgba(254, 229, 0, 0.3); margin-bottom:18px;">
                    💬 카카오톡 1:1 입금 확인 및 환불 문의
                </div>
            </a>
        """, unsafe_allow_html=True)

        with st.expander("⚖️ 전자상거래법에 따른 티켓 환불 및 안심 이용 규정 안내"):
            st.markdown("""
            **1. 미사용 티켓 100% 청약철회 (환불)**
            * 구매 후 **7일 이내에 전혀 사용하지 않은 티켓**은 전자상거래법 제17조에 따라 별도의 수수료 없이 **결제 금액 전액(100%) 환불**됩니다.

            **2. 사용한 티켓의 환불 제한**
            * 상대방 프로필에 대화 신청을 전송하여 **이미 사용(차감)된 티켓은 디지털 용역 제공이 완료된 것으로 간주되어 환불이 불가**합니다.
            * 패키지 상품 중 일부만 사용한 경우, 미사용 잔여 티켓은 전체 결제액에서 사용한 횟수만큼 단품 정가(회당 30,000원)를 차감한 후 잔여액을 반환합니다.

            **3. 대화 신청 거절 및 72시간 미응답 시 티켓 보호**
            * 신청을 받은 상대방이 정중히 '거절'하거나 72시간 이내 응답이 없을 경우, **차감된 티켓은 보유 수량으로 100% 자동 반환**됩니다.
            """)

    # --- TAB 4: 프로필 관리 ---
    with tabs_main[3]:
        my_avatar = me.get("photo_url") or DEFAULT_AVATARS.get(me["gender"])
        st.markdown(f"""
            <div style="text-align:center; padding:10px 0 20px 0;">
                <img src="{my_avatar}" style="width:110px; height:110px; border-radius:50%; object-fit:cover; border:3px solid #3B82F6;">
                <h3 style="margin:10px 0 4px 0; color:#FFFFFF;">{me['name']} ({me['gender']} · {me['age']}세)</h3>
                <div style="font-size:0.9rem; color:#CBD5E1;">📍 {me['region']} | 💼 {me.get('job')}</div>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("##### ✏️ 자기소개 및 직장·취미 정보 수정")
        edit_job = st.text_input("직업 또는 직장/전문분야 수정", value=me.get("job", ""), key="edit_job")
        job_errs = audit_text_typos(edit_job)
        if job_errs:
            st.caption(f"💡 권장 수정: {', '.join(job_errs)}")

        edit_hobbies = st.text_input("취미 및 여가 생활 수정", value=me.get("hobbies", ""), key="edit_hobbies")
        hobby_errs = audit_text_typos(edit_hobbies)
        if hobby_errs:
            st.caption(f"💡 권장 수정: {', '.join(hobby_errs)}")

        edit_intro = st.text_area("한 줄 소개 수정", value=me.get("intro", ""), key="edit_intro")
        intro_errs = audit_text_typos(edit_intro)
        if intro_errs:
            st.caption(f"💡 권장 수정: {', '.join(intro_errs)}")

        if st.button("프로필 정보 업데이트"):
            supabase.table("users").update({
                "job": edit_job.strip(),
                "hobbies": edit_hobbies.strip(),
                "intro": edit_intro.strip()
            }).eq("id", me["id"]).execute()
            me["job"] = edit_job.strip()
            me["hobbies"] = edit_hobbies.strip()
            me["intro"] = edit_intro.strip()
            st.session_state.user_info = me
            st.success("프로필 정보가 성공적으로 수정되었습니다.")
            st.rerun()

        st.markdown("---")
        st.markdown("##### 📸 프로필 사진 등록")
        st.caption("등록된 사진은 매칭 전까지 블라인드 블러 처리되어 안전하게 보호되며, 상호 수락 시에만 상대방에게 선명하게 공개됩니다.")
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

    # 👑 [관리자 전용] 3040 서류 심사 및 즉시 파기 센터
    if me.get("is_admin"):
        st.markdown("---")
        with st.expander("👑 [관리자 전용] 3040 서류 심사 및 즉시 파기 센터"):
            pending_users = supabase.table("users").select("*").eq("credit_status", "PENDING").execute().data
            if not pending_users:
                st.success("현재 심사 대기 중인 회원이 없습니다.")
            else:
                st.caption(f"총 {len(pending_users)}명의 서류 검토 대기자가 있습니다.")
                for pu in pending_users:
                    st.markdown(f"**신청자:** {pu['name']} ({pu['gender']} · {pu['age']}세 · {pu.get('job')} · 신용 {pu['credit_score']}점)")
                    st.caption(f"연락처: {pu['phone']}")
                    
                    doc_path = pu.get("credit_doc_url", "")
                    if doc_path and not doc_path.startswith("["):
                        try:
                            raw_path = doc_path.split("/")[-1]
                            signed = supabase.storage.from_("credit-docs").create_signed_url(raw_path, 60)
                            s_url = signed.get("signedURL") or signed.get("signedUrl")
                            if s_url:
                                st.markdown(f'<a href="{s_url}" target="_blank">📄 [안심 열람] 증빙서류 1회용 링크 열기 (60초 후 만료)</a>', unsafe_allow_html=True)
                        except Exception as err:
                            st.caption(f"서류 링크 생성 오류: {err}")

                    col_ap, col_rj = st.columns(2)
                    with col_ap:
                        if st.button(f"✅ 승인 및 서류 영구 파기", key=f"btn_ap_3040_{pu['id']}"):
                            raw_fname = doc_path.split("/")[-1]
                            try:
                                supabase.storage.from_("credit-docs").remove([raw_fname])
                            except Exception:
                                pass
                            
                            supabase.table("users").update({
                                "is_verified": True,
                                "credit_status": "VERIFIED",
                                "credit_doc_url": "[심사 완료 후 안전 파기됨]"
                            }).eq("id", pu["id"]).execute()

                            send_aligo_notice_sms(pu["phone"], "블라인드 라온 신원 및 신용 검증이 완료되었습니다. 제출 서류는 안전하게 영구 파기되었습니다.")
                            st.success(f"{pu['name']} 님이 정회원으로 승인되었습니다.")
                            st.rerun()

                    with col_rj:
                        if st.button(f"🚫 반려 및 서류 파기", key=f"btn_rj_3040_{pu['id']}"):
                            raw_fname = doc_path.split("/")[-1]
                            try:
                                supabase.storage.from_("credit-docs").remove([raw_fname])
                            except Exception:
                                pass
                            
                            supabase.table("users").update({
                                "is_verified": False,
                                "credit_status": "REJECTED",
                                "credit_doc_url": "[반려 후 안전 파기됨]"
                            }).eq("id", pu["id"]).execute()

                            send_aligo_notice_sms(pu["phone"], "제출하신 증빙 서류가 기준에 미달하여 반려되었습니다. 다시 등록해 주세요.")
                            st.warning(f"{pu['name']} 님의 신청이 반려되었습니다.")
                            st.rerun()
                    st.divider()

    st.markdown("---")
    if st.button("로그아웃"):
        st.session_state.user_id = None
        st.session_state.user_info = None
        st.session_state.kakao_user = None
        st.rerun()
