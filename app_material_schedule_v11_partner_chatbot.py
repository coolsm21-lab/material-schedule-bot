import os
import re
import pandas as pd
import streamlit as st
from datetime import datetime

st.set_page_config(page_title="🏷️ 자재일정 협력사 챗봇", layout="centered")
st.title("🏷️ 자재일정 협력사 챗봇")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

def lower_map(cols):
    return {str(c).strip().lower(): c for c in cols}

def pick_col(df, candidates):
    m = lower_map(df.columns)
    for c in candidates:
        key = str(c).strip().lower()
        if key in m:
            return m[key]
    for col in df.columns:
        lc = str(col).strip().lower()
        for c in candidates:
            if str(c).strip().lower() in lc:
                return col
    return None

def parse_korean_date(text):
    text = (text or "").strip()
    m = re.search(r'(\d{4})[./-](\d{1,2})[./-](\d{1,2})', text)
    if m:
        y, mo, d = map(int, m.groups())
        try:
            return datetime(y, mo, d).date()
        except Exception:
            pass
    m = re.search(r'(\d{1,2})[./-](\d{1,2})', text)
    if m:
        now = datetime.now()
        mo, d = map(int, m.groups())
        try:
            return datetime(now.year, mo, d).date()
        except Exception:
            pass
    m = re.search(r'(\d{1,2})\s*월\s*(\d{1,2})\s*일', text)
    if m:
        now = datetime.now()
        mo, d = map(int, m.groups())
        try:
            return datetime(now.year, mo, d).date()
        except Exception:
            pass
    return None

@st.cache_data(show_spinner=False)
def load_all_excel_merged(data_dir=DATA_DIR) -> pd.DataFrame:
    if not os.path.isdir(data_dir):
        raise FileNotFoundError(f"데이터 폴더가 없습니다: {data_dir}")
    xfiles = [f for f in os.listdir(data_dir) if f.lower().endswith('.xlsx')]
    if not xfiles:
        raise FileNotFoundError("엑셀 파일이 없습니다. /data 폴더에 .xlsx 파일을 업로드하세요.")
    latest = max([os.path.join(data_dir, f) for f in xfiles], key=os.path.getmtime)
    st.info(f"📂 불러온 파일: **{os.path.basename(latest)}**")

    all_sheets = pd.read_excel(latest, sheet_name=None, engine="openpyxl")
    merged = []
    for sname, sdf in all_sheets.items():
        sdf = sdf.copy()
        if sdf.shape[1] >= 2:
            code_col = sdf.columns[1]
        else:
            code_col = pick_col(sdf, ['업체코드','협력사코드','거래처코드','코드'])
        if code_col is not None and str(code_col) != '업체코드':
            if '업체코드' in sdf.columns:
                sdf.drop(columns=['업체코드'], inplace=True, errors='ignore')
            sdf.rename(columns={code_col: '업체코드'}, inplace=True)

        name_col = pick_col(sdf, ['업체명','협력사명','거래처명','고객명'])
        if name_col and str(name_col) != '업체명':
            if '업체명' in sdf.columns:
                sdf.drop(columns=['업체명'], inplace=True, errors='ignore')
            sdf.rename(columns={name_col: '업체명'}, inplace=True)

        qty_col = pick_col(sdf, ['수량','qty','수량합계'])
        if qty_col and str(qty_col) != '수량':
            if '수량' in sdf.columns:
                sdf.drop(columns=['수량'], inplace=True, errors='ignore')
            sdf.rename(columns={qty_col: '수량'}, inplace=True)
        if '수량' not in sdf.columns:
            sdf['수량'] = 0

        work_col = pick_col(sdf, ['작업일자','작업일','작업','완료일','작업완료'])
        if work_col and str(work_col) != '작업일자':
            if '작업일자' in sdf.columns:
                sdf.drop(columns=['작업일자'], inplace=True, errors='ignore')
            sdf.rename(columns={work_col: '작업일자'}, inplace=True)

        req_col = pick_col(sdf, ['요청일자','요청일','본사요청'])
        if req_col and str(req_col) != '요청일자':
            if '요청일자' in sdf.columns:
                sdf.drop(columns=['요청일자'], inplace=True, errors='ignore')
            sdf.rename(columns={req_col: '요청일자'}, inplace=True)

        recv_col = pick_col(sdf, ['인수일자','인수','인계','수령일자'])
        if recv_col and str(recv_col) != '인수일자':
            if '인수일자' in sdf.columns:
                sdf.drop(columns=['인수일자'], inplace=True, errors='ignore')
            sdf.rename(columns={recv_col: '인수일자'}, inplace=True)

        po_col = pick_col(sdf, ['발주번호','주문번호','po','발주'])
        if po_col and str(po_col) != '발주번호':
            if '발주번호' in sdf.columns:
                sdf.drop(columns=['발주번호'], inplace=True, errors='ignore')
            sdf.rename(columns={po_col: '발주번호'}, inplace=True)

        item_col = pick_col(sdf, ['아이템','품목','item','제품명'])
        if item_col and str(item_col) != '아이템':
            if '아이템' in sdf.columns:
                sdf.drop(columns=['아이템'], inplace=True, errors='ignore')
            sdf.rename(columns={item_col: '아이템'}, inplace=True)

        spec_col = pick_col(sdf, ['규격','스펙','규'])
        if spec_col and str(spec_col) != '규격':
            if '규격' in sdf.columns:
                sdf.drop(columns=['규격'], inplace=True, errors='ignore')
            sdf.rename(columns={spec_col: '규격'}, inplace=True)

        pkg_col = pick_col(sdf, ['package','포장','패키지'])
        if pkg_col and str(pkg_col) != 'PACKAGE':
            if 'PACKAGE' in sdf.columns:
                sdf.drop(columns=['PACKAGE'], inplace=True, errors='ignore')
            sdf.rename(columns={pkg_col: 'PACKAGE'}, inplace=True)

        if '업체코드' in sdf.columns:
            sdf['업체코드'] = sdf['업체코드'].astype(str).str.strip().str.lower()
        if '업체명' in sdf.columns:
            sdf['업체명'] = sdf['업체명'].astype(str).str.strip()
        if '수량' in sdf.columns:
            sdf['수량'] = pd.to_numeric(sdf['수량'], errors='coerce').fillna(0).astype(int)
        for c in ['작업일자','요청일자','인수일자']:
            if c in sdf.columns:
                sdf[c] = pd.to_datetime(sdf[c], errors='coerce').dt.date

        sdf['시트명'] = sname
        merged.append(sdf)

    df = pd.concat(merged, ignore_index=True)
    return df

