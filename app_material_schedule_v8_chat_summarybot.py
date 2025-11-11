import os
import pandas as pd
import numpy as np
import streamlit as st
from datetime import datetime, timedelta

# ================================
# 기본 설정
# ================================
st.set_page_config(page_title="🏷️ 자재일정 요약봇 (협력사용)", layout="centered")
st.title("🏷️ 자재일정 요약봇 (협력사용 전용)")

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(APP_DIR, "data", "material_schedule.xlsx")

# ================================
# 유틸: 컬럼 자동 매핑
# ================================
def pick_col(df, candidates):
    cols = {str(c).strip().lower(): c for c in df.columns}
    for cand in candidates:
        key = str(cand).strip().lower()
        if key in cols:
            return cols[key]
    # 부분일치(초간단 fallback)
    for c in df.columns:
        lc = str(c).strip().lower()
        for cand in candidates:
            if cand in lc:
                return c
    return None

# ================================
# 데이터 로드
# ================================
@st.cache_data(show_spinner=False)
def load_df(path):
    df = pd.read_excel(path, engine="openpyxl")
    return df

def ensure_schema(df):
    # 날짜/수량/구분/업체코드/업체명 추론
    date_col = pick_col(df, ["날짜", "일자", "date"])
    qty_col = pick_col(df, ["수량", "qty", "수량합계"])
    type_col = pick_col(df, ["구분", "유형", "type", "작업유형"])
    code_col = pick_col(df, ["업체코드", "협력사코드", "code"])
    name_col = pick_col(df, ["업체명", "협력사명", "name"])

    missing = []
    if date_col is None: missing.append("날짜/일자(date)")
    if qty_col is None: missing.append("수량(qty)")
    if code_col is None: missing.append("업체코드(code)")
    # type_col, name_col은 선택

    return {
        "date": date_col,
        "qty": qty_col,
        "type": type_col,
        "code": code_col,
        "name": name_col,
        "missing": missing
    }

def normalize(df, schema):
    d = df.copy()
    # 날짜 파싱
    d[schema["date"]] = pd.to_datetime(d[schema["date"]], errors="coerce")
    # 수량 숫자화
    d[schema["qty"]] = pd.to_numeric(d[schema["qty"]], errors="coerce").fillna(0)
    # 구분 소문자 정리
    if schema["type"]:
        d[schema["type"]] = d[schema["type"]].astype(str).str.strip().str.lower()
    # 코드 정리
    d[schema["code"]] = d[schema["code"]].astype(str).str.strip().str.lower()
    return d

# ================================
# 질의 파서
# ================================
TIME_KEYWORDS = {
    "오늘": "today", "금일": "today",
    "어제": "yesterday",
    "이번주": "this_week", "금주": "this_week",
    "지난주": "last_week", "전주": "last_week",
    "이번달": "this_month", "금월": "this_month",
    "지난달": "last_month", "전월": "last_month",
    "올해": "this_year", "금년": "this_year",
    "작년": "last_year"
}

TYPE_KEYWORDS = {
    "입고": "inbound",
    "출고": "outbound",
    "반품": "return",
    "전체": "all",
    "합계": "all",
}

def parse_query(q):
    q = (q or "").strip().lower()
    # 기간 파악
    time_key = None
    for k, v in TIME_KEYWORDS.items():
        if k in q:
            time_key = v
            break
    # 유형 파악
    act_key = None
    for k, v in TYPE_KEYWORDS.items():
        if k in q:
            act_key = v
            break
    # 기본값
    if time_key is None:
        time_key = "today"
    if act_key is None:
        # 질문에 '수량'만 있을 때는 전체로
        act_key = "all"
    return time_key, act_key

def compute_period(ref, mode):
    # ref: datetime.date
    # mode: today/yesterday/this_week/last_week/this_month/last_month/this_year/last_year
    if mode == "today":
        start = ref
        end = ref
        prev_start = ref - timedelta(days=1)
        prev_end = prev_start
    elif mode == "yesterday":
        start = ref - timedelta(days=1)
        end = start
        prev_start = start - timedelta(days=1)
        prev_end = prev_start
    elif mode == "this_week":
        # 월요일=0
        start = ref - timedelta(days=ref.weekday())
        end = ref
        prev_end = start - timedelta(days=1)
        prev_start = prev_end - timedelta(days=prev_end.weekday())
    elif mode == "last_week":
        end = ref - timedelta(days=ref.weekday()+1)
        start = end - timedelta(days=6)
        prev_end = start - timedelta(days=1)
        prev_start = prev_end - timedelta(days=6)
    elif mode == "this_month":
        start = ref.replace(day=1)
        end = ref
        prev_end = start - timedelta(days=1)
        prev_start = prev_end.replace(day=1)
    elif mode == "last_month":
        this_month_start = ref.replace(day=1)
        prev_end = this_month_start - timedelta(days=1)
        prev_start = prev_end.replace(day=1)
        start, end = prev_start, prev_end
    elif mode == "this_year":
        start = ref.replace(month=1, day=1)
        end = ref
        prev_end = start.replace(year=start.year-1).replace(month=12, day=31)
        prev_start = prev_end.replace(month=1, day=1)
    elif mode == "last_year":
        prev_end = ref.replace(month=12, day=31, year=ref.year-1)
        prev_start = prev_end.replace(month=1, day=1)
        start, end = prev_start, prev_end
    else:
        start = end = ref
        prev_start = ref - timedelta(days=1)
        prev_end = prev_start
    return start, end, prev_start, prev_end

