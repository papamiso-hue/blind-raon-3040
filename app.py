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

# 3. 서비스 기본 상수 및 보안 Secrets 연동
BRAND_NAME_KR = "블라인드 라온"
BRAND_NAME_EN = "BLIND RAON 3040"
SITE_URL = "https://blind-raon-3040-xtwjdberufkkgwje2abbzq.streamlit.app"
OG_IMAGE_URL = "https://images.unsplash.com/photo-1507679799987-c73779587ccf?q=80&w=1200&auto=format&fit=crop"
KAKAO_CHAT_URL = "https://open.kakao.com/o/sRas35Li"

ALIGO_API_KEY = st.secrets["ALIGO_API_KEY"]
ALIGO_USER_ID = st.secrets["ALIGO_USER_ID"]
ALIGO_SENDER = st.secrets["ALIGO_SENDER"]

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

# 비밀번호 단방향 암호화 함수
def hash_password(pwd: str) -> str:
    if not pwd:
        return ""
    return hashlib.sha256(pwd.strip().encode("utf-8")).hexdigest()

# 4. 맞춤법 및 오타 검증
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

QUESTIONS_75 = {
    1: {"category": "결혼관 및 가족 계획", "text": "1. 구체적인 결혼 희망 시점?", "options": ["1년 이내 빠른 결혼 희망", "1~2년 정도 진중한 연애 후 결정", "2~3년 이상 충분히 겪어본 후 결정", "혼인신고에 얽매이지 않는 진지한 연인 관계"]},
    2: {"category": "결혼관 및 가족 계획", "text": "2. 자녀 출산 계획?", "options": ["필수 (최소 1~2명 이상 희망)", "상호 합의에 따라 유연하게 결정", "딩크(DINK: 자녀 없이 둘만의 삶) 확고", "상대방의 뜻에 전적으로 맞춤"]},
    3: {"category": "결혼관 및 가족 계획", "text": "3. 자녀 양육의 주체?", "options": ["부부 공동 육아 (육아휴직 필수 활용)", "부모님이나 베이비시터 적극 도움 활용", "한쪽이 전업으로 집중 케어", "상호 커리어 상황에 따라 유연 대처"]},
    4: {"category": "결혼관 및 가족 계획", "text": "4. 양가 부모님과의 교류 빈도?", "options": ["월 1~2회 이상 정기적 식사 및 교류", "명절 및 생신 등 특별한 기념일 중심", "분기별 1회 정도의 편안한 거리감 유지", "각자 본인 부모님은 각자 챙기는 독립형"]},
    5: {"category": "결혼관 및 가족 계획", "text": "5. 명절(설/추석) 방문 문화?", "options": ["양가 당일 공평하게 순차 방문", "양가 한 번씩 번갈아 가며 방문", "명절 당일 가벼운 인사 후 부부만의 여행/휴식", "각자 본가 방문 후 집에서 조우"]},
    6: {"category": "결혼관 및 가족 계획", "text": "6. 부모님 부양 및 노후 지원?", "options": ["부모님 노후는 자녀가 일정 부분 책임 분담", "경제적 지원(용돈) 위주로 분담", "부모님 자산 내 자립 원칙, 간섭 최소화", "건강 악화 등 위급 상황 시에만 지원"]},
    7: {"category": "결혼관 및 가족 계획", "text": "7. 스몰 웨딩 vs 전통 예식?", "options": ["호텔/컨벤션 격식 있는 정통 예식", "보증인원 100명 안팎의 스몰/하우스 웨딩", "직계 가족만 모시는 식사 형태의 간소화", "예식 생략(혼인신고 및 여행으로 대체)"]},
    8: {"category": "결혼관 및 가족 계획", "text": "8. 혼수 및 예물·예단에 대한 생각?", "options": ["전통적 격식과 예의를 갖춘 예단/예물", "반지 등 필수 상징물만 간소하게 진행", "예단/예물 전면 생략, 신혼집에 올인", "상호 부모님 의견에 전적으로 맞춤"]},
    9: {"category": "결혼관 및 가족 계획", "text": "9. 시댁/처가와의 단톡방 개설?", "options": ["가족 전체 단톡방 적극 찬성 및 소통", "공지용 단톡방 개설은 무방", "단톡방 개설 부담, 배우자를 통한 소통 선호", "절대 사양 (사생활 보호 필수)"]},
    10: {"category": "결혼관 및 가족 계획", "text": "10. 주거지 선택 시 양가 거리?", "options": ["부모님 근처(도보/차량 10분) 거주 선호", "양가 중간 지점 거주", "직장 출퇴근 편리성이 최우선 (거리 무관)", "간섭 방지를 위해 양가와 먼 곳 선호"]},
    11: {"category": "결혼관 및 가족 계획", "text": "11. 자녀의 사교육에 대한 가치관?", "options": ["조기 교육 및 학군지 진입 필수", "아이가 원하는 분야 중심 맞춤 교육", "공교육과 체험·인성 위주 교육", "사교육 최소화, 자율성 존중"]},
    12: {"category": "결혼관 및 가족 계획", "text": "12. 부모님과의 동거 가능 여부?", "options": ["상황에 따라 동거 가능", "한 건물(위아래층)이나 인근 거주는 가능", "절대 동거 불가 (완전 독립 원칙)", "상대방 부모님 케어가 절실할 때만 한시적 허용"]},
    13: {"category": "결혼관 및 가족 계획", "text": "13. 자녀 출산 후 본인의 성씨 승계?", "options": ["부계 성씨 원칙 준수", "상호 협의하여 부모 성씨 선택 가능", "깊게 생각해보지 않음 (일반적 관례 수용)", "어머니 성씨 승계도 열려 있음"]},
    14: {"category": "결혼관 및 가족 계획", "text": "14. 집안 대소사(제사 등) 참석?", "options": ["모든 제사 및 집안 행사 성실 참석", "주요 제사 1~2개만 간소화하여 참석", "제사 문화 폐지 또는 가족 모임으로 대체 희망", "종교적 이유 등으로 제사 미참석"]},
    15: {"category": "결혼관 및 가족 계획", "text": "15. 결혼 전 파혼/이혼에 대한 가치관?", "options": ["어떠한 갈등도 끝까지 대화로 극복해야 함", "가치관 훼손이나 외도/폭력 시 즉시 결별/이혼", "신뢰 상실 시 미련 없이 정리", "자녀가 있다면 자녀 독립까지 유지 노력"]},

    16: {"category": "경제관 및 자산 관리", "text": "16. 신혼집 마련 자금 분담 비율?", "options": ["남녀 5:5 완전 공평 분담", "각자 보유 자산 비례 분담", "경제적 여유가 더 있는 쪽이 주도적 분담", "전통적 관례(주택 남성 / 혼수 여성) 선호"]},
    17: {"category": "경제관 및 자산 관리", "text": "17. 결혼 후 부부 자산 관리 방식?", "options": ["급여 통장 전액 합산 + 용돈제 운용", "공동 생활비 통장 각출 + 잉여 자산 각자 관리", "한 사람이 전담 관리 (금융 감각 있는 사람)", "완벽한 각자 관리 (생활비만 항목별 자동이체)"]},
    18: {"category": "경제관 및 자산 관리", "text": "18. 결혼 전 자산 및 부채 공개 시점?", "options": ["교제 초반 진지한 대화 시 전면 공개", "결혼 승낙 및 구체적 준비 시작 시 공개", "신혼집 계약 직전 필수 자금만 공개", "굳이 상세 내역까지 100% 깔 필요는 없음"]},
    19: {"category": "경제관 및 자산 관리", "text": "19. 주식 / 코인 등 고위험 투자?", "options": ["절대 반대 (원금 손실 공포형)", "총자산의 10~20% 이내 소액 운용 찬성", "본인 용돈/여유 자금 범위 내 자율 투자 인정", "고수익 적극 지향 (적극적 레버리지 찬성)"]},
    20: {"category": "경제관 및 자산 관리", "text": "20. 주택 매수를 위한 대출 허용 범위?", "options": ["대출 최소화 (원리금 상환액이 월 소득 20% 이내)", "감당 가능한 수준 (월 소득 30~40% 상환)", "상급지 갈아타기라면 소득 50% 수준까지 감수", "무리한 매수 반대, 전월세 거주 선호"]},
    21: {"category": "경제관 및 자산 관리", "text": "21. 본인 순수 개인 용돈 규모 (월 기준)?", "options": ["30만 원 미만 (극단적 절약)", "30만 ~ 50만 원 수준", "50만 ~ 100만 원 수준", "100만 원 이상 (자율적 사회생활 보장)"]},
    22: {"category": "경제관 및 자산 관리", "text": "22. 양가 부모님 정기 용돈 및 명절 비용?", "options": ["매월 정기 용돈 필수 (양가 동일 금액)", "생신/명절/어버이날에만 목돈 지급", "상호 부모님 경제력에 따라 차등 지급", "정기 지원 지양 (선물 및 식사 대접 위주)"]},
    23: {"category": "경제관 및 자산 관리", "text": "23. 명품, 고가 소비 성향?", "options": ["실용성 위주 (가성비 철저 추구)", "1년에 1~2번 나를 위한 특별 보상형 소비", "취향과 품위를 위한 가치 소비 적극 인정", "타인 시선 의식한 사치성 소비 절대 지양"]},
    24: {"category": "경제관 및 자산 관리", "text": "24. 배우자 몰래 형성하는 비상금?", "options": ["절대 불가 (모든 자산 투명 공개 원칙)", "비상시를 위한 소액(수백만 원) 정도는 묵인", "각자 프라이버시 영역이므로 얼마든지 인정", "서로 묻지 않는 것이 미덕"]},
    25: {"category": "경제관 및 자산 관리", "text": "25. 가족/친인척 대상 금전 대여?", "options": ["어떠한 경우에도 절대 불가", "100만~200만 원 선에서 안 받을 생각으로 지급", "배우자 사전 동의 하에 제한적 대여 가능", "직계 가족이라면 능력껏 도와야 함"]},
    26: {"category": "경제관 및 자산 관리", "text": "26. 배달 음식 및 외식 소비 빈도?", "options": ["주 1회 이하 (집밥/밀키트 중심 절약)", "주 2~3회 적절한 외식과 배달", "주 4회 이상 (시간 절약과 미식 중심)", "평일 집밥, 주말은 전면 외식"]},
    27: {"category": "경제관 및 자산 관리", "text": "27. 은퇴 및 노후 준비 우선순위?", "options": ["국민연금 + 퇴직연금 + 개인연금 3층 보장", "수익형 부동산(월세 흐름) 세팅", "미국 배당주/지수 ETF 장기 적립", "자녀 교육과 현재 삶이 우선, 노후는 추후 고민"]},
    28: {"category": "경제관 및 자산 관리", "text": "28. 가계부 작성 및 지출 결산?", "options": ["매월 정기적으로 부부 가계부 결산 필수", "큰 지출(50만 원 이상)만 상호 공유", "카드 명세서 각자 확인하는 수준", "가계부 작성 불필요 (각자 한도 내 관리)"]},
    29: {"category": "경제관 및 자산 관리", "text": "29. 배우자의 기존 학자금/마통 대출?", "options": ["결혼 전 본인이 전액 청산 후 입주 원칙", "결혼 후 공동 자금으로 최우선 상환", "대출자 본인 용돈/수입으로 개별 상환", "저금리라면 굳이 조기 상환하지 않고 운용"]},
    30: {"category": "경제관 및 자산 관리", "text": "30. 복권, 사행성 오락에 대한 생각?", "options": ["1천 원짜리 로또도 낭비 (일절 반대)", "매주 5천 원~1만 원 소소한 로또는 취미 인정", "여행지 카지노나 레저성 게임은 인정", "어떠한 도박성 행위도 절대 용납 불가"]},

    31: {"category": "직업관 및 커리어·가사", "text": "31. 맞벌이 지속 여부?", "options": ["평생 맞벌이 필수 (소득 극대화)", "출산·육아 시기에만 한시적 외벌이 허용", "한 사람 소득이 충분하다면 외벌이 선호", "언제든 원할 때 퇴사/휴직 지지"]},
    32: {"category": "직업관 및 커리어·가사", "text": "32. 가사 노동(청소·빨래·요리) 분담 원칙?", "options": ["요일/구역별 5:5 철저 분담", "잘하는 분야 전담 (요리는 남편, 청소는 아내 등)", "소득/퇴근 시간에 비례하여 유연 분담", "가전제품 및 가사도우미 적극 활용"]},
    33: {"category": "직업관 및 커리어·가사", "text": "33. 식사 준비 및 요리 성향?", "options": ["건강을 위해 매일 직접 요리하는 밥상 선호", "밀키트, 반찬가게 적극 활용", "주말 위주 요리, 평일은 간단 해결", "요리에 스트레스받지 않고 배달/간편식 선호"]},
    34: {"category": "직업관 및 커리어·가사", "text": "34. 잦은 야근 및 주말 출근에 대한 이해도?", "options": ["일과 커리어 성장을 위해 얼마든지 지지", "사전 공유만 된다면 이해 가능", "워라밸 필수 (가족과의 시간이 부족하면 반대)", "직장 이동 권유"]},
    35: {"category": "직업관 및 커리어·가사", "text": "35. 배우자의 이직, 진학, 유학 희망?", "options": ["커리어 점프라면 전폭적 재정/심리 지원", "경제적 공백이 크지 않은 선에서만 찬성", "현실적 가계 유지가 우선이므로 신중 반대", "결혼 후에는 무리한 도전 지양 희망"]},
    36: {"category": "직업관 및 커리어·가사", "text": "36. 배우자의 개인 사업 / 창업 희망 시?", "options": ["확실한 계획과 종잣돈 범위 내 전폭 지지", "가족 자산 담보 대출이 없다면 인정", "안정적 직장 유지가 우선이므로 결사반대", "동업 형태로 함께 참여할 의사 있음"]},
    37: {"category": "직업관 및 커리어·가사", "text": "37. 직장 회식 및 술자리 빈도?", "options": ["월 1~2회 필수 회식만 참석 희망", "업무상 네트워킹이라면 주 1~2회도 이해", "2차, 3차 이어지는 늦은 귀가는 절대 반대", "자율에 맡기되 귀가 시간 사전 공유 필수"]},
    38: {"category": "직업관 및 커리어·가사", "text": "38. 지방 발령 또는 해외 파견 시?", "options": ["부부 동반 이주 필수 (절대 떨어져 살 수 없음)", "단기(1~2년)라면 주말 부부 가능", "아이 교육이나 커리어가 우선인 쪽 거주지 유지", "원거리 근무 조건 자체를 거절하길 바람"]},
    39: {"category": "직업관 및 커리어·가사", "text": "39. 집안 청결도 및 정리정돈 기준?", "options": ["매일 먼지 없이 칼각 정리정돈 유지", "주말에 한 번 몰아서 대청소", "눈에 거슬리는 사람 먼저 치우기", "어질러져 있어도 크게 스트레스받지 않음"]},
    40: {"category": "직업관 및 커리어·가사", "text": "40. 재택근무 시 배우자 배려?", "options": ["업무 시간엔 완벽한 직장 모드로 터치 금지", "집안일과 업무 유연 병행 기대", "집 안 독립된 서재/오피스 공간 필수", "카페나 공유오피스 출근 선호"]},
    41: {"category": "직업관 및 커리어·가사", "text": "41. 정년퇴직 후 인생 설계?", "options": ["은퇴 후에도 소소한 일/봉사 지속 희망", "귀농·귀촌 또는 전원생활", "해외 한 달 살기 등 완전한 휴식과 여가", "도심에 머물며 문화생활 향유"]},
    42: {"category": "직업관 및 커리어·가사", "text": "42. 직장 동료(이성 포함)와의 친목?", "options": ["공적인 업무 소통 외 사적 연락 자제", "팀 단위 친목 모임은 자연스럽게 인정", "1:1 점심/커피는 업무 연장이면 가능", "퇴근 후 사적 만남은 절대 불가"]},
    43: {"category": "직업관 및 커리어·가사", "text": "43. 3대 가전(식세기, 로봇청소기, 건조기)?", "options": ["3대 이모님 필수 구비 (시간 절약 최우선)", "필요성 검토 후 선별적 구매", "손으로 직접 하는 것이 더 깨끗하고 경제적", "최신 AI 가전으로 전면 스마트홈 구축"]},
    44: {"category": "직업관 및 커리어·가사", "text": "44. 가사 분담 불이행 시 해결책?", "options": ["벌금제 도입 또는 패널티 부여", "즉시 가사도우미 유료 고용", "조용히 내가 먼저 하고 나중에 차분히 대화", "감정 싸움으로 번지기 전에 규칙 재조정"]},
    45: {"category": "직업관 및 커리어·가사", "text": "45. 경력 단절에 대한 생각?", "options": ["어떠한 경우에도 경력 단절 절대 반대", "육아기 2~3년 정도의 경력 단절은 감수", "재취업 준비가 되어 있다면 단절 무방", "전업주부로서의 삶도 훌륭한 커리어로 인정"]},

    46: {"category": "일상·생활 습관 및 취미", "text": "46. 흡연(연초/전자담배)에 대한 기준?", "options": ["절대 비흡연자 필수 (과거 흡연도 싫음)", "전자담배까지는 양해 가능", "실외 흡연 및 냄새 관리 철저하면 무관", "본인도 흡연자이므로 상관없음"]},
    47: {"category": "일상·생활 습관 및 취미", "text": "47. 음주 빈도 및 주류 취향?", "options": ["일절 안 마심 (술자리 기피)", "주 1~2회 가볍게 반주나 와인/맥주 한 캔", "주 3~4회 애주가 스타일", "취할 때까지 마시는 폭음 문화 절대 반대"]},
    48: {"category": "일상·생활 습관 및 취미", "text": "48. 주말 여가 활용 패턴?", "options": ["무조건 집에서 쉬는 집돌이/집순이", "캠핑, 등산, 골프, 드라이브 등 야외 아웃도어", "맛집, 카페, 전시회 등 핫플레이스 탐방", "자기계발(운동, 독서, 스터디) 중심"]},
    49: {"category": "일상·생활 습관 및 취미", "text": "49. 반려동물(개/고양이) 양육?", "options": ["가족과 같으므로 이미 키우고 있거나 키울 예정", "털 날림, 냄새 등으로 실내 양육 절대 반대", "상대방이 원하면 키울 의향 있음", "아이 낳기 전까지만 한시적 양육"]},
    50: {"category": "일상·생활 습관 및 취미", "text": "50. 종교 활동 및 신앙심?", "options": ["동일 종교 필수 + 주말 예배/미사 필수", "무교 선호 (종교 활동 강요 절대 사양)", "종교는 자유이나 집안 행사/자녀 강요 금지", "종교 무관 (상대방 신앙 존중)"]},
    51: {"category": "일상·생활 습관 및 취미", "text": "51. 수면 패턴 및 기상 시간?", "options": ["밤 11시 취침 - 아침 6시 기상 (아침형)", "새벽 1~2시 취침 - 아침 8~9시 기상 (저녁형)", "주말엔 무조건 늦잠과 낮잠 필수", "불규칙한 편이나 상대방에게 맞출 수 있음"]},
    52: {"category": "일상·생활 습관 및 취미", "text": "52. 잠자리 습관 (코골이, 뒤척임 등)?", "options": ["소음에 민감하여 각방 또는 트윈베드 선호", "암막 커튼, 보조기구 적극 활용", "껴안고 자야 하며 분리 수면 절대 반대", "크게 예민하지 않아 무던하게 잠"]},
    53: {"category": "일상·생활 습관 및 취미", "text": "53. 여행 스타일?", "options": ["분 단위 계획표 세우는 파워 J 스타일", "발길 닿는 대로 움직이는 즉흥 힐링(P 스타일)", "호캉스, 리조트 등 휴양 위주", "관광지 전부 돌아보는 액티비티 중심"]},
    54: {"category": "일상·생활 습관 및 취미", "text": "54. 식습관 및 음식 취향?", "options": ["한식 파 (국, 찌개, 밥 필수)", "양식, 육류, 미식 다이닝 선호", "비건, 채식 또는 건강 다이어트 식단", "가리는 것 없이 아무거나 잘 먹음"]},
    55: {"category": "일상·생활 습관 및 취미", "text": "55. 집안 실내 온도 조절?", "options": ["여름엔 24도 이하 풀가동 (더위 못 참음)", "에어컨 바람 싫어함 (27도 이상 또는 선풍기)", "겨울철 따뜻한 온돌 난방 필수 (추위 못 참음)", "관리비 절약을 위해 적정 실내온도 엄격 준수"]},
    56: {"category": "일상·생활 습관 및 취미", "text": "56. TV 및 스마트폰 사용 습관?", "options": ["집에 오면 TV나 유튜브 항상 틀어놓음", "미디어 단식 (책 읽거나 대화 중심)", "식사 중 스마트폰 사용 절대 금지", "각자 자유롭게 침대에서 스마트폰 하는 시간 존중"]},
    57: {"category": "일상·생활 습관 및 취미", "text": "57. 운동 및 자기관리 루틴?", "options": ["주 3~5회 헬스, 필라테스, 러닝 필수", "주말 가벼운 산책이나 스트레칭", "다이어트와 체형 관리에 엄격한 편", "운동을 거의 안 하는 편"]},
    58: {"category": "일상·생활 습관 및 취미", "text": "58. 사우나, 찜질방, 스파 선호도?", "options": ["땀 빼고 목욕하는 문화 매우 좋아함", "대중탕 위생 문제로 절대 가지 않음", "개별 료칸이나 프라이빗 스파만 선호", "가끔 기분 전환용으로 무난하게 이용"]},
    59: {"category": "일상·생활 습관 및 취미", "text": "59. 차 안에서의 흡연 및 취식?", "options": ["내 차 안에서는 물 이외 취식/흡연 절대 불가", "냄새 안 나는 간단한 음료/과자는 허용", "자유롭게 음식 섭취 가능", "차는 이동 수단일 뿐, 털털하게 관리"]},
    60: {"category": "일상·생활 습관 및 취미", "text": "60. 문신(타투)에 대한 시선?", "options": ["작은 레터링이나 감성 타투는 개성으로 인정", "크기 무관 타투 일절 반대", "혐오감을 주지 않는 선에서 자유", "본인도 타투가 있어 긍정적"]},

    61: {"category": "갈등 해결 및 관계·대화", "text": "61. 다퉜을 때 갈등 해결 방식?", "options": ["감정이 상해도 무조건 당일 밤 대화로 풀기", "감정을 가라앉힐 생각할 시간(1~2일) 갖기", "사과 편지나 장문의 카톡으로 이성적 정리", "자고 일어나면 아무 일 없었다는 듯 일상 복귀"]},
    62: {"category": "갈등 해결 및 관계·대화", "text": "62. 화가 났을 때 감정 표출 방식?", "options": ["침묵 모드 (말을 섞지 않음)", "서운한 점을 논리적으로 조목조목 따짐", "눈물이 먼저 나서 대화가 중단됨", "솔직하게 언성을 높여서라도 감정을 즉각 표출"]},
    63: {"category": "갈등 해결 및 관계·대화", "text": "63. 배우자의 이성 친구 허용 범위?", "options": ["1:1 만남(식사/술/커피) 절대 불가", "단체 모임에 섞여 있는 것은 무방", "배우자에게 사전 공유한다면 1:1 커피/식사 가능", "오랜 동창/친구라면 밤늦은 술자리도 신뢰"]},
    64: {"category": "갈등 해결 및 관계·대화", "text": "64. 스마트폰 비밀번호 공개 여부?", "options": ["부부라도 완벽한 프라이버시 (절대 열람 금지)", "비번은 공유하되 굳이 들여다보지 않음", "원할 때 언제든 서로 자유롭게 확인", "위치 추적 앱 설치까지 상호 동의 가능"]},
    65: {"category": "갈등 해결 및 관계·대화", "text": "65. 사랑 표현(애정 표현) 스타일?", "options": ["하루에도 수십 번 사랑한다 말하는 언어형", "스킨십(손잡기, 포옹, 뽀뽀) 중심형", "필요한 것을 챙겨주고 행동으로 보여주는 헌신형", "무뚝뚝하지만 뒤에서 묵묵히 챙겨주는 스타일"]},
    66: {"category": "갈등 해결 및 관계·대화", "text": "66. 기념일(생일, 결혼기념일 등) 챙기기?", "options": ["호텔, 파인다이닝, 선물 등 성대한 기념 필수", "생일과 결혼기념일 딱 2개만 정성껏 챙김", "특별한 이벤트보다 따뜻한 말과 맛있는 식사", "굳이 챙기지 않고 지나가도 서운하지 않음"]},
    67: {"category": "갈등 해결 및 관계·대화", "text": "67. 데이트 및 대화 시 침묵의 편안함?", "options": ["대화가 끊기면 어색해서 계속 말을 거는 편", "한 공간에서 각자 딴짓하며 침묵해도 편안함", "깊이 있는 진지한 대화가 매일 이어져야 함", "유머와 농담 위주의 가벼운 소통 선호"]},
    68: {"category": "갈등 해결 및 관계·대화", "text": "68. 배우자의 슬럼프 대처법?", "options": ["해결책을 제시하고 극복 방법을 찾아줌 (T 성향)", "묻지도 따지지도 않고 꼭 안아주고 공감 (F 성향)", "혼자만의 시간을 가질 수 있게 방해하지 않음", "기분 전환을 위해 맛집이나 여행으로 이끌기"]},
    69: {"category": "갈등 해결 및 관계·대화", "text": "69. 외모 및 옷차림에 대한 지적?", "options": ["상호 품위를 위해 스타일링 피드백 적극 수용", "개인의 개성이므로 옷차림 지적 절대 사양", "공식 석상(결혼식, 양가 방문)에서만 코칭", "트레이닝복 등 편안한 차림 지향"]},
    70: {"category": "갈등 해결 및 관계·대화", "text": "70. 싸울 때 절대 쓰지 말아야 할 금기어?", "options": ["\"우리 헤어져\", \"이혼해\" (극단적 표현)", "\"너희 집은 왜 그러니?\" (원가족 비하)", "\"네가 다 그렇지 뭐\" (인격 비하 및 단정)", "상대방의 과거사나 컴플렉스 들추기"]},
    71: {"category": "갈등 해결 및 관계·대화", "text": "71. 사생활(혼자만의 시간) 필요도?", "options": ["주 1~2회 퇴근 후 완벽히 혼자 있는 시간 필수", "주말 중 반나절은 개인 취미 시간 보장", "부부는 모든 여가와 일상을 함께해야 함", "서로 터치하지 않는 독립적인 생활 패턴 선호"]},
    72: {"category": "갈등 해결 및 관계·대화", "text": "72. SNS 일상 및 얼굴 공개?", "options": ["부부 일상 및 얼굴 사진 적극 포스팅", "비공개 계정으로 소수 지인과만 공유", "눈팅 위주이며 내 사생활 업로드 절대 안 함", "배우자나 자녀 얼굴 공개는 결사반대"]},
    73: {"category": "갈등 해결 및 관계·대화", "text": "73. 이전 연애사 언급에 대한 태도?", "options": ["과거는 과거일 뿐, 서로 솔직히 다 알아도 됨", "절대로 먼저 묻지도 말고 말하지도 않기", "연애 횟수나 기간 정도는 가볍게 공유", "이전 연애 흔적(사진, 선물)은 결혼 전 완벽 폐기"]},
    74: {"category": "갈등 해결 및 관계·대화", "text": "74. 술 취한 상태에서의 주사 용인 기준?", "options": ["잠들거나 말 많아지는 수준까지만 허용", "필름 끊김(블랙아웃) 1회 발생 시 엄중 경고", "주사로 인한 시비나 폭언 시 즉시 결별 사유", "술자리 연락 두절 시 신뢰 회복 불가"]},
    75: {"category": "갈등 해결 및 관계·대화", "text": "75. 내가 생각하는 성공적인 결혼 생활이란?", "options": ["경제적 풍요와 사회적 성공을 함께 일구는 팀플레이", "세상 누구보다 편안한 내 편이 집에 있다는 정서적 안정", "서로의 자유와 성장을 응원하는 독립적인 동반자", "아이를 올바르게 키워 화목한 가정을 완성하는 것"]}
}