def filter_company(df, code):
    code_norm = str(code).strip().lower()
    if '업체코드' not in df.columns:
        raise ValueError('업체코드 컬럼을 찾을 수 없습니다.')
    return df[df['업체코드'] == code_norm].copy()

def company_name(df):
    if '업체명' in df.columns and not df['업체명'].dropna().empty:
        return str(df['업체명'].dropna().iloc[0])
    return ''

def answer_query(df, q):
    q = (q or '').strip().lower()
    date = parse_korean_date(q)
    target_col = '작업일자'
    if '인수' in q:
        target_col = '인수일자'
    elif '요청' in q:
        target_col = '요청일자'

    df2 = df.copy()
    if target_col in df2.columns and date:
        df2 = df2[df2[target_col] == date]

    if ('작업' in q and ('되었' in q or '완료' in q)) or ('작업일자' in q):
        if target_col != '작업일자':
            target_col = '작업일자'
        if date:
            ok = not df2.empty
            cnt = int(df2['수량'].sum()) if '수량' in df2.columns else len(df2)
            return f"{date} 작업은 {'완료' if ok else '미완료'}입니다. 수량 {cnt:,}건.", df2
        else:
            last = df[df[target_col].notna()].sort_values(target_col).tail(1)
            if last.empty:
                return '작업 완료 이력이 없습니다.', df2
            dval = last[target_col].iloc[0]
            cnt = int(last['수량'].sum()) if '수량' in last.columns else len(last)
            return f'가장 최근 작업일자는 {dval}이며 수량 {cnt:,}건입니다.', last

    if '인수' in q and ('완료' in q or '되었' in q or '일자' in q):
        if target_col != '인수일자':
            target_col = '인수일자'
        if date:
            ok = not df2.empty
            cnt = int(df2['수량'].sum()) if '수량' in df2.columns else len(df2)
            return f"{date} 인수 {'완료' if ok else '미완료'}입니다. 수량 {cnt:,}건.", df2
        else:
            last = df[df[target_col].notna()].sort_values(target_col).tail(1)
            if last.empty:
                return '인수 완료 이력이 없습니다.', df2
            dval = last[target_col].iloc[0]
            cnt = int(last['수량'].sum()) if '수량' in last.columns else len(last)
            return f'가장 최근 인수일자는 {dval}이며 수량 {cnt:,}건입니다.', last

    if '수량' in q or '몇건' in q:
        total = int(df2['수량'].sum()) if '수량' in df2.columns else len(df2)
        msg = f"{date} 기준 수량은 총 {total:,}건입니다." if date else f"전체 수량 합계는 {total:,}건입니다."
        return msg, df2

    if '발주' in q or 'po' in q:
        return '발주번호 내역을 표로 보여드릴게요.', df2

    if '아이템' in q or '품목' in q:
        return '아이템 내역을 표로 보여드릴게요.', df2

    if 'package' in q or '포장' in q or '패키지' in q:
        return 'PACKAGE 내역을 표로 보여드릴게요.', df2

    if '브랜드' in q:
        return '브랜드 내역을 표로 보여드릴게요.', df2

    if '업체명' in q:
        nm = company_name(df)
        return (f'업체명은 {nm} 입니다.' if nm else '업체명을 찾지 못했습니다.'), df2

    if '내역' in q or '보여' in q or '표' in q:
        return '해당 조건의 내역을 표로 표시했습니다.', df2

    return "예) '11월 11일 수량', '작업되었어?', '인수완료?', '발주번호/아이템/PACKAGE 내역' 처럼 물어보면 돼요.", df2

