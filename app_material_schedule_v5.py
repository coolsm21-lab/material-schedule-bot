import streamlit as st
import pandas as pd
import io, requests

st.set_page_config(page_title="자재일정 조회 시스템", page_icon="🏷️", layout="centered")
st.title("🏷️ 자재일정 조회 시스템")

# 모드 선택
mode = st.sidebar.radio("모드 선택", ["협력업체용", "관리자용"])

# ---- 협력업체용 ----
if mode == "협력업체용":
    st.subheader("🔍 협력업체 자재일정 조회")
    st.caption("OneDrive 최신 엑셀 기준으로 자동 조회됩니다.")

    onedrive_link = "https://1drv.ms/x/넣을링크여기"  # 🔹 여기에 네 OneDrive 링크 넣기
    try:
        download_url = onedrive_link.replace("redir?", "download?")
        file_content = requests.get(download_url).content
        df = pd.read_excel(io.BytesIO(file_content))

        # 업체코드 입력
        company_code = st.text_input("업체코드를 입력하세요 (예: A001)")
        if company_code:
            filtered = df[df["업체코드"].astype(str).str.strip().str.lower() == company_code.strip().lower()]
            if filtered.empty:
                st.error("❌ 등록되지 않은 업체코드입니다.")
            else:
                st.success(f"✅ {filtered.iloc[0]['업체명']} 업체 데이터 확인됨")
                st.dataframe(filtered.reset_index(drop=True))
                st.info("데이터는 OneDrive 최신버전 기준으로 자동 반영됩니다.")
        else:
            st.info("업체코드를 입력하면 해당 일정이 표시됩니다.")

    except Exception as e:
        st.error(f"데이터를 불러오는 중 오류 발생: {e}")

# ---- 관리자용 ----
else:
    st.subheader("🔐 관리자 전용 페이지")

    password = st.text_input("비밀번호를 입력하세요", type="password")
    correct_pw = "fflogi2025"  # 🔸 원하는 비밀번호로 변경 가능

    if password == correct_pw:
        st.success("✅ 인증 성공! 관리자 기능에 접근 가능합니다.")
        uploaded_file = st.file_uploader("📂 자재일정 엑셀 파일 업로드", type=["xlsx"])
        if uploaded_file:
            df = pd.read_excel(uploaded_file)
            st.success("파일 업로드 완료 ✅")
            st.dataframe(df)
            st.info("이 파일을 OneDrive에 업로드하면 협력업체용 화면에 자동 반영됩니다.")
        else:
            st.warning("엑셀 파일을 업로드하세요.")
    elif password:
        st.error("❌ 비밀번호가 틀렸습니다.")
    else:
        st.info("관리자 비밀번호를 입력하세요.")
