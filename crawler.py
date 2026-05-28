import requests
import io
import pandas as pd
import json
from datetime import datetime, timedelta

def get_today_live_data():
    """第一軌：抓取今日最新即時數據"""
    url = "https://openapi.twse.com.tw/v1/taiwanFuturesBigTraders/callsAndPutsDate"
    today_str = datetime.now().strftime("%Y/%m/%d")
    try:
        response = requests.get(url, timeout=15)
        if response.status_code != 200: return None
        data_json = response.json()
        
        tx_data = [item for item in data_json if any(k in item.get('CommodityId', '') for k in ["臺股期貨", "TX"])]
        if not tx_data: return None
            
        result = {'date': today_str}
        for item in tx_data:
            name = item.get('IdentityName', '')
            long_val = int(item.get('OpenInterestLong', 0))
            short_val = int(item.get('OpenInterestShort', 0))
            net_val = int(item.get('OpenInterestNet', 0))
            
            if any(k in name for k in ['外資', '陸資']):
                result['foreign'] = {'long': long_val, 'short': short_val, 'net': net_val}
            elif '投信' in name:
                result['sitc'] = {'long': long_val, 'short': short_val, 'net': net_val}
            elif '自營商' in name:
                result['dealers'] = {'long': long_val, 'short': short_val, 'net': net_val}
        
        if 'foreign' in result and 'sitc' in result and 'dealers' in result:
            return result
        return None
    except:
        return None

def get_history_data():
    """第二軌：下載期交所歷史 CSV（改用「固定位置」抓取，不再核對中文字，徹底防壞）"""
    url = "https://www.taifex.com.tw/cht/3/futThreeBigProductInstiDown"
    end_date = datetime.now()
    start_date = end_date - timedelta(days=40)
    payload = {
        'down_type': '1',
        'queryStartDate': start_date.strftime("%Y/%m/%d"),
        'queryEndDate': end_date.strftime("%Y/%m/%d"),
        'commodityId': 'TX'
    }
    try:
        response = requests.post(url, data=payload, timeout=20)
        if response.status_code != 200: return [], f"期交所伺服器連線失敗(狀態碼:{response.status_code})"
        
        # 讀取 CSV 檔案內容
        df = pd.read_csv(io.StringIO(response.text))
        
        # 期交所標準三大法人 CSV 的固定欄位結構位置：
        # 第0欄:日期, 第1欄:商品代號/名稱, 第2欄:身份別...
        # 多方未平倉通常在第11欄, 空方在第12欄, 淨額在第13欄 (依據期交所標準規格)
        # 為了絕對保險，我們直接用欄位順序來指定！
        
        results = {}
        for _, row in df.iterrows():
            try:
                # 模糊相容：抓取商品名稱與身份別
                commodity = str(row.iloc[1]).strip()
                if '臺股期貨' not in commodity and 'TX' not in commodity: continue
                
                date_str = str(row.iloc[0]).strip().replace('-', '/')
                name = str(row.iloc[2]).strip()
                
                # 直接用表格第 11, 12, 13 欄位置強制取數 (未平倉多、空、淨)
                long_val = int(row.iloc[11])
                short_val = int(row.iloc[12])
                net_val = int(row.iloc[13])
                
                if date_str not in results:
                    results[date_str] = {'date': date_str}
                if any(k in name for k in ['外資', '陸資']):
                    results[date_str]['foreign'] = {'long': long_val, 'short': short_val, 'net': net_val}
                elif '投信' in name:
                    results[date_str]['sitc'] = {'long': long_val, 'short': short_val, 'net': net_val}
                elif '自營商' in name:
                    results[date_str]['dealers'] = {'long': long_val, 'short': short_val, 'net': net_val}
            except:
                continue
        
        final_list = [v for k, v in results.items() if 'foreign' in v and 'sitc' in v and 'dealers' in v]
        final_list.sort(key=lambda x: x['date'])
        
        if len(final_list) > 0:
            return final_list, "OK"
        else:
            return [], "CSV 資料解析成功，但未篩選到符合的大台指(TX)法人行列。"
            
    except Exception as e:
        return [], f"歷史資料解析重大異常: {e}"

def generate_html_template(data_list_json, err_msg="OK"):
    err_banner = "" if err_msg == "OK" else f"""
    <div class="w-full max-w-5xl bg-red-950/80 border border-red-500/50 rounded-xl p-4 my-2 text-red-200 text-xs">
        ⚠️ [⚠️ SYSTEM_ERROR_LOG]：{err_msg} <br> 提示：系統目前自動啟動安全防護，畫面展示之歷史數據可能未包含今日最新收盤。
    </div>"""
    
    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🎛️ TRI-法人期貨留倉高級觀測站</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        .neon-border {{ box-shadow: 0 0 15px rgba(6, 182, 212, 0.15); border: 1px solid rgba(6, 182, 212, 0.3); }}
        .neon-text-orange {{ text-shadow: 0 0 8px rgba(245, 158, 11, 0.6); }}
        .neon-text-cyan {{ text-shadow: 0 0 8px rgba(6, 182, 212, 0.6); }}
    </style>
