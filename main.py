import os
import json
import base64
import datetime
import requests
import pandas as pd
import yfinance as yf
import holidays # 米国祝日判定用

# --- 定数設定 (米国版) ---
TICKERS = {
    "SP500": "^GSPC",       # [金融経済] S&P500 (米国の成長期待)
    "US_Rate": "^TNX",      # [資金コスト] 米10年債金利 (割引率・重力)
    "USD": "DX-Y.NYB",      # [帝国の通貨] ドル指数 (資金吸収力)
    "Copper": "HG=F",       # [実体経済] 銅 (グローバル需要)
    "Oil": "CL=F",          # [物理コスト] WTI原油 (インフレ圧力)
    "Gold": "GC=F"          # [信認/恐怖] 金 (質への逃避)
}

# 表示用ラベル
LABELS = {
    "SP500": "S&P500 (成長期待)",
    "US_Rate": "米10年債金利",
    "USD": "ドル指数 (通貨強度)",
    "Copper": "銅 (実体経済)",
    "Oil": "WTI原油 (コスト)",
    "Gold": "金 (恐怖/信認)"
}

# チャート・アイコン用カラー (US市場慣習)
COLORS = {
    "SP500": "#1f77b4",     # 青 (株)
    "US_Rate": "#7f7f7f",   # グレー (金利)
    "USD": "#2ca02c",       # 緑 (ドル)
    "Copper": "#ff7f0e",    # オレンジ (産業)
    "Oil": "#8c564b",       # 茶 (エネルギー)
    "Gold": "#bcbd22"       # 金 (ゴールド)
}

def get_ny_now():
    """現在時刻(NY時間)を取得"""
    # EST/EDTの厳密な管理より簡易的にUTC-5(標準時)で計算
    # ※厳密にやるならpytzが必要だが標準ライブラリ範囲で実装
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-5)))

def is_market_holiday():
    """NY市場の祝日・土日判定"""
    now_ny = get_ny_now()
    today = now_ny.date()
    
    # 土日 (5=Sat, 6=Sun)
    if today.weekday() >= 5:
        return True
    
    # 米国の祝日 (holidaysライブラリ)
    us_holidays = holidays.US()
    if today in us_holidays:
        return True
    return False

def get_market_data():
    """Yahoo Financeからデータ取得＆整形"""
    print("Fetching US market data...")
    end_date = datetime.datetime.now()
    start_date = end_date - datetime.timedelta(days=550)

    # データ取得
    raw_df = yf.download(list(TICKERS.values()), start=start_date, end=end_date, progress=False)['Close']
    
    if isinstance(raw_df.columns, pd.MultiIndex):
        raw_df.columns = raw_df.columns.droplevel(1)
    
    # 欠損値補完 (修正箇所1)
    raw_df = raw_df.ffill()
    raw_df = raw_df.dropna(how='all')
    
    return raw_df

def analyze_trends(raw_df):
    """365日前と比較してトレンド(UP/DOWN/FLAT)を判定"""
    current_data = raw_df.iloc[-1]
    
    target_date = raw_df.index[-1] - datetime.timedelta(days=365)
    
    if target_date < raw_df.index[0]:
        idx_365 = 0
    else:
        idx_365 = raw_df.index.get_indexer([target_date], method='nearest')[0]
        
    old_data = raw_df.iloc[idx_365]

    trends = {}
    ratios = {}
    
    for key, ticker in TICKERS.items():
        col_name = ticker
        
        if col_name not in current_data or pd.isna(current_data[col_name]):
            ratios[key] = 1.0
            trends[key] = "FLAT"
            continue

        val_now = current_data[col_name]
        val_old = old_data[col_name]
        
        if val_old == 0 or pd.isna(val_old): 
            ratio = 1.0
        else: 
            ratio = val_now / val_old
        
        ratios[key] = ratio
        
        # 判定基準: ±5%
        if ratio >= 1.05:
            trends[key] = "UP"
        elif ratio <= 0.95:
            trends[key] = "DOWN"
        else:
            trends[key] = "FLAT"
            
    return trends, ratios, current_data

