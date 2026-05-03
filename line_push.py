import os
import json
import random
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from linebot import LineBotApi
from linebot.models import TextSendMessage, ImageSendMessage
import imgbbpy

# --- 環境変数 ---
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")
IMGBB_API_KEY = os.getenv("IMGBB_API_KEY")

line_bot_api = LineBotApi(LINE_ACCESS_TOKEN)

def generate_stock_image(ticker, is_jp):
    symbol = f"{ticker}.T" if is_jp else ticker
    stock = yf.Ticker(symbol)
    df = stock.history(period="9mo")
    
    # テクニカル計算
    df['SMA5'] = df['Close'].rolling(window=5).mean()
    df['SMA25'] = df['Close'].rolling(window=25).mean()
    std25 = df['Close'].rolling(window=25).std()
    df['BB_up'] = df['SMA25'] + (std25 * 3)
    df['BB_low'] = df['SMA25'] - (std25 * 3)
    
    # ATR
    tr = pd.concat([df['High']-df['Low'], (df['High']-df['Close'].shift()).abs(), (df['Low']-df['Close'].shift()).abs()], axis=1).max(axis=1)
    df['ATR'] = tr.rolling(window=14).mean()
    
    df = df.tail(125)
    
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.6, 0.2, 0.2])
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close']), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA5'], line=dict(color='orange', width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['BB_up'], line=dict(color='rgba(255,255,255,0.2)', dash='dot')), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['BB_low'], line=dict(color='rgba(255,255,255,0.2)', dash='dot')), row=1, col=1)
    
    colors = ['red' if r['Open'] < r['Close'] else 'green' for _, r in df.iterrows()]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=colors), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['ATR'], line=dict(color='yellow', width=1.5)), row=3, col=1)
    
    fig.update_layout(template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False, width=1000, height=800)
    
    img_path = os.path.join(os.path.dirname(__file__), "line_quiz.png")
    fig.write_image(img_path, engine="kaleido")
    return img_path

def main():
    # --- 重要: パスを確実に取得 ---
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(BASE_DIR, 'ai_stock_dictionary_rich_225.json')
    
    print(f"DEBUG: BASE_DIR is {BASE_DIR}")
    print(f"DEBUG: Looking for JSON at {json_path}")

    # ファイルの読み込み
    try:
        # openの中身が 'ai_stock_dictionary...' ではなく json_path になっているか確認
        with open(json_path, 'r', encoding='utf-8') as f:
            stocks = json.load(f)
    except Exception as e:
        print(f"❌ 読み込み失敗: {str(e)}")
        # フォルダの中身をデバッグ表示
        print(f"DEBUG: Folder contents: {os.listdir(BASE_DIR)}")
        return

    target = random.choice(stocks)
    img_path = generate_stock_image(target['code'], True)
    
    client = imgbbpy.SyncClient(IMGBB_API_KEY)
    image_url = client.upload(file=img_path).url
    
    message = f"【本日の銘柄クイズ 📈】\n\n💡 ヒント:\n{target['simple_desc'][:120]}...\n\nさて、どこの銘柄でしょう？"
    
    line_bot_api.push_message(LINE_USER_ID, [
        TextSendMessage(text=message),
        ImageSendMessage(original_content_url=image_url, preview_image_url=image_url)
    ])
    print(f"✅ 送信成功: {target['name']}")

if __name__ == "__main__":
    main()