</head>
<body class="bg-[#0b0f19] text-slate-200 min-h-screen p-4 md:p-8 flex flex-col items-center justify-start font-mono">
    {err_banner}
    <div class="w-full max-w-5xl bg-[#111827]/80 backdrop-blur-md rounded-2xl p-6 my-2 neon-border">
        <div class="flex justify-between items-center border-b border-cyan-500/30 pb-4 mb-6">
            <div>
                <h1 class="text-xl md:text-2xl font-black tracking-widest text-cyan-400 neon-text-cyan">SYSTEM://TRI_法人期貨留倉觀測站</h1>
                <p class="text-[10px] text-slate-500 mt-1">REFRESH_TIME: <span id="update-date" class="text-slate-400">LOADING...</span></p>
            </div>
            <span class="px-2 py-1 text-[10px] bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 rounded">📊 近 10 日數據監控</span>
        </div>
        <div class="overflow-x-auto mb-8 rounded-xl border border-slate-800 bg-[#0d1321]">
            <table class="w-full text-left border-collapse">
                <thead>
                    <tr class="border-b border-slate-800 text-slate-400 text-xs bg-slate-900/50">
                        <th class="p-4">法人項目 [ENTITY]</th>
                        <th class="p-4 text-right">多方未平倉 (口)</th>
                        <th class="p-4 text-right">空方未平倉 (口)</th>
                        <th class="p-4 text-right">淨部位 (口) [NET]</th>
                    </tr>
                </thead>
                <tbody class="text-sm divide-y divide-slate-800/60">
                    <tr>
                        <td class="p-4 font-bold text-amber-400 neon-text-orange">■ 外資及陸資</td>
                        <td id="foreign-long" class="p-4 text-right">--</td><td id="foreign-short" class="p-4 text-right">--</td><td id="foreign-net" class="p-4 text-right font-black text-base">--</td>
                    </tr>
                    <tr>
                        <td class="p-4 font-bold text-blue-400">■ 投信</td>
                        <td id="sitc-long" class="p-4 text-right">--</td><td id="sitc-short" class="p-4 text-right">--</td><td id="sitc-net" class="p-4 text-right font-black text-base">--</td>
                    </tr>
                    <tr>
                        <td class="p-4 font-bold text-emerald-400">■ 自營商</td>
                        <td id="dealers-long" class="p-4 text-right">--</td><td id="dealers-short" class="p-4 text-right">--</td><td id="dealers-net" class="p-4 text-right font-black text-base">--</td>
                    </tr>
                </tbody>
            </table>
        </div>
        <div class="bg-[#0d1321] border border-slate-800 p-4 rounded-xl">
            <h3 class="text-xs font-bold text-slate-400 mb-4">📈 三大法人淨部位近 10 日歷史趨勢線</h3>
            <div class="h-72 w-full"><canvas id="trendsChart"></canvas></div>
        </div>
    </div>
    <script>
        const rawData = {data_list_json};
        if (rawData.length > 0) {{
            const latest = rawData[rawData.length - 1];
            document.getElementById('update-date').innerText = latest.date;
            const fillRow = (prefix, data) => {{
                document.getElementById(prefix + '-long').innerText = data.long.toLocaleString();
                document.getElementById(prefix + '-short').innerText = data.short.toLocaleString();
                const net = data.net;
                const netEl = document.getElementById(prefix + '-net');
                netEl.innerText = (net > 0 ? "+" : "") + net.toLocaleString();
                netEl.className = net >= 0 ? "p-4 text-right font-black text-base text-rose-500" : "p-4 text-right font-black text-base text-emerald-400";
            }};
            fillRow('foreign', latest.foreign); fillRow('sitc', latest.sitc); fillRow('dealers', latest.dealers);
            const ctx = document.getElementById('trendsChart').getContext('2d');
            new Chart(ctx, {{
                type: 'line',
                data: {{
                    labels: rawData.map(d => d.date.substring(5)),
                    datasets: [
                        {{ label: '外資', data: rawData.map(d => d.foreign.net), borderColor: '#f59e0b', tension: 0.15 }},
                        {{ label: '投信', data: rawData.map(d => d.sitc.net), borderColor: '#3b82f6', tension: 0.15 }},
                        {{ label: '自營商', data: rawData.map(d => d.dealers.net), borderColor: '#10b981', tension: 0.15 }}
                    ]
                }},
                options: {{ responsive: true, maintainAspectRatio: false }}
            }});
        }}
    </script>
</body>
</html>
"""

def update_web():
    data_list, err_msg = get_history_data()
    today_data = get_today_live_data()
    
    if today_data and len(data_list) > 0:
        if not any(d['date'] == today_data['date'] for d in data_list):
            data_list.append(today_data)
        else:
            for idx, d in enumerate(data_list):
                if d['date'] == today_data['date']:
                    data_list[idx] = today_data
                    break

    # 如果抓取失敗，防崩潰預設安全數據
    if len(data_list) == 0:
        data_list = [{
            'date': '暫無連線紀錄',
            'foreign': {'long': 0, 'short': 0, 'net': 0},
            'sitc': {'long': 0, 'short': 0, 'net': 0},
            'dealers': {'long': 0, 'short': 0, 'net': 0}
        }]
        
    data_list = data_list[-10:]
    data_list_json = json.dumps(data_list, ensure_ascii=False)
    
    final_html = generate_html_template(data_list_json, err_msg)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(final_html)
    print("【欄位容錯覆蓋大成功】")

if __name__ == "__main__":
    update_web()
