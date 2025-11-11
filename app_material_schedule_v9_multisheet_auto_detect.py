import os
import pandas as pd
import streamlit as st

st.set_page_config(page_title="🏷️ 자재일정 멀티시트 챗봇", layout="centered")
st.title("🏷️ 자재일정 멀티시트 챗봇")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# ----------------------------------------------
# 엑셀 자동 탐색 및 멀티시트 병합
# ----------------------------------------------
@st.cache_data(show_spinner=False)
def load_all_excel_data(data_dir=DATA_DIR):
    if not os.path.isdir(data_dir):
        raise FileNotFoundError(f"데이터 폴더가 없습니다: {data_dir}")
    excel_files = [f for f in os.listdir(data_dir) if f.endswith(".xlsx")]
    if not excel_files:
        raise FileNotFoundError("엑셀 파일이 없습니다. /data 폴더에 업로드해주세요.")

    latest_file = max([os.path.join(data_dir, f) for f in excel_files], key=os.path.getmtime)
    st.info(f"📂 불러온 파일: **{os.path.basename(latest_file)}**")

    all_sheets = pd.read_excel(latest_file, sheet_name=None, engine="openpyxl")
    df_list = []
    for sheet_name, sheet_df in all_sheets.items():
        sheet_df["시트명"] = sheet_name
        df_list.append(sheet_df)
    merged_df = pd.concat(df_list, ignore_index=True)
    return merged_df

# ----------------------------------------------
# 협력사 필터링
# ----------------------------------------------
def filter_by_company(df, company_code):
    colnames = [c.lower() for c in df.columns]
    if "업체코드" in colnames:
        code_col = df.columns[colnames.index("업체코드")]
    elif "협력사코드" in colnames:
        code_col = df.columns[colnames.index("협력사코드")]
    else:
        raise ValueError("업체코드/협력사코드 컬럼이 없습니다.")
    df[code_col] = df[code_col].astype(str).str.strip().str.lower()
    return df[df[code_col] == str(company_code).strip().lower()]

# ----------------------------------------------
# 기본 요약
# ----------------------------------------------
def summarize_company_data(df):
    summary = ""
    if "시트명" in df.columns:
        counts = df["시트명"].value_counts().to_dict()
        summary += "📑 시트별 데이터 건수\\n"
        for s, n in counts.items():
            summary += f"- {s}: {n}건\\n"
        summary += "\\n"
    if "수량" in df.columns:
        total_qty = df["수량"].sum()
        summary += f"📦 전체 수량 합계: {total_qty:,}\\n"
    summary += "✅ 모든 시트 데이터가 포함되어 있습니다."
    return summary

# ----------------------------------------------
# 간단 챗봇 응답
# ----------------------------------------------
def chatbot_answer(df, question):
    q = question.lower()
    if "입고" in q:
        data = df[df["구분"].astype(str).str.contains("입고", na=False)]
        total = data["수량"].sum() if not data.empty else 0
        return f"입고 총합은 {int(total):,}건입니다."
    elif "출고" in q:
        data = df[df["구분"].astype(str).str.contains("출고", na=False)]
        total = data["수량"].sum() if not data.empty else 0
        return f"출고 총합은 {int(total):,}건입니다."
    elif "반품" in q:
        data = df[df["구분"].astype(str).str.contains("반품", na=False)]
        total = data["수량"].sum() if not data.empty else 0
        return f"반품 총합은 {int(total):,}건입니다."
    elif "시트" in q:
        sheets = df["시트명"].unique().tolist()
        return "엑셀에 포함된 시트: " + ", ".join(sheets)
    else:
        return "질문을 이해하지 못했어요. '입고', '출고', '반품', '시트' 등으로 물어보세요."

# ----------------------------------------------
# 페이지 흐름 관리
# ----------------------------------------------
if "page" not in st.session_state:
    st.session_state["page"] = "start"
if "company_data" not in st.session_state:
    st.session_state["company_data"] = None

# ----------------------------------------------
# 페이지 1: 협력사 코드 입력
# ----------------------------------------------
if st.session_state["page"] == "start":
    st.subheader("🔹 협력업체 코드 입력")
    code = st.text_input("🏭 협력업체 코드", placeholder="예: A001 / B002 ...")
    if st.button("조회하기") and code:
        try:
            df_all = load_all_excel_data()
            filtered_df = filter_by_company(df_all, code)
            if filtered_df.empty:
                st.error("해당 협력사 코드 데이터가 없습니다.")
            else:
                st.session_state["company_data"] = filtered_df
                st.session_state["page"] = "chatbot"
                st.experimental_rerun()
        except Exception as e:
            st.error(f"데이터 로드 오류: {e}")

# ----------------------------------------------
# 페이지 2: 챗봇
# ----------------------------------------------
elif st.session_state["page"] == "chatbot":
    df = st.session_state["company_data"]
    st.markdown("### 🤖 협력사 전용 챗봇")
    st.markdown(summarize_company_data(df))

    user_q = st.chat_input("질문을 입력하세요 (예: 입고 수량, 반품 총합, 시트 목록 등)")

    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    for msg in st.session_state["chat_history"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if user_q:
        st.session_state["chat_history"].append({"role": "user", "content": user_q})
        with st.chat_message("user"):
            st.markdown(user_q)

        try:
            answer = chatbot_answer(df, user_q)
        except Exception as e:
            answer = f"오류 발생: {e}"

        st.session_state["chat_history"].append({"role": "assistant", "content": answer})
        with st.chat_message("assistant"):
            st.markdown(answer)

    if st.button("🔙 처음으로"):
        st.session_state["page"] = "start"
        st.experimental_rerun()
