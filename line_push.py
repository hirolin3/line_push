import os
import json
import random
import time
import requests
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
# LINE SDK v2 (v3への移行警告は一旦無視して動作を優先します)
from linebot import LineBotApi
from linebot.models import (
    TextSendMessage, ImageSendMessage, FlexSendMessage, 
    BubbleContainer, BoxComponent, TextComponent, ButtonComponent, PostbackAction
)
import imgbbpy

# --- 環境変数 ---
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")
IMGBB_API_KEY = os.getenv("IMGBB_API_KEY")

line_bot_api = LineBotApi(LINE_ACCESS_TOKEN)

def generate_stock_image(ticker, is_jp):
    # --- 1. シンボル名の重複を徹底的に防ぐ ---
    ticker = str(ticker).strip().replace(".T", "") # 一旦 .T を消してから
    if is_jp:
        symbol = f"{ticker}.T" # 改めて .T を付ける
    else:
        symbol = ticker
    
    print(f"DEBUG: Fetching data for {symbol}")

    # --- 2. レート制限対策 (User-Agent設定) ---
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    })

    df = pd.DataFrame()
    # 最大3回リトライ
    for i in range(3):
        try:
            stock = yf.Ticker(symbol, session=session)
            df = stock.history(period="9mo")
            if not df.empty:
                break
        except Exception as e:
            print(f"⚠️ 試行 {i+1}回目エラー: {e}")
        time.sleep(5)

    if df.empty:
        print(f"❌ {symbol} のデータを取得できませんでした。")
        return None

    # --- 3. 安全な日付変換 ---
    df.index = pd.to_datetime(df.index) # 強制的に日付型へ
    df = df.tail(80)
    date_strings = df.index.strftime('%m/%d') # ここでエラーにならないよう上記で変換済み

    # チャート作成
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])
    
    # ローソク足
    fig.add_trace(go.Candlestick(
        x=date_strings, 
        open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
        increasing_line_color='#FF4B4B', decreasing_line_color='#00F0FF',
        name="株価"
    ), row=1, col=1)
    
    # 5日移動平均線
    df['SMA5'] = df['Close'].rolling(window=5).mean()
    fig.add_trace(go.Scatter(x=date_strings, y=df['SMA5'], line=dict(color='orange', width=2)), row=1, col=1)

    # 出来高
    colors = ['#FF4B4B' if r['Open'] < r['Close'] else '#00F0FF' for _, r in df.iterrows()]
    fig.add_trace(go.Bar(x=date_strings, y=df['Volume'], marker_color=colors), row=2, col=1)
    
    fig.update_xaxes(type='category', rangeslider_visible=False)
    fig.update_layout(template="plotly_dark", width=1000, height=700, margin=dict(l=10, r=10, t=10, b=10))
    
    img_path = os.path.join(os.path.dirname(__file__), "line_quiz.png")
    fig.write_image(img_path, engine="kaleido")
    return img_path

def create_quiz_flex(target, options):
    buttons = []
    for opt in options:
        name = opt['name'][:20]
        code = str(opt.get('code') or opt.get('symbol')).replace(".T", "")
        correct_code = str(target.get('code') or target.get('symbol')).replace(".T", "")
        
        is_correct = "正解" if code == correct_code else "不正解"
        
        buttons.append(ButtonComponent(
            action=PostbackAction(
                label=f"{name} ({code})",
                data=f"ans={is_correct}&name={target['name']}&code={code}",
                display_text=f"{name} だと思う！"
            ),
            color="#00CCFF", style="primary", margin="sm"
        ))

    bubble = BubbleContainer(
        body=BoxComponent(
            layout='vertical',
            contents=[
                TextComponent(text="📈 このチャートの銘柄は？", weight='bold', size='lg'),
                TextComponent(text=f"💡 ヒント:\n{target['simple_desc'][:100]}...", size='sm', wrap=True, margin='md'),
                BoxComponent(layout='vertical', margin='lg', contents=buttons)
            ]
        )
    )
    return FlexSendMessage(alt_text="株価クイズが届きました！", contents=bubble)

def main():
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(BASE_DIR, 'ai_stock_dictionary_rich_225.json')
    
    with open(json_path, 'r', encoding='utf-8') as f:
        stocks = json.load(f)
    
    target = random.choice(stocks)
    wrongs = random.sample([s for s in stocks if s != target], 3)
    options = random.sample([target] + wrongs, 4)
    
    print(f"DEBUG: Selected {target['name']} ({target.get('code')})")
    
    img_path = generate_stock_image(target['code'], True)
    
    if img_path is None:
        print("❌ 画像生成に失敗したため終了します。")
        return

    client = imgbbpy.SyncClient(IMGBB_API_KEY)
    image_url = client.upload(file=img_path).url
    
    line_bot_api.push_message(LINE_USER_ID, [
        ImageSendMessage(original_content_url=image_url, preview_image_url=image_url),
        create_quiz_flex(target, options)
    ])
    print(f"✅ 送信完了: {target['name']}")

if __name__ == "__main__":
    main()
