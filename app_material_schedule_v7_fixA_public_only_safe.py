import os
import io
import platform
import pandas as pd
import streamlit as st

st.set_page_config(page_title="🏷️ 자재일정 조회 시스템 (협력사용 전용/안전모드)", layout="centered")
st.title("🏷️ 자재일정 조회 시스템 (협력사용 전용/안전모드)")

# ===== 경로 및 버전 디버그 =====
APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(APP_DIR, "data")
DATA_PATH = os.path.join(DATA_DIR, "material_schedule.xlsx")

st.caption("GitHub의 /data/material_schedule.xlsx 를 읽어옵니다. 없으면 여기서 1회 등록할 수 있어요.")

with st.expander("🔧 디버그 정보", expanded=False):
    st.write("Python:", platform.python_version())
    try:
        import streamlit, pandas, openpyxl
        st.write("Streamlit:", streamlit.__version__)
        st.write("Pandas:", pandas.__version__)
        st.write("openpyxl:", openpyxl.__version__)
    except Exception as e:
        st.write("버전 확인 중 오류:", e)
    st.write("실행 폴더(APP_DIR):", APP_DIR)
    st.write("데이터 폴더(DATA_DIR):", DATA_DIR, "— 존재:", os.path.isdir(DATA_DIR))
    st.write("엑셀 경로(DATA_PATH):", DATA_PATH, "— 존재:", os.path.isfile(DATA_PATH))

# ===== 데이터 로더 =====
@st.cache_data(show_spinner=False)
def load_excel(path: str) -> pd.DataFrame:
    df = pd.read_excel(path, engine="openpyxl")
    return df

# ===== 데이터 확보 (없으면 한 번만 업로드 허용) =====
if not os.path.isdir(DATA_DIR):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
    except Exception as e:
        st.error(f"데이터 폴더 생성 실패: {e}")

if not os.path.isfile(DATA_PATH):
    st.warning("GitHub의 /data/material_schedule.xlsx 파일이 없습니다.")
    up = st.file_uploader("여기에 material_schedule.xlsx 업로드 (1회 저장용)", type=["xlsx"])
    if up is not None:
        if st.button("⬆️ 업로드 파일을 /data/material_schedule.xlsx 로 저장"):
            try:
                with open(DATA_PATH, "wb") as f:
                    f.write(up.read())
                st.success("저장 완료! 이제 아래에서 조회해 보세요.")
                st.rerun()
            except Exception as e:
                st.error(f"저장 실패: {e}")

# ===== 협력사용 조회 UI =====
st.subheader("🔍 협력업체 자재일정 조회")
company_code = st.text_input("🏭 협력사 코드 입력 (예: A001)", placeholder="A001 / B015 ...")
find_btn = st.button("바로 조회")

if company_code and find_btn:
    if not os.path.isfile(DATA_PATH):
        st.error("데이터 파일이 아직 없습니다. /data/material_schedule.xlsx 를 GitHub에 올리거나 위에서 업로드해 주세요.")
    else:
        try:
            df = load_excel(DATA_PATH)
        except Exception as e:
            st.error(f"엑셀을 불러오는 중 오류: {e}")
        else:
            required = {"업체코드", "업체명"}
            if not required.issubset(set(map(str, df.columns))):
                st.error(f"엑셀에 필수 컬럼이 없습니다. 필요 컬럼: {sorted(required)} / 현재 컬럼: {list(df.columns)}")
            else:
                norm = lambda s: str(s).strip().lower()
                filtered = df[df["업체코드"].astype(str).map(norm) == norm(company_code)]
                if filtered.empty:
                    st.error("❌ 등록되지 않은 업체코드거나 데이터가 없습니다.")
                else:
                    st.success(f"✅ {filtered.iloc[0]['업체명']} — {len(filtered)}건")
                    st.dataframe(filtered.reset_index(drop=True), use_container_width=True)
                    st.info("※ 본 화면은 GitHub /data/material_schedule.xlsx 기준으로 표시됩니다.")
