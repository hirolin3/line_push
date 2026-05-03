import requests # 先頭に追加してください
import time     # 先頭に追加してください
import os
import json
import random
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
# line-bot-sdk v2系を想定
from linebot import LineBotApi
from linebot.models import (
    TextSendMessage, ImageSendMessage, FlexSendMessage, 
    BubbleContainer, BoxComponent, TextComponent, ButtonComponent, PostbackAction
)
import imgbbpy

LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")
IMGBB_API_KEY = os.getenv("IMGBB_API_KEY")

line_bot_api = LineBotApi(LINE_ACCESS_TOKEN)

def generate_stock_image(ticker, is_jp):
    # --- 1. シンボルの整形 (重複防止) ---
    ticker = str(ticker).strip()
    if is_jp:
        # すでに .T が付いていなければ付与する
        symbol = f"{ticker}.T" if not ticker.endswith(".T") else ticker
    else:
        symbol = ticker
        
    print(f"DEBUG: Fetching data for {symbol}") # デバッグログ
    
    stock = yf.Ticker(symbol)
    df = stock.history(period="9mo")
    
    # --- 2. データが取得できなかった場合のチェック ---
    if df.empty:
        print(f"❌ Error: No data found for {symbol}")
        return None

    # テクニカル計算
    df['SMA5'] = df['Close'].rolling(window=5).mean()
    df = df.tail(80) 

    # --- 3. Indexのエラー対策 (DatetimeIndexであることを確認) ---
    # IndexをDatetime型に変換してからstrftimeを呼び出す
    df.index = pd.to_datetime(df.index)
    date_strings = df.index.strftime('%m/%d')

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])
    
    # ローソク足
    fig.add_trace(go.Candlestick(
        x=date_strings, 
        open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
        increasing_line_color='#FF4B4B', decreasing_line_color='#00F0FF',
        name="株価"
    ), row=1, col=1)
    
    fig.add_trace(go.Scatter(x=date_strings, y=df['SMA5'], line=dict(color='orange', width=2)), row=1, col=1)

    colors = ['#FF4B4B' if r['Open'] < r['Close'] else '#00F0FF' for _, r in df.iterrows()]
    fig.add_trace(go.Bar(x=date_strings, y=df['Volume'], marker_color=colors), row=2, col=1)
    
    fig.update_xaxes(type='category', rangeslider_visible=False)
    fig.update_layout(template="plotly_dark", width=1000, height=700, margin=dict(l=10, r=10, t=10, b=10))
    
    img_path = os.path.join(os.path.dirname(__file__), "line_quiz.png")
    fig.write_image(img_path, engine="kaleido")
    return img_path

    # --- 💡 レート制限対策: ブラウザになりすます設定 ---
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    })

    print(f"DEBUG: Fetching data for {symbol}...")
    
    df = pd.DataFrame()
    # 最大3回リトライする
    for i in range(3):
        try:
            # sessionを指定してTickerを呼び出す
            stock = yf.Ticker(symbol, session=session)
            df = stock.history(period="9mo")
            if not df.empty:
                break
            print(f"⚠️ 試行 {i+1}回目: データが空です。少し待機します。")
        except Exception as e:
            print(f"⚠️ 試行 {i+1}回目: エラーが発生しました ({e})")
        
        # 失敗したら10秒待って再試行
        time.sleep(10)

    if df.empty:
        print(f"❌ 3回試行しましたが、{symbol} のデータを取得できませんでした。")
        return None

    # --- 3. Indexのエラー対策 (DatetimeIndexであることを確認) ---
    # IndexをDatetime型に変換してからstrftimeを呼び出す
    df.index = pd.to_datetime(df.index)
    date_strings = df.index.strftime('%m/%d')

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])
    
    # ローソク足
    fig.add_trace(go.Candlestick(
        x=date_strings, 
        open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
        increasing_line_color='#FF4B4B', decreasing_line_color='#00F0FF',
        name="株価"
    ), row=1, col=1)
    
    fig.add_trace(go.Scatter(x=date_strings, y=df['SMA5'], line=dict(color='orange', width=2)), row=1, col=1)

    colors = ['#FF4B4B' if r['Open'] < r['Close'] else '#00F0FF' for _, r in df.iterrows()]
    fig.add_trace(go.Bar(x=date_strings, y=df['Volume'], marker_color=colors), row=2, col=1)
    
    fig.update_xaxes(type='category', rangeslider_visible=False)
    fig.update_layout(template="plotly_dark", width=1000, height=700, margin=dict(l=10, r=10, t=10, b=10))
    
    img_path = os.path.join(os.path.dirname(__file__), "line_quiz.png")
    fig.write_image(img_path, engine="kaleido")
    return img_path

def create_quiz_flex(target, options):
    """4択ボタン付きのFlex Messageを作成"""
    buttons = []
    for opt in options:
        label = opt['name'][:20] # ボタン文字数制限対策
        code = opt.get('code') or opt.get('symbol')
        is_correct = "正解" if code == (target.get('code') or target.get('symbol')) else "不正解"
        
        # ボタンを押すと「データ」として正誤を送信する(Webhookで受信)
        buttons.append(ButtonComponent(
            action=PostbackAction(
                label=f"{label} ({code})",
                data=f"ans={is_correct}&name={target['name']}&code={code}",
                display_text=f"{label} だと思う！"
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
    with open(os.path.join(BASE_DIR, 'ai_stock_dictionary_rich_225.json'), 'r', encoding='utf-8') as f:
        stocks = json.load(f)
    
    target = random.choice(stocks)
    wrongs = random.sample([s for s in stocks if s != target], 3)
    options = random.sample([target] + wrongs, 4)
    
    # 1. チャート画像生成 & アップロード
    img_path = generate_stock_image(target['code'], True)
    client = imgbbpy.SyncClient(IMGBB_API_KEY)
    image_url = client.upload(file=img_path).url
    
    # 2. クイズ（画像 + ボタン付きメッセージ）をプッシュ送信
    line_bot_api.push_message(LINE_USER_ID, [
        ImageSendMessage(original_content_url=image_url, preview_image_url=image_url),
        create_quiz_flex(target, options)
    ])

if __name__ == "__main__":
    main()
