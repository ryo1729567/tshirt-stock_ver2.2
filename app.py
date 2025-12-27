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

# ページ設定
st.set_page_config(
    page_title="Tシャツ在庫管理システム",
    page_icon="👕",
    layout="wide",
    initial_sidebar_state="expanded"
)

# カスタムCSS（タブレット・PC対応）
st.markdown("""
<style>
    .main {
        padding: 1rem;
    }
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        height: 3em;
        font-weight: bold;
    }
    .inventory-input {
        font-size: 1.2em;
        text-align: center;
    }
    @media (max-width: 768px) {
        .stColumn {
            padding: 0.5rem;
        }
    }
    div[data-testid="stExpander"] {
        border: 1px solid #ddd;
        border-radius: 5px;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# データファイルパス
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
INVENTORY_FILE = DATA_DIR / "inventory_data.json"
RECORDS_FILE = DATA_DIR / "daily_records.json"

# Tシャツの種類
TSHIRT_TYPES = [
    'パンクラス×禅道会コラボTシャツ(ホワイト)ゼンプロマークなし',
    'パンクラス×禅道会コラボTシャツ(ブラック)ゼンプロマークなし',
    'パンクラス×禅道会コラボTシャツ(ホワイト)ゼンプロマークあり',
    'パンクラス×禅道会コラボTシャツ(ブラック)ゼンプロマークあり'
]

# サイズ
SIZES = ['150cm', '160cm', 'S', 'M', 'L', 'XL', 'XXL']

class InventoryManager:
    @staticmethod
    def load_inventory():
        """在庫データを読み込む"""
        if INVENTORY_FILE.exists():
            try:
                with open(INVENTORY_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {ttype: {size: 0 for size in SIZES} for ttype in TSHIRT_TYPES}
    
    @staticmethod
    def save_inventory(inventory):
        """在庫データを保存"""
        with open(INVENTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(inventory, f, ensure_ascii=False, indent=2)
    
    @staticmethod
    def load_records():
        """日次記録を読み込む"""
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
        """日次記録を保存"""
        sorted_records = sorted(records, key=lambda x: x['date'], reverse=True)
        with open(RECORDS_FILE, 'w', encoding='utf-8') as f:
            json.dump(sorted_records, f, ensure_ascii=False, indent=2)
    
    @staticmethod
    def determine_type_from_filename(filename):
        """ファイル名からTシャツタイプを判定"""
        base = os.path.basename(filename)
        base = base.replace('（', '(').replace('）', ')')
        
        is_white = '白' in base or 'ホワイト' in base
        is_black = '黒' in base or 'ブラック' in base
        is_ari = 'あり' in base
        is_nasi = 'なし' in base
        
        if is_white and is_nasi:
            return 'パンクラス×禅道会コラボTシャツ(ホワイト)ゼンプロマークなし'
        elif is_white and is_ari:
            return 'パンクラス×禅道会コラボTシャツ(ホワイト)ゼンプロマークあり'
        elif is_black and is_nasi:
            return 'パンクラス×禅道会コラボTシャツ(ブラック)ゼンプロマークなし'
        elif is_black and is_ari:
            return 'パンクラス×禅道会コラボTシャツ(ブラック)ゼンプロマークあり'
        return None
    
    @staticmethod
    def normalize_size(cell_value):
        """セル値からサイズを抽出"""
        val = str(cell_value).strip()
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
        """Excel日付をYYYY-MM-DD形式に変換"""
        if isinstance(value, datetime):
            return value.strftime('%Y-%m-%d')
        if isinstance(value, str):
            if re.match(r'^\d{4}[-/]\d{1,2}[-/]\d{1,2}$', value.strip()):
                try:
                    return pd.to_datetime(value).strftime('%Y-%m-%d')
                except:
                    pass
        return None
    
    @staticmethod
    def import_matrix_excel(uploaded_files):
        """マトリクス形式のExcelファイルをインポート"""
        date_records = {}
        total_loaded = 0
        
        for uploaded_file in uploaded_files:
            target_type = InventoryManager.determine_type_from_filename(uploaded_file.name)
            if not target_type:
                continue
            
            try:
                wb = openpyxl.load_workbook(uploaded_file, data_only=True)
                ws = wb.active
                
                # ヘッダー行を探す
                header_row_idx = None
                date_col_map = {}
                
                for r in range(1, 10):
                    row_values = [cell.value for cell in ws[r]]
                    if any('商品名' in str(v) for v in row_values if v):
                        header_row_idx = r
                        for c_idx, val in enumerate(row_values):
                            d_str = InventoryManager.parse_excel_date(val)
                            if d_str:
                                date_col_map[c_idx] = d_str
                        break
                
                if not header_row_idx or not date_col_map:
                    continue
                
                # データ行を読み込む
                for r in range(header_row_idx + 1, ws.max_row + 1):
                    row_values = [cell.value for cell in ws[r]]
                    if not row_values:
                        continue
                    
                    product_name = ""
                    if len(row_values) > 1 and row_values[1]:
                        product_name = str(row_values[1])
                    elif row_values[0]:
                        product_name = str(row_values[0])
                    
                    if not product_name:
                        continue
                    
                    size = InventoryManager.normalize_size(product_name)
                    if not size:
                        continue
                    
                    for c_idx, date_str in date_col_map.items():
                        if c_idx < len(row_values):
                            val = row_values[c_idx]
                            try:
                                count = int(float(val)) if val is not None else 0
                            except:
                                count = 0
                            
                            if date_str not in date_records:
                                date_records[date_str] = {}
                            if target_type not in date_records[date_str]:
                                date_records[date_str][target_type] = {}
                            
                            date_records[date_str][target_type][size] = count
                            total_loaded += 1
            
            except Exception as e:
                st.error(f"ファイル読み込みエラー: {uploaded_file.name} - {str(e)}")
        
        return date_records, total_loaded

def init_session_state():
    """セッション状態を初期化"""
    if 'inventory' not in st.session_state:
        st.session_state.inventory = InventoryManager.load_inventory()
    
    if 'records' not in st.session_state:
        st.session_state.records = InventoryManager.load_records()
    
    if 'edit_mode' not in st.session_state:
        st.session_state.edit_mode = {}

def inventory_tab():
    """在庫管理タブ"""
    st.header("📦 在庫管理")
    
    today = datetime.now().strftime("%Y年%m月%d日")
    st.info(f"📅 本日の日付: {today}")
    st.caption("※ 入力欄は前回の在庫数で自動入力されています")
    
    # 最新記録から在庫を同期
    if st.session_state.records:
        latest_record = st.session_state.records[0]
        st.session_state.inventory = latest_record['inventory']
    
    # ボタン
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("💾 本日の記録を保存", use_container_width=True):
            save_daily_record()
    with col2:
        if st.button("📤 現在の在庫をExportダウンロード", use_container_width=True):
            export_current_excel()
    with col3:
        uploaded_files = st.file_uploader("📥 Excelインポート", 
                                         type=['xlsx', 'xls'], 
                                         accept_multiple_files=True,
                                         key="import_excel")
        if uploaded_files:
            import_excel_data(uploaded_files)
    
    # 各Tシャツタイプの在庫入力
    for ttype in TSHIRT_TYPES:
        with st.expander(f"**{ttype}**", expanded=True):
            cols = st.columns(len(SIZES))
            
            for idx, size in enumerate(SIZES):
                with cols[idx]:
                    st.markdown(f"**{size}**")
                    current_val = st.session_state.inventory.get(ttype, {}).get(size, 0)
                    
                    new_val = st.number_input(
                        "在庫数",
                        min_value=0,
                        value=current_val,
                        step=1,
                        key=f"inv_{ttype}_{size}",
                        label_visibility="collapsed"
                    )
                    
                    if new_val != current_val:
                        st.session_state.inventory[ttype][size] = new_val
                        InventoryManager.save_inventory(st.session_state.inventory)
                    
                    # +/- ボタン
                    col_btn1, col_btn2 = st.columns(2)
                    with col_btn1:
                        if st.button("➕", key=f"plus_{ttype}_{size}", use_container_width=True):
                            st.session_state.inventory[ttype][size] += 1
                            InventoryManager.save_inventory(st.session_state.inventory)
                            st.rerun()
                    with col_btn2:
                        if st.button("➖", key=f"minus_{ttype}_{size}", use_container_width=True):
                            st.session_state.inventory[ttype][size] = max(0, st.session_state.inventory[ttype][size] - 1)
                            InventoryManager.save_inventory(st.session_state.inventory)
                            st.rerun()

def save_daily_record():
    """本日の記録を保存"""
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 既存記録をチェック
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
        st.success(f"✅ {today}の記録を更新しました")
    else:
        st.session_state.records.append(new_record)
        st.success(f"✅ {today}の記録を保存しました")
    
    InventoryManager.save_records(st.session_state.records)
    st.rerun()

def import_excel_data(uploaded_files):
    """Excelデータをインポート"""
    date_records, total_loaded = InventoryManager.import_matrix_excel(uploaded_files)
    
    if date_records:
        existing_map = {r['date']: r for r in st.session_state.records}
        
        for date_str, type_data in date_records.items():
            if date_str in existing_map:
                record = existing_map[date_str]
                for ttype, sizes in type_data.items():
                    if ttype not in record['inventory']:
                        record['inventory'][ttype] = {s: 0 for s in SIZES}
                    for s, count in sizes.items():
                        record['inventory'][ttype][s] = count
            else:
                new_inventory = {}
                for ttype in TSHIRT_TYPES:
                    new_inventory[ttype] = {s: 0 for s in SIZES}
                
                for ttype, sizes in type_data.items():
                    for s, count in sizes.items():
                        new_inventory[ttype][s] = count
                
                new_record = {
                    'date': date_str,
                    'timestamp': f"{date_str}T12:00:00",
                    'inventory': new_inventory,
                    'note': 'Excelから自動取込'
                }
                st.session_state.records.append(new_record)
        
        InventoryManager.save_records(st.session_state.records)
        st.success(f"✅ {len(uploaded_files)}個のファイルから{len(date_records)}日分のデータをインポートしました（更新セル数: {total_loaded}）")
        st.rerun()
    else:
        st.warning("⚠️ インポート可能なデータが見つかりませんでした")

def export_current_excel():
    """現在の在庫をExcelエクスポート"""
    output = io.BytesIO()
    wb = openpyxl.Workbook()
    
    for i, ttype in enumerate(TSHIRT_TYPES):
        if i == 0:
            ws = wb.active
            ws.title = ttype[:31]
        else:
            ws = wb.create_sheet(title=ttype[:31])
        
        ws['A1'] = 'サイズ'
        for j, size in enumerate(SIZES):
            ws.cell(row=1, column=j+2, value=size)
        
        ws['A2'] = '在庫数'
        for j, size in enumerate(SIZES):
            ws.cell(row=2, column=j+2, value=st.session_state.inventory[ttype][size])
        
        header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = Font(bold=True, color="FFFFFF")
            cell.alignment = Alignment(horizontal="center")
    
    wb.save(output)
    output.seek(0)
    
    st.download_button(
        label="📥 Excelファイルをダウンロード",
        data=output,
        file_name=f"現在の在庫_{datetime.now().strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

def records_tab():
    """日次記録タブ"""
    st.header("📊 日次記録")
    
    # 期間選択
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        start_date = st.date_input("開始日", value=datetime.now() - timedelta(days=30))
    with col2:
        end_date = st.date_input("終了日", value=datetime.now())
    with col3:
        st.write("")  # スペーサー
        if st.button("🔄 記録を更新", use_container_width=True):
            st.rerun()
    
    # クイック選択ボタン
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("📅 今週", use_container_width=True):
            today = datetime.now()
            start_date = today - timedelta(days=today.weekday())
            end_date = today
    with col2:
        if st.button("📅 今月", use_container_width=True):
            today = datetime.now()
            start_date = today.replace(day=1)
            end_date = today
    with col3:
        if st.button("📅 先月", use_container_width=True):
            today = datetime.now()
            first_day = today.replace(day=1)
            last_month = first_day - timedelta(days=1)
            start_date = last_month.replace(day=1)
            end_date = last_month
    with col4:
        if st.button("📅 全期間", use_container_width=True):
            if st.session_state.records:
                start_date = datetime.strptime(st.session_state.records[-1]['date'], '%Y-%m-%d').date()
                end_date = datetime.strptime(st.session_state.records[0]['date'], '%Y-%m-%d').date()
    
    # エクスポートボタン
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📊 CSVエクスポート", use_container_width=True):
            export_csv(start_date, end_date)
    with col2:
        if st.button("📈 Excelエクスポート", use_container_width=True):
            export_excel(start_date, end_date)
    
    # 記録をフィルタリング
    start_str = start_date.strftime('%Y-%m-%d')
    end_str = end_date.strftime('%Y-%m-%d')
    
    filtered_records = [r for r in st.session_state.records 
                       if start_str <= r['date'] <= end_str]
    
    if not filtered_records:
        st.info(f"📭 指定期間（{start_str} ～ {end_str}）の記録がありません")
        return
    
    st.success(f"📊 記録サマリー: {len(filtered_records)}件 | 期間: {filtered_records[-1]['date']} ～ {filtered_records[0]['date']}")
    
    # 記録表示
    for record in filtered_records:
        date_str = record['date']
        timestamp = datetime.fromisoformat(record['timestamp']).strftime('%H:%M:%S') if 'T' in record['timestamp'] else ""
        note = record.get('note', '')
        
        with st.expander(f"📅 {date_str} {timestamp} {f'({note})' if note else ''}", expanded=False):
            # 編集・削除ボタン
            col1, col2, col3 = st.columns([6, 1, 1])
            with col2:
                if st.button("✏️ 編集", key=f"edit_{date_str}"):
                    st.session_state.edit_mode[date_str] = not st.session_state.edit_mode.get(date_str, False)
                    st.rerun()
            with col3:
                if st.button("🗑️ 削除", key=f"delete_{date_str}"):
                    st.session_state.records = [r for r in st.session_state.records if r['date'] != date_str]
                    InventoryManager.save_records(st.session_state.records)
                    st.success(f"✅ {date_str}の記録を削除しました")
                    st.rerun()
            
            # 編集モード
            if st.session_state.edit_mode.get(date_str, False):
                st.warning("📝 編集モード")
                edited_record = record.copy()
                
                for ttype in TSHIRT_TYPES:
                    st.markdown(f"**{ttype.replace('パンクラス×禅道会コラボTシャツ', '')}**")
                    cols = st.columns(len(SIZES))
                    
                    for idx, size in enumerate(SIZES):
                        with cols[idx]:
                            current_val = record['inventory'].get(ttype, {}).get(size, 0)
                            new_val = st.number_input(
                                f"{size}",
                                min_value=0,
                                value=current_val,
                                step=1,
                                key=f"edit_{date_str}_{ttype}_{size}"
                            )
                            edited_record['inventory'][ttype][size] = new_val
                
                if st.button("💾 変更を保存", key=f"save_{date_str}"):
                    for idx, r in enumerate(st.session_state.records):
                        if r['date'] == date_str:
                            st.session_state.records[idx] = edited_record
                            break
                    InventoryManager.save_records(st.session_state.records)
                    st.session_state.edit_mode[date_str] = False
                    st.success(f"✅ {date_str}の記録を更新しました")
                    st.rerun()
            
            # 通常表示
            else:
                col1, col2 = st.columns(2)
                for idx, ttype in enumerate(TSHIRT_TYPES):
                    with col1 if idx % 2 == 0 else col2:
                        inventory_data = record['inventory'].get(ttype, {})
                        total = sum(inventory_data.values())
                        
                        st.markdown(f"**{ttype.replace('パンクラス×禅道会コラボTシャツ', '')}**")
                        st.markdown(f"<h3 style='color: blue;'>合計: {total}枚</h3>", unsafe_allow_html=True)
                        
                        details = " | ".join([f"{size}: {inventory_data.get(size, 0)}" for size in SIZES])
                        st.caption(details)

def export_csv(start_date, end_date):
    """CSV形式でエクスポート"""
    start_str = start_date.strftime('%Y-%m-%d')
    end_str = end_date.strftime('%Y-%m-%d')
    
    filtered = [r for r in st.session_state.records 
               if start_str <= r['date'] <= end_str]
    
    if not filtered:
        st.warning("⚠️ エクスポートするデータがありません")
        return
    
    data = []
    for record in sorted(filtered, key=lambda x: x['date']):
        for ttype in TSHIRT_TYPES:
            for size in SIZES:
                count = record['inventory'].get(ttype, {}).get(size, 0)
                data.append([record['date'], ttype, size, count])
    
    df = pd.DataFrame(data, columns=['日付', 'Tシャツ種類', 'サイズ', '在庫数'])
    csv = df.to_csv(index=False, encoding='utf-8-sig')
    
    st.download_button(
        label="📥 CSVファイルをダウンロード",
        data=csv,
        file_name=f"在庫記録_{start_str}_{end_str}.csv",
        mime="text/csv"
    )

def export_excel(start_date, end_date):
    """Excel形式でエクスポート"""
    start_str = start_date.strftime('%Y-%m-%d')
    end_str = end_date.strftime('%Y-%m-%d')
    
    filtered = [r for r in st.session_state.records 
               if start_str <= r['date'] <= end_str]
    
    if not filtered:
        st.warning("⚠️ エクスポートするデータがありません")
        return
    
    output = io.BytesIO()
    wb = openpyxl.Workbook()
    
    for i, ttype in enumerate(TSHIRT_TYPES):
        if i == 0:
            ws = wb.active
            ws.title = ttype[:31]
        else:
            ws = wb.create_sheet(title=ttype[:31])
        
        ws['A1'] = '日付'
        for j, size in enumerate(SIZES):
            ws.cell(row=1, column=j+2, value=size)
        
        header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF")
        
        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center")
        
        for row_idx, record in enumerate(sorted(filtered, key=lambda x: x['date']), start=2):
            ws.cell(row=row_idx, column=1, value=record['date'])
            for col_idx, size in enumerate(SIZES, start=2):
                count = record['inventory'].get(ttype, {}).get(size, 0)
                cell = ws.cell(row=row_idx, column=col_idx, value=count)
                cell.alignment = Alignment(horizontal="center")
        
        for column in ws.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            ws.column_dimensions[column_letter].width = max(max_length + 2, 12)
    
    wb.save(output)
    output.seek(0)
    
    st.download_button(
        label="📥 Excelファイルをダウンロード",
        data=output,
        file_name=f"在庫記録_{start_str}_{end_str}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

def settings_tab():
    """設定タブ"""
    st.header("⚙️ 設定")
    
    # サイズ管理
    with st.expander("📏 サイズ管理", expanded=True):
        st.markdown("**現在のサイズ:**")
        st.info(" | ".join(SIZES))
        
        st.caption("※ サイズの追加はコードを直接編集してください")
    
    # データ管理
    with st.expander("🗄️ データ管理", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**データバックアップ**")
            if st.button("💾 全データをダウンロード"):
                backup_data()
        
        with col2:
            st.markdown("**データリストア**")
            uploaded_file = st.file_uploader("JSONファイルをアップロード", type=['json'])
            if uploaded_file:
                restore_data(uploaded_file)
    
    # システム情報
    with st.expander("ℹ️ システム情報", expanded=True):
        st.markdown(f"""
        **バージョン:** 2.0.0 (Streamlit Web App)  
        **登録サイズ数:** {len(SIZES)}  
        **日次記録数:** {len(st.session_state.records)}  
        **データ保存:** JSONファイル（永続化）
        """)

def backup_data():
    """データをバックアップ"""
    backup = {
        'inventory': st.session_state.inventory,
        'records': st.session_state.records,
        'backup_date': datetime.now().isoformat()
    }
    
    json_str = json.dumps(backup, ensure_ascii=False, indent=2)
    st.download_button(
        label="📥 バックアップファイルをダウンロード",
        data=json_str,
        file_name=f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        mime="application/json"
    )

def restore_data(uploaded_file):
    """データをリストア"""
    try:
        backup = json.load(uploaded_file)
        st.session_state.inventory = backup['inventory']
        st.session_state.records = backup['records']
        
        InventoryManager.save_inventory(st.session_state.inventory)
        InventoryManager.save_records(st.session_state.records)
        
        st.success("✅ データをリストアしました")
        st.rerun()
    except Exception as e:
        st.error(f"❌ リストアに失敗しました: {str(e)}")

def main():
    init_session_state()
    
    st.title("👕 Tシャツ在庫管理システム")
    st.markdown("**パンクラス×禅道会コラボTシャツ**")
    
    # タブ
    tab1, tab2, tab3 = st.tabs(["📦 在庫管理", "📊 日次記録", "⚙️ 設定"])
    
    with tab1:
        inventory_tab()
    
    with tab2:
        records_tab()
    
    with tab3:
        settings_tab()

if __name__ == "__main__":
    main()