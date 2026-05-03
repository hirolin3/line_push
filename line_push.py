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
    symbol = f"{ticker}.T" if is_jp else ticker
    df = yf.Ticker(symbol).history(period="9mo")
    
    # テクニカル計算
    df['SMA5'] = df['Close'].rolling(window=5).mean()
    df['SMA25'] = df['Close'].rolling(window=25).mean()
    df = df.tail(80) # 表示期間を少し絞って見やすくする

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])
    
    # ローソク足の修正: 線の太さと色を明示
    fig.add_trace(go.Candlestick(
        x=df.index.strftime('%m/%d'), # 日付を文字列にして土日を詰める
        open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
        increasing_line_color='#FF4B4B', decreasing_line_color='#00F0FF',
        name="株価"
    ), row=1, col=1)
    
    fig.add_trace(go.Scatter(x=df.index.strftime('%m/%d'), y=df['SMA5'], line=dict(color='orange', width=2)), row=1, col=1)

    colors = ['#FF4B4B' if r['Open'] < r['Close'] else '#00F0FF' for _, r in df.iterrows()]
    fig.add_trace(go.Bar(x=df.index.strftime('%m/%d'), y=df['Volume'], marker_color=colors), row=2, col=1)
    
    # 【重要】type="category" にすることで土日を詰め、棒を太くする
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
