import streamlit as st
import requests

# 카카오 REST API 키 (노블레스 라온과 동일한 앱 키)
KAKAO_REST_API_KEY = "53c242a5a25a23e264cd7e845b124a82"

# 🌟 블라인드 라온의 실제 배포 URL
KAKAO_REDIRECT_URI = "https://blind-raon-3040-xtwjdberufkkgwje2abbzq.streamlit.app"

def get_kakao_login_url():
    return (
        f"https://kauth.kakao.com/oauth/authorize?"
        f"client_id={KAKAO_REST_API_KEY}&"
        f"redirect_uri={KAKAO_REDIRECT_URI}&"
        f"response_type=code"
    )

def get_kakao_user_info(auth_code):
    token_url = "https://kauth.kakao.com/oauth/token"
    token_data = {
        "grant_type": "authorization_code",
        "client_id": KAKAO_REST_API_KEY,
        "redirect_uri": KAKAO_REDIRECT_URI,
        "code": auth_code,
    }
    headers = {"Content-type": "application/x-www-form-urlencoded;charset=utf-8"}
    
    try:
        res = requests.post(token_url, data=token_data, headers=headers)
        token_res = res.json()
        
        access_token = token_res.get("access_token")
        if not access_token:
            return None

        user_url = "https://kapi.kakao.com/v2/user/me"
        auth_headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-type": "application/x-www-form-urlencoded;charset=utf-8",
        }
        user_res = requests.get(user_url, headers=auth_headers).json()
        
        kakao_id = str(user_res.get("id"))
        properties = user_res.get("properties", {})
        nickname = properties.get("nickname", "라온 회원")
        profile_image = properties.get("profile_image", "")

        return {
            "id": kakao_id,
            "nickname": nickname,
            "profile_image": profile_image
        }
    except Exception:
        return None
