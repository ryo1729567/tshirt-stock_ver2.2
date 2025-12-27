import streamlit as st
import pandas as pd
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from datetime import datetime, timedelta
import json
import os
import io
import re
from pathlib import Path
import unicodedata

# --- 設定 ---
PAGE_TITLE = "Tシャツ＆タグ在庫管理システム"
PAGE_ICON = "👕"

# ページ設定
st.set_page_config(
    page_title=PAGE_TITLE,
    page_icon=PAGE_ICON,
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- カスタムCSS（iPad/スマホ対応） ---
st.markdown("""
<style>
    /* メインエリアの調整 */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 5rem;
    }
    /* ボタンのスタイル強化 */
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        height: 3.5em;
        font-weight: bold;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    /* 在庫入力フィールド */
    .stNumberInput input {
        text-align: center;
        font-size: 1.2rem;
    }
    /* タグ管理の現在の在庫数表示 */
    .big-number {
        font-size: 3rem;
        font-weight: bold;
        color: #0068c9;
        text-align: center;
        margin-bottom: 0;
    }
    .big-label {
        font-size: 1.2rem;
        text-align: center;
        color: #555;
    }
    /* Expanderのデザイン */
    div[data-testid="stExpander"] {
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        background-color: #ffffff;
        margin-bottom: 0.8rem;
    }
</style>
""", unsafe_allow_html=True)

# --- 定数・パス設定 ---
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
INVENTORY_FILE = DATA_DIR / "inventory_data.json"
RECORDS_FILE = DATA_DIR / "daily_records.json"
TAG_FILE = DATA_DIR / "tag_data.json"  # 新規: タグデータ用

TSHIRT_TYPES = [
    'パンクラス×禅道会コラボTシャツ(ホワイト)ゼンプロマークなし',
    'パンクラス×禅道会コラボTシャツ(ブラック)ゼンプロマークなし',
    'パンクラス×禅道会コラボTシャツ(ホワイト)ゼンプロマークあり',
    'パンクラス×禅道会コラボTシャツ(ブラック)ゼンプロマークあり'
]

SIZES = ['150cm', '160cm', 'S', 'M', 'L', 'XL', 'XXL']

# --- ロジッククラス ---
class InventoryManager:
    @staticmethod
    def load_inventory():
        if INVENTORY_FILE.exists():
            try:
                with open(INVENTORY_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {ttype: {size: 0 for size in SIZES} for ttype in TSHIRT_TYPES}
    
    @staticmethod
    def save_inventory(inventory):
        with open(INVENTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(inventory, f, ensure_ascii=False, indent=2)
    
    @staticmethod
    def load_records():
        if RECORDS_FILE.exists():
            try:
                with open(RECORDS_FILE, 'r', encoding='utf-8') as f:
                    records = json.load(f)
                    return sorted(records, key=lambda x: x['date'], reverse=True)
            except:
                pass
        return []
    
    @staticmethod
    def save_records(records):
        sorted_records = sorted(records, key=lambda x: x['date'], reverse=True)
        with open(RECORDS_FILE, 'w', encoding='utf-8') as f:
            json.dump(sorted_records, f, ensure_ascii=False, indent=2)

    # --- タグ管理用メソッド ---
    @staticmethod
    def load_tags():
        """タグデータを読み込む (在庫数と履歴)"""
        default_data = {"current_stock": 0, "history": []}
        if TAG_FILE.exists():
            try:
                with open(TAG_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 履歴を日付順(降順)にソート
                    if "history" in data:
                        data["history"] = sorted(data["history"], key=lambda x: x.get('timestamp', ''), reverse=True)
                    return data
            except:
                pass
        return default_data

    @staticmethod
    def save_tags(tag_data):
        """タグデータを保存"""
        with open(TAG_FILE, 'w', encoding='utf-8') as f:
            json.dump(tag_data, f, ensure_ascii=False, indent=2)

    @staticmethod
    def normalize_str(s):
        return unicodedata.normalize('NFC', s)

    @staticmethod
    def determine_type_from_filename(filename):
        base = InventoryManager.normalize_str(os.path.basename(filename))
        base = base.replace('（', '(').replace('）', ')')
        is_white = '白' in base or 'ホワイト' in base
        is_black = '黒' in base or 'ブラック' in base
        is_ari = 'あり' in base
        is_nasi = 'なし' in base
        
        if is_white and is_nasi: return 'パンクラス×禅道会コラボTシャツ(ホワイト)ゼンプロマークなし'
        elif is_white and is_ari: return 'パンクラス×禅道会コラボTシャツ(ホワイト)ゼンプロマークあり'
        elif is_black and is_nasi: return 'パンクラス×禅道会コラボTシャツ(ブラック)ゼンプロマークなし'
        elif is_black and is_ari: return 'パンクラス×禅道会コラボTシャツ(ブラック)ゼンプロマークあり'
        return None
    
    @staticmethod
    def normalize_size(cell_value):
        if cell_value is None: return None
        val = InventoryManager.normalize_str(str(cell_value)).strip()
        val = val.translate(str.maketrans({chr(0xFF01 + i): chr(0x21 + i) for i in range(94)}))
        if '150' in val: return '150cm'
        if '160' in val: return '160cm'
        if 'XXL' in val or '3L' in val: return 'XXL'
        if 'XL' in val or 'LL' in val: return 'XL'
        if 'L' in val: return 'L'
        if 'M' in val: return 'M'
        if 'S' in val: return 'S'
        return None
    
    @staticmethod
    def parse_excel_date(value):
        if value is None: return None
        if isinstance(value, datetime): return value.strftime('%Y-%m-%d')
        if isinstance(value, str):
            cleaned = value.strip().replace('/', '-')
            if re.match(r'^\d{4}-\d{1,2}-\d{1,2}$', cleaned):
                try: return pd.to_datetime(cleaned).strftime('%Y-%m-%d')
                except: pass
        return None

    @staticmethod
    def import_matrix_excel(uploaded_files):
        date_records = {}
        total_loaded = 0
        for uploaded_file in uploaded_files:
            target_type = InventoryManager.determine_type_from_filename(uploaded_file.name)
            if not target_type: continue
            try:
                wb = openpyxl.load_workbook(uploaded_file, data_only=True)
                ws = wb.active
                header_row_idx = None
                date_col_map = {}
                for r in range(1, 15):
                    row_values = [cell.value for cell in ws[r]]
                    if any(v and '商品名' in str(v) for v in row_values):
                        header_row_idx = r
                        for c_idx, val in enumerate(row_values):
                            d_str = InventoryManager.parse_excel_date(val)
                            if d_str: date_col_map[c_idx] = d_str
                        break
                if not header_row_idx or not date_col_map: continue
                for r in range(header_row_idx + 1, ws.max_row + 1):
                    row_values = [cell.value for cell in ws[r]]
                    if not row_values: continue
                    product_name = ""
                    if len(row_values) > 1 and row_values[1]: product_name = str(row_values[1])
                    elif row_values[0]: product_name = str(row_values[0])
                    size = InventoryManager.normalize_size(product_name)
                    if not size: continue
                    for c_idx, date_str in date_col_map.items():
                        if c_idx < len(row_values):
                            val = row_values[c_idx]
                            try: count = int(float(val)) if val is not None else 0
                            except: count = 0
                            if date_str not in date_records: date_records[date_str] = {}
                            if target_type not in date_records[date_str]: date_records[date_str][target_type] = {}
                            date_records[date_str][target_type][size] = count
                            total_loaded += 1
            except Exception as e:
                st.error(f"Error {uploaded_file.name}: {e}")
        return date_records, total_loaded

# --- セッション初期化 ---
def init_session_state():
    if 'inventory' not in st.session_state:
        st.session_state.inventory = InventoryManager.load_inventory()
    if 'records' not in st.session_state:
        st.session_state.records = InventoryManager.load_records()
    if 'tags' not in st.session_state:
        st.session_state.tags = InventoryManager.load_tags()
    if 'edit_mode' not in st.session_state:
        st.session_state.edit_mode = {}

# --- タブ1: Tシャツ在庫管理 ---
def inventory_tab():
    st.header("📦 Tシャツ在庫入力")
    today = datetime.now().strftime("%Y-%m-%d")
    
    last_record_date = st.session_state.records[0]['date'] if st.session_state.records else "なし"
    if last_record_date != today:
        st.warning(f"⚠️ 本日 ({today}) の記録がまだ保存されていません。（最終記録: {last_record_date}）")
    else:
        st.success(f"✅ 本日 ({today}) の記録は保存済みです。")

    col_act1, col_act2 = st.columns(2)
    with col_act1:
        if st.button("💾 本日の記録を保存/更新", type="primary", use_container_width=True):
            save_daily_record()
    with col_act2:
        if st.button("📤 Tシャツ在庫をExcelでDL", use_container_width=True):
            export_current_excel()

    st.markdown("---")
    with st.expander("📥 過去データをExcelから一括インポート"):
        uploaded_files = st.file_uploader("Excelファイルをドラッグ&ドロップ", type=['xlsx', 'xls'], accept_multiple_files=True)
        if uploaded_files:
            import_excel_data(uploaded_files)

    st.markdown("### 在庫数入力")
    for ttype in TSHIRT_TYPES:
        display_name = ttype.replace('パンクラス×禅道会コラボTシャツ', '').replace('ゼンプロマーク', 'マーク')
        with st.container():
            st.markdown(f"**{display_name}**")
            cols = st.columns(len(SIZES))
            for idx, size in enumerate(SIZES):
                with cols[idx]:
                    current_val = st.session_state.inventory.get(ttype, {}).get(size, 0)
                    new_val = st.number_input(f"{size}", min_value=0, value=current_val, step=1, key=f"inv_{ttype}_{size}")
                    if new_val != current_val:
                        st.session_state.inventory[ttype][size] = new_val
                        InventoryManager.save_inventory(st.session_state.inventory)
                    
                    c_minus, c_plus = st.columns(2)
                    if c_minus.button("－", key=f"m_{ttype}_{size}"):
                        st.session_state.inventory[ttype][size] = max(0, current_val - 1)
                        InventoryManager.save_inventory(st.session_state.inventory)
                        st.rerun()
                    if c_plus.button("＋", key=f"p_{ttype}_{size}"):
                        st.session_state.inventory[ttype][size] = current_val + 1
                        InventoryManager.save_inventory(st.session_state.inventory)
                        st.rerun()
            st.markdown("---")

def save_daily_record():
    today = datetime.now().strftime("%Y-%m-%d")
    existing_idx = None
    for idx, record in enumerate(st.session_state.records):
        if record['date'] == today:
            existing_idx = idx
            break
    new_record = {
        'date': today,
        'timestamp': datetime.now().isoformat(),
        'inventory': json.loads(json.dumps(st.session_state.inventory)),
        'note': '手動保存'
    }
    if existing_idx is not None:
        st.session_state.records[existing_idx] = new_record
        st.toast(f"✅ {today}の記録を更新しました")
    else:
        st.session_state.records.insert(0, new_record)
        st.toast(f"✅ {today}の記録を新規保存しました")
    InventoryManager.save_records(st.session_state.records)
    st.rerun()

def import_excel_data(uploaded_files):
    date_records, total_loaded = InventoryManager.import_matrix_excel(uploaded_files)
    if date_records:
        existing_map = {r['date']: r for r in st.session_state.records}
        for date_str, type_data in date_records.items():
            if date_str in existing_map:
                record = existing_map[date_str]
                for ttype, sizes in type_data.items():
                    if ttype not in record['inventory']: record['inventory'][ttype] = {s: 0 for s in SIZES}
                    for s, count in sizes.items(): record['inventory'][ttype][s] = count
            else:
                new_inventory = {t: {s: 0 for s in SIZES} for t in TSHIRT_TYPES}
                for ttype, sizes in type_data.items():
                    for s, count in sizes.items(): new_inventory[ttype][s] = count
                new_record = {'date': date_str, 'timestamp': f"{date_str}T12:00:00", 'inventory': new_inventory, 'note': 'Excel自動取込'}
                st.session_state.records.append(new_record)
        InventoryManager.save_records(st.session_state.records)
        st.success(f"✅ インポート完了: {len(date_records)}日分のデータを処理しました。")
        st.rerun()
    else:
        st.error("⚠️ データが見つかりませんでした。")

def export_current_excel():
    output = io.BytesIO()
    wb = openpyxl.Workbook()
    for i, ttype in enumerate(TSHIRT_TYPES):
        safe_title = ttype[:30].replace('/', '_')
        if i == 0: ws = wb.active; ws.title = safe_title
        else: ws = wb.create_sheet(title=safe_title)
        ws.append(['サイズ', '在庫数'])
        for j, size in enumerate(SIZES):
            ws.cell(row=j+2, column=1, value=size)
            ws.cell(row=j+2, column=2, value=st.session_state.inventory[ttype].get(size, 0))
    wb.save(output)
    output.seek(0)
    st.download_button("📥 Excelダウンロード", output, f"在庫_{datetime.now().strftime('%Y%m%d')}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# --- タブ2: タグ管理 (修正版) ---
def tags_tab():
    st.header("🏷️ タグ（衣服）在庫管理")
    
    # 現在の在庫表示
    current_stock = st.session_state.tags.get("current_stock", 0)
    
    st.markdown("<div class='big-label'>現在の在庫数</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='big-number'>{current_stock:,} 枚</div>", unsafe_allow_html=True)
    st.markdown("---")

    # アクション入力
    st.subheader("📝 在庫の更新（使用・入荷・不良）")
    st.caption("※ タグを使用した日、または入荷した際にここから入力してください。")

    with st.form("tag_action_form", clear_on_submit=True):
        col1, col2 = st.columns([1, 2])
        with col1:
            action_type = st.radio("区分", ["使用 (－)", "入荷・追加 (＋)", "不良 (－)"], horizontal=False)
        with col2:
            # 修正: value=0 -> value=1 に変更 (min_value=1のため)
            amount = st.number_input("数量 (枚)", min_value=1, step=1, value=1)
            note = st.text_input("備考 (任意)", placeholder="例: 12月分受注, 追加発注分など")
        
        submitted = st.form_submit_button("更新を記録する", use_container_width=True)
        
        if submitted and amount > 0:
            update_tag_stock(action_type, amount, note)
    
    st.markdown("---")
    
    # 履歴表示
    st.subheader("📜 更新履歴")
    history = st.session_state.tags.get("history", [])
    if history:
        df_hist = pd.DataFrame(history)
        st.dataframe(df_hist, use_container_width=True)
    else:
        st.info("まだ履歴がありません。")

def update_tag_stock(action_type, amount, note):
    """タグの在庫を更新し履歴に追加"""
    current_stock = st.session_state.tags.get("current_stock", 0)
    
    if "使用" in action_type:
        new_stock = current_stock - amount
        act_label = "使用"
    elif "入荷" in action_type:
        new_stock = current_stock + amount
        act_label = "入荷"
    elif "不良" in action_type:
        new_stock = current_stock - amount
        act_label = "不良"
    
    # 在庫がマイナスになる場合の警告（記録は許可する）
    if new_stock < 0:
        st.warning("⚠️ 在庫数がマイナスになります。")

    # データ更新
    new_entry = {
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "date": datetime.now().strftime('%Y-%m-%d'),
        "action": act_label,
        "amount": amount,
        "stock_after": new_stock,
        "note": note
    }
    
    st.session_state.tags["current_stock"] = new_stock
    st.session_state.tags["history"].insert(0, new_entry) # 先頭に追加
    
    InventoryManager.save_tags(st.session_state.tags)
    st.success(f"✅ {act_label} {amount}枚 を記録しました。（現在庫: {new_stock}枚）")
    st.rerun()

# --- タブ3: Tシャツ日次記録 ---
def records_tab():
    st.header("📊 Tシャツ日次記録")
    with st.expander("🔎 期間で絞り込み", expanded=False):
        c1, c2 = st.columns(2)
        start_date = c1.date_input("開始", value=datetime.now() - timedelta(days=60))
        end_date = c2.date_input("終了", value=datetime.now())
    
    c_csv, c_xls = st.columns(2)
    with c_csv:
        if st.button("📊 CSVダウンロード", use_container_width=True): export_records('csv', start_date, end_date)
    with c_xls:
        if st.button("📈 Excelダウンロード", use_container_width=True): export_records('excel', start_date, end_date)
    st.divider()

    records = st.session_state.records
    if not records:
        st.info("データがありません。")
        return

    for i, record in enumerate(records):
        d_str = record['date']
        if not (start_date <= datetime.strptime(d_str, '%Y-%m-%d').date() <= end_date): continue
        note = record.get('note', '')
        with st.expander(f"📅 {d_str} {f'({note})' if note else ''}"):
            is_editing = st.session_state.edit_mode.get(d_str, False)
            c_info, c_edit, c_del = st.columns([6, 2, 2])
            with c_edit:
                if st.button("✏️ 編集", key=f"btn_edit_{d_str}"):
                    st.session_state.edit_mode[d_str] = not is_editing
                    st.rerun()
            with c_del:
                if st.button("🗑️ 削除", key=f"btn_del_{d_str}", type="primary"):
                    st.session_state.records.pop(i)
                    InventoryManager.save_records(st.session_state.records)
                    st.rerun()
            
            if is_editing:
                st.info("📝 編集中...")
                edited_inv = record['inventory'].copy()
                for ttype in TSHIRT_TYPES:
                    st.caption(f"**{ttype}**")
                    cols = st.columns(len(SIZES))
                    for idx, size in enumerate(SIZES):
                        key = f"e_{d_str}_{ttype}_{size}"
                        old_val = edited_inv.get(ttype, {}).get(size, 0)
                        edited_inv[ttype][size] = cols[idx].number_input(size, value=old_val, min_value=0, key=key, label_visibility="collapsed")
                if st.button("💾 保存", key=f"save_{d_str}"):
                    record['inventory'] = edited_inv
                    InventoryManager.save_records(st.session_state.records)
                    st.session_state.edit_mode[d_str] = False
                    st.rerun()
            else:
                st.dataframe(pd.DataFrame([{"種類": t.replace('パンクラス×禅道会コラボTシャツ', ''), **inv} for t, inv in record['inventory'].items()]).set_index("種類"))

def export_records(fmt, start, end):
    records = st.session_state.records
    data = []
    for r in records:
        d = r['date']
        if not (start <= datetime.strptime(d, '%Y-%m-%d').date() <= end): continue
        for ttype in TSHIRT_TYPES:
            for size in SIZES:
                data.append({"日付": d, "種類": ttype, "サイズ": size, "在庫数": r['inventory'].get(ttype, {}).get(size, 0)})
    df = pd.DataFrame(data)
    if df.empty:
        st.warning("対象データなし")
        return
    if fmt == 'csv':
        st.download_button("CSV DL", df.to_csv(index=False).encode('utf-8-sig'), "records.csv", "text/csv")
    else:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.pivot_table(index=['種類', 'サイズ'], columns='日付', values='在庫数', fill_value=0).to_excel(writer, sheet_name="日次推移")
        output.seek(0)
        st.download_button("Excel DL", output, "records.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# --- タブ4: データ管理 ---
def settings_tab():
    st.header("⚙️ データ管理")
    st.warning("クラウド版（Web）では再起動でデータが消えるため、定期的にバックアップをDLしてください。")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📤 バックアップ")
        # タグデータも含める
        full_data = {
            'inventory': st.session_state.inventory,
            'records': st.session_state.records,
            'tags': st.session_state.tags,
            'saved_at': datetime.now().isoformat()
        }
        json_str = json.dumps(full_data, ensure_ascii=False, indent=2)
        st.download_button("📦 全データをバックアップ", json_str, f"backup_{datetime.now().strftime('%Y%m%d')}.json", "application/json", type="primary")

    with col2:
        st.subheader("📥 データ復元")
        uploaded = st.file_uploader("バックアップファイル (.json)", type=['json'])
        if uploaded:
            try:
                data = json.load(uploaded)
                # Tシャツデータ
                if 'inventory' in data: st.session_state.inventory = data['inventory']
                if 'records' in data: st.session_state.records = data['records']
                # タグデータ
                if 'tags' in data: st.session_state.tags = data['tags']
                
                # ファイル保存
                InventoryManager.save_inventory(st.session_state.inventory)
                InventoryManager.save_records(st.session_state.records)
                InventoryManager.save_tags(st.session_state.tags)
                
                st.success("✅ データを復元しました！")
                if st.button("更新を反映"): st.rerun()
            except Exception as e:
                st.error(f"復元失敗: {e}")

# --- タブ5: マニュアル (新規) ---
def manual_tab():
    st.header("📖 システム操作マニュアル")
    st.markdown("""
    このシステムは、**「Tシャツ」**と**「タグ」**の在庫を管理し、記録を残すためのツールです。
    データが消えないよう、以下の手順に従って操作してください。
    """)

    with st.expander("1. Tシャツの在庫管理（毎日実施）", expanded=True):
        st.markdown("""
        **【概要】**
        * 毎日、その時点でのTシャツ在庫数を入力し、保存します。
        
        **【手順】**
        1.  **「📦 Tシャツ在庫」**タブを開きます。
        2.  各Tシャツのサイズごとに、現在の在庫数を入力します（＋－ボタンも使えます）。
        3.  入力が終わったら、画面上部の**「💾 本日の記録を保存/更新」**ボタンを押します。
        4.  画面右上に「✅ 保存しました」と表示されれば完了です。
        
        **【注意】**
        * 保存ボタンを押さないと、その日の記録は残りません。
        * Excelから一括で取り込みたい場合は「過去データをExcelから一括インポート」を使用してください。
        """)

    with st.expander("2. タグ（衣服）の在庫管理（使用・入荷時のみ）", expanded=True):
        st.markdown("""
        **【概要】**
        * タグを使用した日や、新しいタグが入荷した時に記録します。
        * 日々の入力は不要です。アクションがあった時だけ操作してください。
        
        **【手順】**
        1.  **「🏷️ タグ管理」**タブを開きます。
        2.  フォームで**「使用」「入荷」「不良」**のいずれかを選択します。
        3.  枚数を入力し、必要であれば備考（「〇月分受注」など）を記入します。
        4.  **「更新を記録する」**ボタンを押します。
        5.  在庫数が自動計算され、下の履歴表に行が追加されます。
        """)

    with st.expander("3. データの修正・確認", expanded=True):
        st.markdown("""
        * **Tシャツの履歴:** 「📊 Tシャツ記録」タブで過去の記録を確認できます。「✏️ 編集」ボタンで後から数値を修正したり、「🗑️ 削除」で間違った日の記録を消すことができます。
        * **データの出力:** 各タブにある「Excelダウンロード」等のボタンから、報告用のファイルを作成できます。
        """)

    with st.expander("4. 【重要】データのバックアップと復元", expanded=True):
        st.warning("⚠️ この作業は非常に重要です")
        st.markdown("""
        このシステムはWeb上で動作しているため、**長時間放置したりページを閉じたりすると、入力したデータがリセットされる場合があります。**
        
        **【作業終了時】**
        1.  **「⚙️ データ管理」**タブを開きます。
        2.  **「📦 全データをバックアップ」**ボタンを押し、ファイルをPCやiPadに保存してください。
        
        **【作業開始時（データが消えていた場合）】**
        1.  **「⚙️ データ管理」**タブを開きます。
        2.  「📥 データ復元」に、前回保存したファイルをアップロードします。
        3.  データが元の状態に戻ります。
        """)

# --- メイン処理 ---
def main():
    init_session_state()
    st.title(PAGE_TITLE)
    
    # タブ構成
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📦 Tシャツ在庫", 
        "🏷️ タグ管理", 
        "📊 Tシャツ記録", 
        "⚙️ データ管理",
        "📖 マニュアル"
    ])
    
    with tab1: inventory_tab()
    with tab2: tags_tab()
    with tab3: records_tab()
    with tab4: settings_tab()
    with tab5: manual_tab()

if __name__ == "__main__":
    main()
