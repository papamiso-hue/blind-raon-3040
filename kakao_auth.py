import streamlit as st
import requests

# 발급받은 카카오 정보
KAKAO_REST_API_KEY = "53c242a5a25a23e264cd7e845b124a82"
KAKAO_REDIRECT_URI = "https://blindraon.com"

def get_kakao_login_url():
    """카카오 인증 인가 코드 요청 URL 생성"""
    return (
        f"https://kauth.kakao.com/oauth/authorize?"
        f"client_id={KAKAO_REST_API_KEY}&"
        f"redirect_uri={KAKAO_REDIRECT_URI}&"
        f"response_type=code"
    )

def get_kakao_user_info(auth_code):
    """인가 코드로 토큰 발급 및 사용자 프로필 조회"""
    token_url = "https://kauth.kakao.com/oauth/token"
    token_data = {
        "grant_type": "authorization_code",
        "client_id": KAKAO_REST_API_KEY,
        "redirect_uri": KAKAO_REDIRECT_URI,
        "code": auth_code,
    }
    headers = {"Content-type": "application/x-www-form-urlencoded;charset=utf-8"}
    
    token_res = requests.post(token_url, data=token_data, headers=headers).json()
    access_token = token_res.get("access_token")
    
    if not access_token:
        return None

    user_url = "https://kapi.kakao.com/v2/user/me"
    auth_headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-type": "application/x-www-form-urlencoded;charset=utf-8",
    }
    user_res = requests.get(user_url, headers=auth_headers).json()
    
    kakao_id = user_res.get("id")
    properties = user_res.get("properties", {})
    nickname = properties.get("nickname", "카카오 회원")
    profile_image = properties.get("profile_image", "")

    return {
        "id": kakao_id,
        "nickname": nickname,
        "profile_image": profile_image
    }
