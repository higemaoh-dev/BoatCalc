import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import sqlite3
import json
from datetime import datetime, time

# ==========================================
# 1. データベース制御・初期化
# ==========================================
DB_NAME = "fishing_log.db"

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """データベースのテーブル作成および、初期シードデータの投入"""
    conn = get_db_connection()
    c = conn.cursor()
    # 釣行（親テーブル）
    c.execute('''
        CREATE TABLE IF NOT EXISTS trips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            date TEXT NOT NULL,
            departure TEXT,
            destination TEXT,
            route_coords TEXT, -- JSON array of [lat, lon]
            members TEXT
        )
    ''')
    # 釣果（子テーブル）
    c.execute('''
        CREATE TABLE IF NOT EXISTS catches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trip_id INTEGER,
            species TEXT NOT NULL,
            size REAL,
            quantity INTEGER,
            caught_time TEXT,
            lat REAL,
            lon REAL,
            point_name TEXT,
            FOREIGN KEY(trip_id) REFERENCES trips(id)
        )
    ''')
    conn.commit()
    
    # テスト・デモ用のシードデータが未登録の場合は投入する
    c.execute("SELECT COUNT(*) FROM trips")
    if c.fetchone()[0] == 0:
        demo_route = [
            [35.4411, 139.6542],  # 新山下マリーナ（出航地）
            [35.4215, 139.6912],  # 本牧海づり施設沖
            [35.3612, 139.8105]   # 中ノ瀬沖（目的地）
        ]
        c.execute('''
            INSERT INTO trips (title, date, departure, destination, route_coords, members)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            "東京湾タイラバ＆マゴチ仕立て船", 
            "2024-05-15", 
            "新山下マリーナ", 
            "中ノ瀬沖", 
            json.dumps(demo_route), 
            "山田 太郎, 佐藤 次郎, 鈴木 花子"
        ))
        trip_id = c.lastrowid
        
        # 釣果データ（マダイとマゴチ）
        c.execute('''
            INSERT INTO catches (trip_id, species, size, quantity, caught_time, lat, lon, point_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (trip_id, "マダイ", 54.5, 1, "08:30", 35.3612, 139.8105, "中ノ瀬中央タイラバポイント"))
        
        c.execute('''
            INSERT INTO catches (trip_id, species, size, quantity, caught_time, lat, lon, point_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (trip_id, "マゴチ", 47.0, 2, "11:15", 35.4215, 139.6912, "本牧マゴチかけ上がり"))
        
        conn.commit()
    conn.close()

def save_trip_to_db(title, date, departure, destination, route_coords, members, catches):
    """新規の釣行ログとそれに紐づく釣果データを保存"""
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute('''
            INSERT INTO trips (title, date, departure, destination, route_coords, members)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (title, date.strftime("%Y-%m-%d"), departure, destination, json.dumps(route_coords), members))
        trip_id = c.lastrowid
        
        for catch in catches:
            c.execute('''
                INSERT INTO catches (trip_id, species, size, quantity, caught_time, lat, lon, point_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                trip_id, 
                catch['species'], 
                catch['size'], 
                catch['quantity'], 
                catch['caught_time'], 
                catch['lat'], 
                catch['lon'], 
                catch['point_name']
            ))
        conn.commit()
        return trip_id
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def get_all_trips():
    conn = get_db_connection()
    trips = conn.execute("SELECT * FROM trips ORDER BY date DESC").fetchall()
    conn.close()
    return trips

def get_trip_details(trip_id):
    conn = get_db_connection()
    trip = conn.execute("SELECT * FROM trips WHERE id = ?", (trip_id,)).fetchone()
    catches = conn.execute("SELECT * FROM catches WHERE trip_id = ?", (trip_id,)).fetchall()
    conn.close()
    return trip, catches

def delete_trip_from_db(trip_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM catches WHERE trip_id = ?", (trip_id,))
    c.execute("DELETE FROM trips WHERE id = ?", (trip_id,))
    conn.commit()
    conn.close()


# ==========================================
# 2. 定数定義
# ==========================================
# 地図上でクリックやプレビュー設定をしやすくするためのプリセット座標
PRESET_SPOTS = {
    "カスタム手動入力 (地図クリックを推奨)": None,
    "新山下マリーナ (出航地)": [35.4411, 139.6542],
    "本牧海づり施設沖": [35.4215, 139.6912],
    "中ノ瀬沖 (タイラバポイント)": [35.3612, 139.8105],
    "富津沖 (浅場マゴチ)": [35.3150, 139.8000],
    "第二海堡 (タチウオ・アジ)": [35.3132, 139.7405],
    "観音崎沖 (深場タチウオ)": [35.2530, 139.7470],
    "浦賀水道 (真鯛・青物)": [35.2410, 139.7560],
}

# Google Maps API 連携を再現（または標準のオープンマップ）するためのタイル定義
MAP_STYLES = {
    "Google Maps (ハイブリッド航空写真)": {
        "tiles": "https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
        "attr": "Google Maps Satellite"
    },
    "Google Maps (標準ロードマップ)": {
        "tiles": "https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}",
        "attr": "Google Maps"
    },
    "OpenStreetMap (トポグラフィー風)": {
        "tiles": "OpenStreetMap",
        "attr": "OpenStreetMap"
    }
}


# ==========================================
# 3. Streamlit UI 構築
# ==========================================
st.set_page_config(
    page_title="釣果ログ & GPSルート共有",
    page_icon="🎣",
    layout="wide",
    initial_sidebar_state="expanded"
)

# DB初期化
init_db()

# 一時登録用（新規作成時のセッションステート）
if 'temp_route' not in st.session_state:
    st.session_state.temp_route = []
if 'temp_catches' not in st.session_state:
    st.session_state.temp_catches = []
if 'last_clicked' not in st.session_state:
    st.session_state.last_clicked = {"lat": 35.3612, "lng": 139.8105}

# タイトル
st.title("🎣 釣果ログ & GPSルートマップ共有システム")
st.markdown("同船メンバーで「どこで何が釣れたか」の移動経路やポイントをGoogle Maps連携表示でスマートに保存・共有できるWebツールです。")

# 共有用クエリパラメータの監視 (?trip_id=xx)
query_params = st.query_params
param_trip_id = query_params.get("trip_id", None)

# サイドバーによる共通設定
st.sidebar.header("🧭 ナビゲーション & 設定")
map_style_name = st.sidebar.selectbox("🗺️ Google Maps スタイル", list(MAP_STYLES.keys()), index=0)
selected_style = MAP_STYLES[map_style_name]

# 操作モード切替（共有クエリパラメータがある場合は自動で閲覧モードに固定）
if param_trip_id is not None:
    mode = st.sidebar.radio("📁 モード選択", ["釣行ログを閲覧・共有する", "新規釣行ログを登録する"], index=0)
else:
    mode = st.sidebar.radio("📁 モード選択", ["釣行ログを閲覧・共有する", "新規釣行ログを登録する"], index=0)


# ------------------------------------------
# モード 1: 閲覧・共有 (View & Share)
# ------------------------------------------
if mode == "釣行ログを閲覧・共有する":
    st.subheader("📊 保存済み釣行ログの閲覧・共有")
    
    trips = get_all_trips()
    if not trips:
        st.info("登録されているログがありません。右上のメニューから『新規釣行ログを登録する』を選択して追加してください。")
    else:
        trip_options = {t['id']: f"【{t['date']}】{t['title']}" for t in trips}
        
        # クエリパラメータが指定されている場合は、初期選択状態にする
        default_index = 0
        if param_trip_id is not None:
            try:
                pid = int(param_trip_id)
                if pid in trip_options:
                    default_index = list(trip_options.keys()).index(pid)
            except ValueError:
                pass
        
        selected_trip_id = st.selectbox(
            "閲覧したい釣行ログを選択してください：",
            options=list(trip_options.keys()),
            format_func=lambda x: trip_options[x],
            index=default_index
        )
        
        # データベースから対象ログおよび釣果詳細を取得
        trip, catches = get_trip_details(selected_trip_id)
        route_coords = json.loads(trip['route_coords']) if trip['route_coords'] else []
        
        # 表示エリアを2分割 (左: 地図, 右: 詳細情報)
        col1, col2 = st.columns([2, 1])
        
        with col2:
            st.markdown(f"### 📋 {trip['title']}")
            st.write(f"📅 **釣行日:** {trip['date']}")
            st.write(f"⚓ **出航場所:** `{trip['departure']}` ➡️ **目的地:** `{trip['destination']}`")
            st.write(f"👥 **同船メンバー:** {trip['members'] if trip['members'] else 'なし'}")
            
            # 精算・メンバー共有用
            st.markdown("---")
            st.markdown("🤝 **メンバー共有機能**")
            # 擬似的な共有リンク表示
            st.caption("この釣行の閲覧画面に直接アクセスできる共有リンクです。同船メンバーにLINEなどで共有できます。")
            share_url = f"?trip_id={selected_trip_id}"
            st.code(share_url, language="text")
            
            # 危険な操作エリア
            st.markdown("---")
            with st.expander("🚨 ログの削除"):
                if st.button("データベースからこの釣行ログを完全に削除", key="del_btn"):
                    delete_trip_from_db(selected_trip_id)
                    st.success("削除が完了しました。")
                    st.query_params.clear()
                    st.rerun()

        with col1:
            # 地図中心点の決定
            if route_coords:
                center = route_coords[0]
                zoom = 11
            elif catches:
                center = [catches[0]['lat'], catches[0]['lon']]
                zoom = 11
            else:
                center = [35.3612, 139.8105]  # 初期座標
                zoom = 10
                
            m = folium.Map(
                location=center, 
                zoom_start=zoom,
                tiles=selected_style["tiles"],
                attr=selected_style["attr"]
            )
            
            # ルート(移動経路)の描画
            if len(route_coords) > 1:
                folium.PolyLine(
                    locations=route_coords,
                    color="cyan" if "y" in selected_style["tiles"] else "blue", # 航空写真なら見えやすいシアン
                    weight=5,
                    opacity=0.85,
                    tooltip="航行経路"
                ).add_to(m)
                
                # 起点・終点マーカー
                folium.Marker(
                    location=route_coords[0],
                    popup=f"出航港: {trip['departure']}",
                    icon=folium.Icon(color="green", icon="play", prefix="fa")
                ).add_to(m)
                folium.Marker(
                    location=route_coords[-1],
                    popup=f"最終到達地: {trip['destination']}",
                    icon=folium.Icon(color="black", icon="flag", prefix="fa")
                ).add_to(m)
                
            # 各釣果スポットのプロット(ピン立て)
            for idx, catch in enumerate(catches):
                popup_html = f"""
                <div style='font-family: sans-serif; font-size: 13px; line-height: 1.5;'>
                    <b style='color:#d9534f; font-size:14px;'>🐟 {catch['species']}</b><br>
                    📏 <b>サイズ:</b> {catch['size']} cm<br>
                    🔢 <b>匹数:</b> {catch['quantity']} 匹<br>
                    🕒 <b>時間:</b> {catch['caught_time']}<br>
                    📍 <b>ポイント名:</b> {catch['point_name']}
                </div>
                """
                folium.Marker(
                    location=[catch['lat'], catch['lon']],
                    popup=folium.Popup(popup_html, max_width=250),
                    tooltip=f"{catch['species']} ({catch['size']}cm) × {catch['quantity']}匹",
                    icon=folium.Icon(color="red", icon="certificate")
                ).add_to(m)
            
            # 地図描画
            st_folium(m, width="100%", height=500, key="view_map")
            
        # 下部: 釣果詳細の表
        st.markdown("### 🐟 釣れた魚種の記録一覧")
        if catches:
            data_list = []
            for c in catches:
                data_list.append({
                    "魚種": c['species'],
                    "サイズ (cm)": c['size'],
                    "匹数 (数)": c['quantity'],
                    "釣れた時間帯": c['caught_time'],
                    "ポイント名/メモ": c['point_name'],
                    "緯度": c['lat'],
                    "経度": c['lon']
                })
            df = pd.DataFrame(data_list)
            st.dataframe(df, use_container_width=True)
            
            # 分析おまけ
            total_fish = sum(c['quantity'] for c in catches)
            st.metric(label="🎣 本釣行の総匹数", value=f"{total_fish} 匹")
        else:
            st.info("この釣行に関する釣果登録はまだありません。")


# ------------------------------------------
# モード 2: 新規釣行ログ登録 (Register)
# ------------------------------------------
elif mode == "新規釣行ログを登録する":
    st.subheader("📝 新しい釣行ログ・移動経路・釣果の登録")
    st.info("【ヒント】右下の『プレビュー地図』をクリックすると、その場所の緯度経度が自動的に取得され、経由地や釣果場所の入力に流用できます！")
    
    col_input1, col_input2 = st.columns([1, 1])
    
    with col_input1:
        st.markdown("### ① 釣行の基本情報")
        new_title = st.text_input("釣行タイトル", placeholder="例: 東京湾タチウオ・アジリレー仕立て")
        new_date = st.date_input("釣行日", datetime.today())
        new_dep = st.text_input("出航地", placeholder="例: 新山下港")
        new_dest = st.text_input("最終到達目的地", placeholder="例: 第二海堡沖")
        new_members = st.text_input("同船メンバー (カンマ区切り)", placeholder="例: 山田太郎, 佐藤次郎")
        
        st.markdown("---")
        st.markdown("### ② 移動経路（ルート）の設定")
        st.markdown("出航港、ポイント、目的地の順に座標を登録して経路（ライン）を作ります。")
        
        route_preset = st.selectbox("プリセットから座標を選択", list(PRESET_SPOTS.keys()), key="r_preset")
        
        col_rlat, col_rlon = st.columns(2)
        if PRESET_SPOTS[route_preset] is not None:
            r_lat_val = PRESET_SPOTS[route_preset][0]
            r_lon_val = PRESET_SPOTS[route_preset][1]
        else:
            # 地図クリック座標を流用
            r_lat_val = st.session_state.last_clicked["lat"]
            r_lon_val = st.session_state.last_clicked["lng"]
            
        r_lat = col_rlat.number_input("緯度", value=r_lat_val, format="%.6f", key="r_lat")
        r_lon = col_rlon.number_input("経度", value=r_lon_val, format="%.6f", key="r_lon")
        
        if st.button("➕ 経由地をルートに追加する", use_container_width=True):
            st.session_state.temp_route.append([r_lat, r_lon])
            st.success(f"座標 [{r_lat:.5f}, {r_lon:.5f}] をルート配列に格納しました。")
            st.rerun()
            
        if st.session_state.temp_route:
            st.write("🏃‍♂️ **現在のルート経由地点:**")
            st.dataframe(pd.DataFrame(st.session_state.temp_route, columns=["緯度", "経度"]), height=110)
            if st.button("🧹 ルート情報をクリア", key="clear_r"):
                st.session_state.temp_route = []
                st.rerun()
                
    with col_input2:
        st.markdown("### ③ 釣果・釣れたスポットの登録")
        st.markdown("魚種ごとの情報を入れ、釣れた場所（GPS）を指定して登録します。")
        
        catch_species = st.text_input("釣れた魚種", placeholder="例: アジ, タチウオ, マダイ")
        col_csz, col_cqt = st.columns(2)
        catch_size = col_csz.number_input("サイズ (cm)", min_value=0.0, max_value=300.0, value=25.0, step=0.5)
        catch_qty = col_cqt.number_input("匹数 (数)", min_value=1, max_value=1000, value=1, step=1)
        
        catch_time = st.time_input("釣れた時刻", time(9, 30))
        catch_preset = st.selectbox("プリセットから釣れた場所を選択", list(PRESET_SPOTS.keys()), key="c_preset")
        
        col_clat, col_clon = st.columns(2)
        if PRESET_SPOTS[catch_preset] is not None:
            c_lat_val = PRESET_SPOTS[catch_preset][0]
            c_lon_val = PRESET_SPOTS[catch_preset][1]
        else:
            # 地図クリック座標を流用
            c_lat_val = st.session_state.last_clicked["lat"]
            c_lon_val = st.session_state.last_clicked["lng"]
            
        c_lat = col_clat.number_input("スポット緯度", value=c_lat_val, format="%.6f", key="c_lat")
        c_lon = col_clon.number_input("スポット経度", value=c_lon_val, format="%.6f", key="c_lon")
        catch_point_name = st.text_input("ポイントの通称 / メモ", placeholder="例: 中ノ瀬の水深15m付近")
        
        if st.button("🐟 釣果を一時リストに追加する", use_container_width=True):
            if not catch_species:
                st.warning("魚種名を入力してください。")
            else:
                new_catch_item = {
                    "species": catch_species,
                    "size": catch_size,
                    "quantity": catch_qty,
                    "caught_time": catch_time.strftime("%H:%M"),
                    "lat": c_lat,
                    "lon": c_lon,
                    "point_name": catch_point_name if catch_point_name else "指定スポット"
                }
                st.session_state.temp_catches.append(new_catch_item)
                st.success(f"{catch_species} ({catch_size}cm) の仮登録を追加しました。")
                st.rerun()
                
        if st.session_state.temp_catches:
            st.write("🐟 **追加予定の釣果リスト:**")
            df_temp_catches = pd.DataFrame(st.session_state.temp_catches)
            st.dataframe(df_temp_catches[["species", "size", "quantity", "caught_time", "point_name"]], height=110)
            if st.button("🧹 釣果リストをクリア", key="clear_c"):
                st.session_state.temp_catches = []
                st.rerun()

    st.markdown("---")
    
    # 登録確認プレビューマップ ＆ 保存処理
    st.markdown("### ④ 新規釣行データのプレビュー確認 ＆ 地図連携")
    
    col_prev_map, col_save = st.columns([2, 1])
    
    with col_prev_map:
        # プレビューの中心計算
        if st.session_state.temp_route:
            prev_center = st.session_state.temp_route[0]
        elif st.session_state.temp_catches:
            prev_center = [st.session_state.temp_catches[0]['lat'], st.session_state.temp_catches[0]['lon']]
        else:
            prev_center = [35.3612, 139.8105] # 東京湾デフォルト
            
        m_prev = folium.Map(
            location=prev_center, 
            zoom_start=11,
            tiles=selected_style["tiles"],
            attr=selected_style["attr"]
        )
        
        # ルートプレビュー線
        if len(st.session_state.temp_route) > 1:
            folium.PolyLine(
                locations=st.session_state.temp_route,
                color="cyan" if "y" in selected_style["tiles"] else "blue",
                weight=5,
                opacity=0.85,
                tooltip="移動経路予定"
            ).add_to(m_prev)
            folium.Marker(st.session_state.temp_route[0], popup="出発地点", icon=folium.Icon(color="green")).add_to(m_prev)
            folium.Marker(st.session_state.temp_route[-1], popup="目的地", icon=folium.Icon(color="black")).add_to(m_prev)
        elif len(st.session_state.temp_route) == 1:
            folium.Marker(st.session_state.temp_route[0], popup="経由地 1", icon=folium.Icon(color="blue")).add_to(m_prev)
            
        # 釣果プレビューピン
        for idx, tc in enumerate(st.session_state.temp_catches):
            folium.Marker(
                location=[tc['lat'], tc['lon']],
                popup=f"🐟 {tc['species']} ({tc['size']}cm) × {tc['quantity']}",
                icon=folium.Icon(color="red", icon="certificate")
            ).add_to(m_prev)
            
        # プレビューマップ表示とインタラクティブなクリック座標の検知
        out_prev = st_folium(m_prev, width="100%", height=400, key="prev_map")
        
        # クリック座標のアップデート
        if out_prev and out_prev.get("last_clicked"):
            st.session_state.last_clicked = out_prev["last_clicked"]
            st.success(f"🚩 地図クリック座標をキャッチしました ➡️ 緯度: {st.session_state.last_clicked['lat']:.5f} / 経度: {st.session_state.last_clicked['lng']:.5f} (各座標の入力欄に自動適用可能になりました。)")

    with col_save:
        st.markdown("#### 💾 ログを確定・保存")
        st.write("上記のルート情報や釣果プレビューを確認し、問題がなければデータベースへ永続化してください。")
        
        if st.button("🚀 この内容で釣行ログを新規保存する", use_container_width=True):
            if not new_title:
                st.error("【入力漏れ】タイトルは必須項目です。")
            elif not new_dep or not new_dest:
                st.error("【入力漏れ】出航地および目的地を入力してください。")
            else:
                try:
                    new_id = save_trip_to_db(
                        title=new_title,
                        date=new_date,
                        departure=new_dep,
                        destination=new_dest,
                        route_coords=st.session_state.temp_route,
                        members=new_members,
                        catches=st.session_state.temp_catches
                    )
                    st.success("🎉 保存に成功しました！閲覧画面へ自動ジャンプします。")
                    # セッションデータの初期化
                    st.session_state.temp_route = []
                    st.session_state.temp_catches = []
                    # 共有クエリを適用して閲覧モードへ移動
                    st.query_params["trip_id"] = str(new_id)
                    st.rerun()
                except Exception as e:
                    st.error(f"データベース保存中にエラーが発生しました: {e}")