# -----------------------------
# Page flow
# -----------------------------
if 'page' not in st.session_state:
    st.session_state['page'] = 'start'
if 'df_company' not in st.session_state:
    st.session_state['df_company'] = None
if 'company_name' not in st.session_state:
    st.session_state['company_name'] = ''

if st.session_state['page'] == 'start':
    st.subheader('🔹 협력업체 코드 입력 (B열 연동)')
    code = st.text_input('🏭 협력업체 코드', placeholder='예: A001 / B002 ...')
    if st.button('조회하기') and code:
        try:
            df_all = load_all_excel_merged()
            df_comp = filter_company(df_all, code)
            if df_comp.empty:
                st.error('해당 협력업체 코드 데이터가 없습니다.')
            else:
                st.session_state['df_company'] = df_comp
                st.session_state['company_name'] = company_name(df_comp)
                st.session_state['page'] = 'chat'
                st.rerun()
        except Exception as e:
            st.error(f'데이터 로드 오류: {e}')

elif st.session_state['page'] == 'chat':
    nm = st.session_state.get('company_name') or '(업체명 없음)'
    st.markdown(f'### 🏭 {nm} 협력사 전용 챗봇')

    dfc = st.session_state['df_company']
    cnt = len(dfc)
    qty = int(dfc['수량'].sum()) if '수량' in dfc.columns else cnt
    st.caption(f'총 행수: {cnt:,}  /  수량 합계: {qty:,}')

    if 'chat_history' not in st.session_state:
        st.session_state['chat_history'] = []
    for m in st.session_state['chat_history']:
        with st.chat_message(m['role']):
            st.markdown(m['content'])

    user_q = st.chat_input("예) '11월 11일 수량', '작업되었어?', '인수완료?', '발주번호/아이템/PACKAGE 내역'")
    if user_q:
        st.session_state['chat_history'].append({'role':'user','content':user_q})
        with st.chat_message('user'):
            st.markdown(user_q)
        try:
            msg, df_show = answer_query(dfc, user_q)
        except Exception as e:
            msg, df_show = (f'오류: {e}', pd.DataFrame())
        st.session_state['chat_history'].append({'role':'assistant','content':msg})
        with st.chat_message('assistant'):
            st.markdown(msg)
            # 표 요청이거나 필터된 결과가 있을 때 핵심 컬럼 테이블 표시
            if not df_show.empty:
                cols = [c for c in ['작업일자','요청일자','인수일자','발주번호','아이템','규격','수량','PACKAGE','브랜드','시트명'] if c in df_show.columns]
                if cols:
                    st.dataframe(df_show[cols].reset_index(drop=True), use_container_width=True)

    if st.button('🔙 처음으로'):
        st.session_state['page'] = 'start'
        st.rerun()