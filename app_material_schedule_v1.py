import streamlit as st
import pandas as pd

# 페이지 기본 설정
st.set_page_config(page_title="자재 일정 조회 챗봇", page_icon="🏷️", layout="centered")

st.title("🏷️ 자재 일정 조회 챗봇")
st.caption("협력업체 전용 / 엑셀 기반 간편조회")

# 엑셀 업로드
uploaded_file = st.file_uploader("📂 자재일정 엑셀 파일을 업로드하세요", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    required_cols = ["업체코드", "업체명", "브랜드", "오더번호", "납기일", "수량", "진행상태"]
    if not all(col in df.columns for col in required_cols):
        st.error(f"엑셀에 다음 열이 꼭 있어야 해요: {', '.join(required_cols)}")
    else:
        # 보안: 업체코드 입력
        st.markdown("---")
        company_code = st.text_input("🔐 업체코드를 입력하세요", placeholder="예: A001")

        if company_code:
            filtered = df[df["업체코드"].astype(str).str.strip().str.lower() == company_code.strip().lower()]

            if filtered.empty:
                st.error("❌ 등록되지 않은 업체코드입니다.")
            else:
                st.success(f"✅ {filtered.iloc[0]['업체명']} 업체 데이터 확인됨")

                # 챗봇 영역
                st.markdown("---")
                st.subheader("💬 자재 일정 챗봇")

                # 이전 대화 저장
                if "messages" not in st.session_state:
                    st.session_state.messages = []

                user_input = st.text_input("메시지를 입력하세요 (예: 납기일 알려줘)", key="user_input")

                if st.button("보내기"):
                    if user_input.strip():
                        st.session_state.messages.append(("👤", user_input))

                        # 간단한 챗봇 응답 로직
                        user_text = user_input.lower()
                        reply = ""

                        if "납기" in user_text:
                            reply = "\n".join([
                                f"📦 {row['브랜드']} / 오더번호 {row['오더번호']} → 납기일: {pd.to_datetime(row['납기일']).date()} / 수량: {row['수량']}ea / 상태: {row['진행상태']}"
                                for _, row in filtered.iterrows()
                            ])
                        elif "수량" in user_text:
                            reply = "\n".join([
                                f"{row['브랜드']} 오더({row['오더번호']}) 수량은 {row['수량']}ea 입니다."
                                for _, row in filtered.iterrows()
                            ])
                        elif "오더" in user_text:
                            reply = "\n".join([
                                f"{row['브랜드']} 오더번호: {row['오더번호']} / 납기일: {pd.to_datetime(row['납기일']).date()}"
                                for _, row in filtered.iterrows()
                            ])
                        else:
                            reply = "🔍 납기일, 수량, 오더번호 등으로 물어봐주세요!"

                        st.session_state.messages.append(("🤖", reply))

                # 대화 출력
                for speaker, text in st.session_state.messages:
                    with st.chat_message("user" if speaker == "👤" else "assistant"):
                        st.markdown(text)

                st.markdown("---")
                st.subheader("📋 전체 일정표")
                st.dataframe(filtered.reset_index(drop=True))

else:
    st.info("왼쪽에서 📂 자재일정.xlsx 파일을 먼저 업로드하세요.")