def diagnose_economy(trends):
    """構造的歪み判定ロジック (US Macro)"""
    
    sp500 = trends["SP500"]
    rate = trends["US_Rate"]
    usd = trends["USD"]
    cop = trends["Copper"]
    oil = trends["Oil"]
    gold = trends["Gold"]

    # --- Priority 1: クライシス・危険な歪み ---
    
    # バリュエーション・ショック (逆資産効果)
    if sp500 == "DOWN" and rate == "UP":
        return {"level": "critical", "name": "バリュエーション・ショック (逆資産効果)", "desc": "金利の急騰（割引率の上昇）により、株式の適正価値が強制的に切り下げられています。FRBの引き締め等が引き起こす、典型的な金融引き締め局面の痛みです。"}
    
    # スタグフレーション
    if sp500 == "DOWN" and oil == "UP":
        return {"level": "critical", "name": "スタグフレーション (不況下の物価高)", "desc": "景気後退で株価が下落しているにもかかわらず、エネルギーコストが上昇し続けています。中央銀行がアクセルもブレーキも踏めない、経済にとって最も苦しい状態です。"}

    # ドル・スクイーズ
    if usd == "UP" and cop == "DOWN":
        return {"level": "danger", "name": "ドル・スクイーズ (ドルの独り勝ち)", "desc": "ドルが強すぎるため、グローバルな実体経済（銅）が資金不足で窒息しています。新興国通貨の危機や、米国輸出企業の業績悪化につながる「破壊的なドル高」です。"}

    # --- Priority 2: バブル・熱狂・乖離 ---

    # 金融相場
    if sp500 == "UP" and cop == "DOWN":
        return {"level": "warning", "name": "金融相場 (実体なき熱狂)", "desc": "実体経済（銅）の需要は冷え込んでいますが、金融緩和や特定の期待（AI等）だけで株価が上昇しています。実体と金融の乖離が広がっている状態です。"}

    # インフレ・ブーム (過熱)
    if sp500 == "UP" and oil == "UP" and rate == "UP":
        return {"level": "warning", "name": "インフレ・ブーム (過熱)", "desc": "コスト高や金利高をものともせず、強い成長期待で株価が上昇しています。景気は非常に強いですが、バブルの末期や「ノーランディング」のリスクを孕んでいます。"}

    # --- Priority 3: 健全な成長 ---

    # 生産性革命 (黄金期)
    if sp500 == "UP" and (rate == "FLAT" or rate == "DOWN") and (oil == "FLAT" or oil == "DOWN"):
        return {"level": "safe", "name": "生産性革命 (適温相場)", "desc": "金利もコストも落ち着いている中で株価が上昇しています。イノベーションによる生産性向上で、インフレなき成長を謳歌している理想的な「ゴルディロックス」状態です。"}

    # リフレーション (景気回復)
    if sp500 == "UP" and cop == "UP" and rate == "UP":
        return {"level": "safe", "name": "リフレーション (景気回復)", "desc": "金利上昇をこなせるほど需要が強く、実体経済（銅）と金融経済（株）が両輪で上昇しています。健全な景気拡大サイクルの中にあります。"}

    # --- Priority 4: 停滞・不況 ---

    # デフレ・リセッション
    if sp500 == "DOWN" and rate == "DOWN" and oil == "DOWN":
        return {"level": "stagnation", "name": "デフレ・リセッション (需要蒸発)", "desc": "株、金利、エネルギー価格がすべて下落しています。需要が世界的に消失しており、投資家が現金（キャッシュ）へ逃避している完全な不況モードです。"}

    # 信認の揺らぎ
    if usd == "DOWN" and gold == "UP":
        return {"level": "stagnation", "name": "信認の揺らぎ (質のへの逃避)", "desc": "基軸通貨であるドルが売られ、無国籍通貨である金（ゴールド）が買われています。米国の財政や金融システムへの不信感、あるいは将来のインフレ懸念が高まっています。"}

    # --- その他 ---
    return {"level": "other", "name": "トレンド交錯", "desc": "明確なパターンに当てはまりません。金融指標と実体経済指標がちぐはぐに動いており、市場が次の方向性を探っている過渡期です。"}

