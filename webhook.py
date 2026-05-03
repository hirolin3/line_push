from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, PostbackEvent, TextSendMessage
import os
import urllib.parse

app = Flask(__name__)

LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET") # ここでChannel Secretが必要！

line_bot_api = LineBotApi(LINE_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

@app.route("/callback", method=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(PostbackEvent)
def handle_postback(event):
    # ボタンから送られてきたデータを解析 (ans=正解&name=...)
    data = dict(urllib.parse.parse_qsl(event.postback.data))
    
    if data.get('ans') == "正解":
        res = f"🎯 正解です！！\n\nこの銘柄は「{data.get('name')}」でした。お見事！"
    else:
        res = f"❌ 残念！不正解です。\n\n正解は「{data.get('name')}」でした。また明日挑戦しましょう！"
    
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=res))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))