# --- 프리미엄 3040 리뉴얼 UI CSS ---
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

# 비밀번호 찾기 세션 상태
if "reset_sms_code" not in st.session_state:
    st.session_state.reset_sms_code = None
if "reset_verified_phone" not in st.session_state:
    st.session_state.reset_verified_phone = None
if "reset_target_uid" not in st.session_state:
    st.session_state.reset_target_uid = None

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
                # 암호화 해시 및 평문 동시 비교 (기존 가입자 자동 호환)
                hashed_input = hash_password(login_pwd)
                res = supabase.table("users").select("*")\
                    .eq("name", login_name.strip())\
                    .eq("phone", clean_p)\
                    .execute()

                if res.data:
                    u = res.data[0]
                    stored_pwd = u.get("password", "")
                    
                    # 해시값 일치 또는 이전 평문 일치 여부 확인
                    if stored_pwd == hashed_input or stored_pwd == login_pwd.strip():
                        if u.get("is_suspended"):
                            st.error("🚫 제재 조치된 계정입니다. 고객센터로 문의해 주세요.")
                        else:
                            # 이전 평문 비밀번호였던 경우, 암호화 해시로 자동 업그레이드
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

        # 🔑 비밀번호 찾기 (SMS 인증 기반 재설정 창구)
        with st.expander("🔑 비밀번호를 잊으셨나요? (간편 재설정)"):
            st.caption("가입 시 등록한 성명과 휴대폰 번호로 인증 후 새 비밀번호를 설정할 수 있습니다.")
            f_name = st.text_input("가입 성명", key="f_name")
            col_fp1, col_fp2 = st.columns([2.5, 1.2])
            with col_fp1:
                f_phone = st.text_input("가입 휴대폰 번호", placeholder="01012345678", key="f_phone")
            with col_fp2:
                st.write("")
                btn_find_sms = st.button("인증문자 발송", key="btn_find_sms")

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
                        st.session_state.reset_sms_code = code
                        st.session_state.reset_verified_phone = clean_fp
                        st.session_state.reset_target_uid = chk[0]["id"]
                        send_aligo_sms(clean_fp, code)
                        st.success("인증번호가 발송되었습니다. 아래에 입력해 주세요.")

            if st.session_state.reset_sms_code:
                in_fcode = st.text_input("문자 인증번호 6자리", key="in_find_code")
                new_reset_pwd = st.text_input("새로운 간편 비밀번호 (4~6자리)", type="password", key="new_reset_pwd")
                
                if st.button("새 비밀번호로 변경 및 저장", key="btn_do_reset"):
                    if in_fcode.strip() != st.session_state.reset_sms_code:
                        st.error("인증번호가 일치하지 않습니다.")
                    elif len(new_reset_pwd.strip()) < 4:
                        st.error("비밀번호는 최소 4자리 이상이어야 합니다.")
                    else:
                        supabase.table("users").update({
                            "password": hash_password(new_reset_pwd)
                        }).eq("id", st.session_state.reset_target_uid).execute()
                        st.session_state.reset_sms_code = None
                        st.session_state.reset_target_uid = None
                        st.success("🎉 비밀번호가 안전하게 재설정되었습니다! 새 비밀번호로 로그인해 주세요.")

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

        st.markdown("##### 🎯 3040 필수 가치관 5대 문답 (가입용)")
        a1 = st.radio(QUESTIONS_75[1]["text"], QUESTIONS_75[1]["options"], key="jq_1")
        a2 = st.radio(QUESTIONS_75[2]["text"], QUESTIONS_75[2]["options"], key="jq_2")
        a3 = st.radio(QUESTIONS_75[3]["text"], QUESTIONS_75[3]["options"], key="jq_3")
        a4 = st.radio(QUESTIONS_75[4]["text"], QUESTIONS_75[4]["options"], key="jq_4")
        a5 = st.radio(QUESTIONS_75[5]["text"], QUESTIONS_75[5]["options"], key="jq_5")

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

                    # 비밀번호 암호화 저장
                    new_u = supabase.table("users").insert({
                        "name": j_name.strip(),
                        "phone": clean_jp,
                        "password": hash_password(j_pwd),
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

                with st.expander(f"🔍 가치관 대조표 ({len(common_keys)}개 문항 일치율 확인)"):
                    for q_num in sorted(list(common_keys)):
                        if q_num in QUESTIONS_75:
                            q_text = QUESTIONS_75[q_num]["text"]
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

        # 🎯 3040 심층 가치관 진단 75문항 아코디언 영역
        st.markdown("---")
        st.markdown("#### 🎯 3040 심층 가치관 진단 (75문항)")
        st.caption("답변을 많이 채울수록 상대방과의 매칭 일치율 정확도가 비약적으로 향상됩니다.")

        categories = [
            ("1. 결혼관 및 가족 계획 (1~15번)", 1, 15),
            ("2. 경제관 및 자산 관리 (16~30번)", 16, 30),
            ("3. 직업관 및 커리어·가사 (31~45번)", 31, 45),
            ("4. 일상·생활 습관 및 취미 (46~60번)", 46, 60),
            ("5. 갈등 해결 및 관계·대화 (61~75번)", 61, 75)
        ]

        for cat_title, start_q, end_q in categories:
            with st.expander(cat_title):
                cat_answers = {}
                for q_num in range(start_q, end_q + 1):
                    if q_num in QUESTIONS_75:
                        q_info = QUESTIONS_75[q_num]
                        curr_ans = my_answers.get(q_num)
                        default_idx = q_info["options"].index(curr_ans) if curr_ans in q_info["options"] else 0
                        
                        ans = st.radio(
                            q_info["text"],
                            q_info["options"],
                            index=default_idx,
                            key=f"q75_{q_num}"
                        )
                        cat_answers[q_num] = ans

                if st.button(f"💾 {cat_title.split('.')[1][:8]} 영역 답변 저장", key=f"btn_save_cat_{start_q}"):
                    for q_num, ans_val in cat_answers.items():
                        exist = supabase.table("user_answers").select("id").eq("user_id", me["id"]).eq("question_num", q_num).execute().data
                        if exist:
                            supabase.table("user_answers").update({"answer_value": ans_val}).eq("id", exist[0]["id"]).execute()
                        else:
                            supabase.table("user_answers").insert({
                                "user_id": me["id"],
                                "question_num": q_num,
                                "answer_value": ans_val
                            }).execute()
                    st.success("✅ 해당 영역의 가치관 답변이 성공적으로 저장되었습니다!")
                    st.rerun()

    st.markdown("---")
    if st.button("로그아웃"):
        st.session_state.user_id = None
        st.session_state.user_info = None
        st.rerun()