def generate_html(raw_df, trends, ratios, current_data, diagnosis):
    """HTML生成"""
    
    # --- チャートデータ作成 (365日分) ---
    target_date = raw_df.index[-1] - datetime.timedelta(days=365)
    chart_df = raw_df[raw_df.index >= target_date].copy()
    
    # 正規化 (Start=100)
    first_row = chart_df.iloc[0].replace(0, 1) 
    normalized_df = chart_df.div(first_row).mul(100).round(2)
    
    plot_data = {}
    display_keys = ["SP500", "US_Rate", "USD", "Copper", "Oil", "Gold"]
    
    for key in display_keys:
        col_key = TICKERS[key]
        if col_key in normalized_df:
            # 欠損値補完 (修正箇所2)
            series = normalized_df[col_key].ffill()
            plot_data[LABELS[key]] = series.tolist()

    chart_labels = normalized_df.index.strftime('%Y/%m/%d').tolist()
    
    # Chart.js Dataset
    datasets = []
    for label_jp, data_list in plot_data.items():
        key_code = [k for k, v in LABELS.items() if v == label_jp][0]
        color = COLORS.get(key_code, "#333")
        
        datasets.append({
            "label": label_jp,
            "data": data_list,
            "borderColor": color,
            "backgroundColor": color,
            "borderWidth": 2,
            "pointRadius": 0,
            "pointHoverRadius": 5,
            "fill": False,
            "tension": 0.2
        })

    json_labels = json.dumps(chart_labels)
    json_datasets = json.dumps(datasets)

    # --- 診断スタイル ---
    style_map = {
        "critical":   {"bg": "#ffebee", "text": "#b71c1c", "border": "#d32f2f"}, # 赤
        "danger":     {"bg": "#ffecb3", "text": "#e65100", "border": "#ff8f00"}, # 橙
        "warning":    {"bg": "#fff8e1", "text": "#f57f17", "border": "#ffca28"}, # 黄
        "safe":       {"bg": "#e8f5e9", "text": "#1b5e20", "border": "#43a047"}, # 緑
        "stagnation": {"bg": "#e3f2fd", "text": "#0d47a1", "border": "#1e88e5"}, # 青
        "other":      {"bg": "#f5f5f5", "text": "#424242", "border": "#9e9e9e"}  # 灰
    }
    st = style_map.get(diagnosis['level'], style_map["other"])

    # --- HTML構築 ---
    html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Helvetica Neue', sans-serif; max-width: 800px; margin: 0 auto; color: #333;">

        <div style="background: {st['bg']}; border-left: 6px solid {st['border']}; padding: 20px; border-radius: 4px; margin-bottom: 30px; box-shadow: 0 2px 5px rgba(0,0,0,0.05);">
            <div style="font-size: 0.85rem; color: {st['text']}; font-weight: bold; margin-bottom: 5px;">現在の米国経済フェーズ</div>
            <h3 style="margin: 0 0 10px 0; color: {st['text']}; font-size: 1.4rem;">{diagnosis['name']}</h3>
            <p style="margin: 0; font-size: 1.0rem; line-height: 1.6;">{diagnosis['desc']}</p>
        </div>

        <h4 style="font-size: 1.0rem; border-bottom: 2px solid #eee; padding-bottom: 10px; margin-bottom: 20px; color: #555;">主要指数の構造トレンド (対365日前比)</h4>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 15px; margin-bottom: 30px;">
    """

    icons = {"UP": "📈", "FLAT": "➡️", "DOWN": "📉"}
    display_keys = ["SP500", "US_Rate", "USD", "Copper", "Oil", "Gold"]
    
    for key in display_keys:
        trend = trends[key]
        ratio = ratios[key]
        label = LABELS[key]
        icon = icons[trend]
        
        if TICKERS[key] in current_data:
            raw_val = current_data[TICKERS[key]]
            fmt_val = f"{raw_val:,.2f}"
        else:
            fmt_val = "-"

        t_color = "#333"
        if trend == "UP": t_color = "#d32f2f"
        elif trend == "DOWN": t_color = "#1976d2"

        html += f"""
            <div style="background: #fff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 15px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                <div style="font-size: 0.75rem; color: #666; font-weight: bold; height: 32px; display: flex; align-items: center; justify-content: center;">{label}</div>
                <div style="font-size: 2rem; margin: 5px 0;">{icon}</div>
                <div style="font-size: 1.1rem; font-weight: bold; color: {t_color};">x {ratio:.2f}</div>
                <div style="font-size: 0.7rem; color: #999; margin-top: 5px;">現在: {fmt_val}</div>
            </div>
        """

    html += """
        </div>

        <details style="margin-bottom: 40px; background: #fafafa; border: 1px solid #eee; border-radius: 6px;">
            <summary style="padding: 15px; cursor: pointer; font-weight: bold; outline: none; color: #555;">経済判定ロジックの解説 (クリックで開閉)</summary>
            <div style="padding: 0 20px 20px 20px; font-size: 0.9rem; line-height: 1.8; border-top: 1px solid #eee;">
                <p style="margin-bottom: 20px;">金融（株・金利）、実体経済（銅）、コスト（原油・ドル）の3軸の乖離から、米国経済の構造的状態を自動判定しています。</p>
                
                <h5 style="margin: 20px 0 10px 0; border-left: 4px solid #d32f2f; padding-left: 10px; color: #333;">🔴 危険な歪み (クライシス)</h5>
                <div style="margin-bottom: 15px;">
                    <strong style="color: #d32f2f;">バリュエーション・ショック (逆資産効果)</strong><br>
                    <span style="font-size: 0.8rem; color: #666; background: #eee; padding: 2px 6px; border-radius: 4px;">条件: SP500=DOWN and US_Rate=UP</span><br>
                    金利急騰（割引率の上昇）により、株式の価値が強制的に剥落している局面です。FRBの引き締め等が引き起こす、典型的な金融調整の痛みです。
                </div>
                <div style="margin-bottom: 15px;">
                    <strong style="color: #d32f2f;">スタグフレーション (不況下の物価高)</strong><br>
                    <span style="font-size: 0.8rem; color: #666; background: #eee; padding: 2px 6px; border-radius: 4px;">条件: SP500=DOWN and Oil=UP</span><br>
                    景気後退で株価が下落しているにもかかわらず、エネルギーコストが上昇し続けています。経済にとって最も逃げ場のない苦しい状態です。
                </div>
                <div>
                    <strong style="color: #e65100;">ドル・スクイーズ (ドルの独り勝ち)</strong><br>
                    <span style="font-size: 0.8rem; color: #666; background: #eee; padding: 2px 6px; border-radius: 4px;">条件: USD=UP and Copper=DOWN</span><br>
                    ドルが強すぎるため、グローバルな実体経済（銅）が資金不足で窒息しています。新興国危機や、米国輸出企業の業績悪化につながる破壊的なドル高です。
                </div>

                <h5 style="margin: 25px 0 10px 0; border-left: 4px solid #f57f17; padding-left: 10px; color: #333;">🟠 乖離・熱狂 (バブル)</h5>
                <div style="margin-bottom: 15px;">
                    <strong style="color: #f57f17;">金融相場 (実体なき熱狂)</strong><br>
                    <span style="font-size: 0.8rem; color: #666; background: #eee; padding: 2px 6px; border-radius: 4px;">条件: SP500=UP and Copper=DOWN</span><br>
                    実体経済（銅）は冷え込んでいますが、金融緩和や特定の期待だけで株価が上昇しています。実体と金融の乖離が広がっている状態です。
                </div>
                <div>
                    <strong style="color: #f57f17;">インフレ・ブーム (過熱)</strong><br>
                    <span style="font-size: 0.8rem; color: #666; background: #eee; padding: 2px 6px; border-radius: 4px;">条件: SP500=UP and Oil=UP and US_Rate=UP</span><br>
                    コスト高や金利高をものともせず、強い成長期待で株価が上昇しています。景気は非常に強いですが、バブルの末期や過熱のリスクを孕んでいます。
                </div>

                <h5 style="margin: 25px 0 10px 0; border-left: 4px solid #2e7d32; padding-left: 10px; color: #333;">🟢 健全な成長</h5>
                <div style="margin-bottom: 15px;">
                    <strong style="color: #2e7d32;">生産性革命 (適温相場)</strong><br>
                    <span style="font-size: 0.8rem; color: #666; background: #eee; padding: 2px 6px; border-radius: 4px;">条件: SP500=UP and US_Rate=FLAT/DOWN</span><br>
                    金利もコストも落ち着いている中で株価が上昇しています。イノベーションによる生産性向上で、インフレなき成長を謳歌している理想的な状態です。
                </div>
                <div>
                    <strong style="color: #2e7d32;">リフレーション (景気回復)</strong><br>
                    <span style="font-size: 0.8rem; color: #666; background: #eee; padding: 2px 6px; border-radius: 4px;">条件: SP500=UP and Copper=UP and US_Rate=UP</span><br>
                    金利上昇をこなせるほど需要が強く、実体経済（銅）と金融経済（株）が両輪で上昇しています。健全な景気拡大サイクルです。
                </div>

                <h5 style="margin: 25px 0 10px 0; border-left: 4px solid #1976d2; padding-left: 10px; color: #333;">🔵 停滞・不況</h5>
                <div style="margin-bottom: 15px;">
                    <strong style="color: #0d47a1;">デフレ・リセッション (需要蒸発)</strong><br>
                    <span style="font-size: 0.8rem; color: #666; background: #eee; padding: 2px 6px; border-radius: 4px;">条件: SP500=DOWN and US_Rate=DOWN</span><br>
                    株、金利、エネルギー価格がすべて下落しています。需要が世界的に消失しており、投資家が現金（キャッシュ）へ逃避している不況モードです。
                </div>
                <div style="margin-bottom: 15px;">
                    <strong style="color: #0d47a1;">信認の揺らぎ (質への逃避)</strong><br>
                    <span style="font-size: 0.8rem; color: #666; background: #eee; padding: 2px 6px; border-radius: 4px;">条件: USD=DOWN and Gold=UP</span><br>
                    基軸通貨であるドルが売られ、無国籍通貨である金が買われています。米国の財政や金融システムへの不信感、あるいは将来のインフレ懸念が高まっています。
                </div>

                <h5 style="margin: 25px 0 10px 0; border-left: 4px solid #757575; padding-left: 10px; color: #333;">⚪ その他</h5>
                <div>
                    <strong style="color: #616161;">トレンド交錯・過渡期</strong><br>
                    <span style="font-size: 0.8rem; color: #666; background: #eee; padding: 2px 6px; border-radius: 4px;">パターン合致なし</span><br>
                    主要指数の方向性がバラバラで、明確なトレンドが出ていません。市場の迷い、あるいはトレンドの転換点（過渡期）にある可能性が高い状態です。
                </div>
            </div>
        </details>

        <h4 style="font-size: 1.0rem; border-bottom: 2px solid #eee; padding-bottom: 10px; color: #555;">過去365日の相対パフォーマンス (起点=100)</h4>
        
        <div style="position: relative; width: 100%; height: 450px; border: 1px solid #eee; border-radius: 4px; padding: 10px; background: #fff;">
            <canvas id="us_economy_chart"></canvas>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <script>
        (function() {
            const ctx = document.getElementById('us_economy_chart').getContext('2d');
            new Chart(ctx, {
                type: 'line',
                data: {
                    labels: """ + json_labels + """,
                    datasets: """ + json_datasets + """
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { mode: 'index', intersect: false },
                    plugins: {
                        legend: {
                            position: 'bottom',
                            labels: { usePointStyle: true, padding: 20, font: {size: 11} }
                        },
                        tooltip: {
                            mode: 'index', intersect: false,
                            backgroundColor: 'rgba(255, 255, 255, 0.95)',
                            titleColor: '#333', bodyColor: '#333', borderColor: '#ddd', borderWidth: 1
                        }
                    },
                    scales: {
                        y: {
                            grid: { color: '#f5f5f5' },
                            title: { display: true, text: '相対指数 (Start=100)' }
                        },
                        x: { grid: { display: false }, ticks: { maxTicksLimit: 8 } }
                    },
                    elements: { point: { radius: 0, hitRadius: 10, hoverRadius: 5 } }
                }
            });
        })();
        </script>
    </div>
    """
    return html

def push_to_pipeline(content):
    """データパイプライン(WordPress)へ送信"""
    pipeline_conf = os.environ.get("DATA_PIPELINE_CREDENTIALS", "")
    conf = {}
    
    for line in pipeline_conf.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            conf[k.strip()] = v.strip()

    api_url = conf.get("API_ENDPOINT")
    user_id = conf.get("CLIENT_ID")
    secret  = conf.get("CLIENT_SECRET")
    target  = conf.get("RESOURCE_TARGET")

    if not all([api_url, user_id, secret, target]):
        print("Pipeline configuration incomplete.")
        return

    endpoint = f"{api_url.rstrip('/')}/wp-json/wp/v2/pages/{target}"
    creds = f"{user_id}:{secret}"
    token = base64.b64encode(creds.encode()).decode('utf-8')
    
    headers = {
        'Authorization': f'Basic {token}',
        'Content-Type': 'application/json'
    }
    payload = {'content': content}

    print(f"Pushing data to endpoint: {endpoint}...")
    
    try:
        res = requests.post(endpoint, headers=headers, json=payload)
        if res.status_code == 200:
            print("Data push successful.")
        else:
            print(f"Data push failed: {res.status_code}")
    except Exception as e:
        print(f"Connection error: {e}")

if __name__ == "__main__":
    if is_market_holiday():
        print("US Market holiday. Skipping execution.")
        exit(0)

    try:
        raw_df = get_market_data()
        trends, ratios, current_data = analyze_trends(raw_df)
        diagnosis = diagnose_economy(trends)
        html_content = generate_html(raw_df, trends, ratios, current_data, diagnosis)
        push_to_pipeline(html_content)
        
    except Exception as e:
        print("An error occurred.")
        import traceback
        traceback.print_exc()
        exit(1)