def filter_period(d, date_col, start, end):
    m = (d[date_col].dt.date >= start) & (d[date_col].dt.date <= end)
    return d.loc[m]

def agg_qty(df, qty_col, type_col, act_key):
    if type_col is None or act_key == "all":
        return float(df[qty_col].sum())
    # map inbound/outbound/return to string matching
    # 허용 라벨
    inbound_keys = ["입고", "inbound"]
    outbound_keys = ["출고", "outbound"]
    return_keys = ["반품", "return"]
    col = df[type_col].astype(str).str.lower()
    if act_key == "inbound":
        m = False
        for k in inbound_keys:
            m = m | col.str.contains(k)
        return float(df.loc[m, qty_col].sum())
    if act_key == "outbound":
        m = False
        for k in outbound_keys:
            m = m | col.str.contains(k)
        return float(df.loc[m, qty_col].sum())
    if act_key == "return":
        m = False
        for k in return_keys:
            m = m | col.str.contains(k)
        return float(df.loc[m, qty_col].sum())
    return float(df[qty_col].sum())

def fmt_num(x):
    try:
        return f"{int(x):,}"
    except Exception:
        return f"{x:,.0f}"

def reply_sentence(company, period_txt, act_txt, cur, prev):
    diff = cur - prev
    pct = 0 if prev == 0 else (diff/prev*100.0)
    sign = "증가" if diff > 0 else ("감소" if diff < 0 else "변동 없음")
    return f"{company}의 {period_txt} {act_txt} 수량은 **{fmt_num(cur)}건**이며, 전기간 대비 {sign}({fmt_num(abs(diff))}건, {pct:.1f}%)입니다."

def period_text(mode, start, end):
    if start == end:
        return f"{start.strftime('%Y-%m-%d')}"
    # 요약 표현
    labels = {
        "today": "오늘",
        "yesterday": "어제",
        "this_week": "이번주",
        "last_week": "지난주",
        "this_month": "이번달",
        "last_month": "지난달",
        "this_year": "올해",
        "last_year": "작년",
    }
    base = labels.get(mode, f"{start:%Y-%m-%d}~{end:%Y-%m-%d}")
    return f"{base}({start:%Y-%m-%d} ~ {end:%Y-%m-%d})"

def act_text(act_key):
    mapping = {
        "inbound": "입고",
        "outbound": "출고",
        "return": "반품",
        "all": "전체",
    }
    return mapping.get(act_key, "전체")

# ================================
# UI — 협력사 코드 입력
# ================================
st.subheader("🔍 협력사 질의응답")
st.caption("GitHub `/data/material_schedule.xlsx` 기준. 협력사 코드를 먼저 입력하세요.")

code_in = st.text_input("🏭 협력사 코드", placeholder="A001 / B015 ...")
ask = st.chat_input("예) 오늘 출고는? 이번주 입고 합계 보여줘")

if "messages" not in st.session_state:
    st.session_state["messages"] = []

def add_msg(role, content):
    st.session_state["messages"].append({"role": role, "content": content})

# 과거 대화 렌더
for m in st.session_state["messages"]:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# ================================
# 데이터 존재 확인
# ================================
if not os.path.isfile(DATA_PATH):
    st.warning("`/data/material_schedule.xlsx` 파일이 없습니다. GitHub에 업로드해 주세요.")
else:
    df = load_df(DATA_PATH)
    schema = ensure_schema(df)
    if schema["missing"]:
        st.error("필수 컬럼 누락: " + ", ".join(schema["missing"]))
        st.stop()
    d = normalize(df, schema)

    if code_in:
        # 해당 협력사만
        sub = d[d[schema["code"]] == code_in.strip().lower()].copy()
        if sub.empty:
            st.info("해당 협력사 코드 데이터가 없습니다.")
        else:
            # 기본 요약 카드
            today = datetime.now().date()
            s_today, e_today, ps, pe = compute_period(today, "today")
            cur_today = agg_qty(filter_period(sub, schema["date"], s_today, e_today), schema["qty"], schema["type"], "all")
            cur_week = agg_qty(filter_period(sub, schema["date"], *compute_period(today, "this_week")[:2]), schema["qty"], schema["type"], "all")
            cur_month = agg_qty(filter_period(sub, schema["date"], *compute_period(today, "this_month")[:2]), schema["qty"], schema["type"], "all")
            # 카드 표시
            c1, c2, c3 = st.columns(3)
            c1.metric("오늘 합계", fmt_num(cur_today))
            c2.metric("이번주 합계", fmt_num(cur_week))
            c3.metric("이번달 합계", fmt_num(cur_month))

            if ask:
                # 사용자 입력 대화 표시
                add_msg("user", ask)
                with st.chat_message("user"):
                    st.markdown(ask)

                # 파싱 후 답변 생성
                tkey, akey = parse_query(ask)
                start, end, pstart, pend = compute_period(datetime.now().date(), tkey)
                cur_df = filter_period(sub, schema["date"], start, end)
                prev_df = filter_period(sub, schema["date"], pstart, pend)

                cur_val = agg_qty(cur_df, schema["qty"], schema["type"], akey)
                prev_val = agg_qty(prev_df, schema["qty"], schema["type"], akey)

                pt = period_text(tkey, start, end)
                at = act_text(akey)
                ans = reply_sentence(code_in.upper(), pt, at, cur_val, prev_val)

                with st.chat_message("assistant"):
                    st.markdown(ans)

                add_msg("assistant", ans)
