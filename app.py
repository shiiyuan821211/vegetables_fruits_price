import os
import urllib.parse
import requests
from bs4 import BeautifulSoup

from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

app = Flask(__name__)

# 使用 os.environ 讀取環境變數，這樣部署到雲端時才安全
CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN', 'YOUR_CHANNEL_ACCESS_TOKEN')
CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET', 'YOUR_CHANNEL_SECRET')

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

def get_vege_price(keyword: str) -> str:
    """去 twfood.cc 搜尋蔬果並回傳價格字串"""
    query = urllib.parse.quote(keyword)
    url = f"https://www.twfood.cc/search?q={query}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    }

    try:
        res = requests.get(url, headers=headers, timeout=5)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')

        # 收集所有符合分類的商品連結
        candidates = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            # 過濾掉分類連結，只抓商品連結
            if ('/vege/' in href or '/fruit/' in href) and '/topic/' not in href:
                text = a.get_text(separator=' ', strip=True)
                if text and '更多細節' not in text:
                    candidates.append((a, text))
        
        product_card = None
        if candidates:
            # 1. 類別名稱完全符合 (例如 "蘋果-五爪" 的 "蘋果")
            for a, text in candidates:
                if text.split('-')[0].strip() == keyword:
                    product_card = a
                    break
            
            # 2. 括號內的別名完全符合 (例如 "(高麗菜, 捲心菜)")
            if not product_card:
                for a, text in candidates:
                    if f"({keyword}," in text or f" {keyword}," in text or f"{keyword})" in text or f"({keyword})" in text:
                        product_card = a
                        break

            # 3. 包含關鍵字
            if not product_card:
                for a, text in candidates:
                    if keyword in text:
                        product_card = a
                        break
                        
            # 4. 預設第一筆
            if not product_card:
                product_card = candidates[0][0]
        
        if not product_card:
            return f"找不到關於「{keyword}」的最新價格資訊哦！"

        first_product_url = product_card.get('href')
        if not first_product_url.startswith('http'):
            first_product_url = "https://www.twfood.cc" + first_product_url
            
        # 爬取商品詳細頁面
        detail_res = requests.get(first_product_url, headers=headers, timeout=5)
        detail_soup = BeautifulSoup(detail_res.text, 'html.parser')
        
        # 抓取菜名
        title = detail_soup.find('h1')
        title_text = title.text.strip() if title else keyword
        
        # 抓取表格內的價格資訊
        th_elements = detail_soup.find_all('th')
        retail_kg = None
        retail_jin = None
        
        current_section = ""
        last_number = None
        
        if th_elements:
            for th in th_elements:
                text = th.get_text(separator=' ', strip=True)
                if not text: continue
                
                if "價:" in text or "量:" in text:
                    current_section = text
                elif current_section == "預估零售價:":
                    try:
                        last_number = float(text)
                    except ValueError:
                        if "(元/公斤)" in text and last_number is not None:
                            retail_kg = last_number
                        elif "(元/台斤)" in text and last_number is not None:
                            retail_jin = last_number
                            
        def fmt(n): return int(n) if n.is_integer() else n

        def shorten_url(u):
            try:
                r = requests.get(f"http://tinyurl.com/api-create.php?url={urllib.parse.quote(u)}", timeout=3)
                if r.status_code == 200:
                    return r.text
            except:
                pass
            return u

        short_url = shorten_url(first_product_url)

        if retail_kg is not None and retail_jin is not None:
            retail_100g = round(retail_kg / 10, 1)
            price_info = (
                f"【預估零售價】\n"
                f"{fmt(retail_100g)} (元/100g)\n"
                f"{fmt(retail_jin)} (元/臺斤)\n"
                f"{fmt(retail_kg)} (元/公斤)"
            )
            return f"【{title_text}】最新市場行情：\n\n{price_info}\n\n來源：{short_url}"
        else:
            return f"【{title_text}】\n目前無法直接抓到預估零售價格，請參考網頁：{short_url}"
            
    except requests.exceptions.RequestException as e:
        print(f"Request Error: {e}")
        return "連線 twfood.cc 失敗，請稍後再試！"
    except Exception as e:
        print(f"Error: {e}")
        return "爬蟲解析發生錯誤 😭"


@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_msg = event.message.text.strip()
    reply_text = get_vege_price(user_msg)

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)]
            )
        )

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
