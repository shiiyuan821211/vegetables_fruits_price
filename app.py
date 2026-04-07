import os
import urllib.parse
import requests
from bs4 import BeautifulSoup
import concurrent.futures
import datetime

from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    FlexMessage,
    FlexContainer
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

app = Flask(__name__)

CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN', 'YOUR_CHANNEL_ACCESS_TOKEN')
CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET', 'YOUR_CHANNEL_SECRET')

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

def shorten_url(u):
    try:
        r = requests.get(f"http://tinyurl.com/api-create.php?url={urllib.parse.quote(u)}", timeout=3)
        if r.status_code == 200:
            return r.text
    except:
        pass
    return u

def fetch_detail(item, headers):
    a, title_text = item
    title_text = " ".join(title_text.split())
    url = a['href']
    if not url.startswith('http'):
        url = "https://www.twfood.cc" + url
        
    try:
        res = requests.get(url, headers=headers, timeout=5)
        detail_soup = BeautifulSoup(res.text, 'html.parser')
        
        # 抓取該農產品專屬圖標
        img_tag = detail_soup.find('img', src=lambda s: s and '/img/code/' in s)
        img_url = "https://www.twfood.cc" + img_tag['src'] if img_tag else "https://www.twfood.cc/images/logo2025-120x120.png"
        
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

        short_url = shorten_url(url)
        
        # --- 新增: 計算歷史價格漲跌幅 ---
        percent_change = 0
        alert_text = None
        alert_color = "#000000"
        
        item_code = ""
        parts = urllib.parse.urlparse(url).path.split('/')
        if len(parts) >= 3:
            item_code = parts[2]
            
        if item_code:
            try:
                today = datetime.date.today()
                week_ago = today - datetime.timedelta(days=21)
                start_day = week_ago.strftime("%Y-%m-%d")
                hist_url = f'https://www.twfood.cc/api/FarmTradeSumWeeks?filter={{"order":"endDay asc","where":{{"itemCode":"{item_code}","startDay":{{"gte":"{start_day}"}}}}}}'
                hist_res = requests.get(hist_url, headers=headers, timeout=5)
                hist_data = hist_res.json()
                if len(hist_data) >= 2:
                    last_week_avg = hist_data[-2].get('avgPrice', 0)
                    this_week_avg = hist_data[-1].get('avgPrice', 0)
                    if last_week_avg > 0:
                        percent_change = (this_week_avg - last_week_avg) / last_week_avg
            except Exception as e:
                pass

        if percent_change >= 0.5:
            alert_text = "🚨 價格暴漲中！"
            alert_color = "#ff0000"
        elif percent_change >= 0.2:
            alert_text = "📈 目前價格偏高"
            alert_color = "#ff6600"
        elif percent_change <= -0.5:
            alert_text = "💸 價格大跳水，超划算！"
            alert_color = "#00aa00"
        elif percent_change <= -0.2:
            alert_text = "📉 目前價格便宜"
            alert_color = "#00aa00"
        # -------------------------------

        if retail_kg is not None and retail_jin is not None:
            retail_100g = round(retail_kg / 10, 1)
            
            body_contents = [
              {
                "type": "text",
                "text": title_text,
                "weight": "bold",
                "size": "xl",
                "wrap": True
              }
            ]
            
            if alert_text:
                body_contents.append({
                    "type": "text",
                    "text": alert_text,
                    "weight": "bold",
                    "size": "md",
                    "color": alert_color,
                    "margin": "sm"
                })
                
            body_contents.append({
                "type": "box",
                "layout": "vertical",
                "margin": "lg",
                "spacing": "sm",
                "contents": [
                  {
                    "type": "box",
                    "layout": "baseline",
                    "spacing": "sm",
                    "contents": [
                      { "type": "text", "text": "價格(100g)", "color": "#aaaaaa", "size": "sm", "flex": 4 },
                      { "type": "text", "text": f"{fmt(retail_100g)} 元", "wrap": True, "color": "#000000", "size": "sm", "flex": 5 }
                    ]
                  },
                  {
                    "type": "box",
                    "layout": "baseline",
                    "spacing": "sm",
                    "contents": [
                      { "type": "text", "text": "價格(臺斤)", "color": "#aaaaaa", "size": "sm", "flex": 4 },
                      { "type": "text", "text": f"{fmt(retail_jin)} 元", "wrap": True, "color": "#000000", "size": "sm", "flex": 5 }
                    ]
                  },
                  {
                    "type": "box",
                    "layout": "baseline",
                    "spacing": "sm",
                    "contents": [
                      { "type": "text", "text": "價格(公斤)", "color": "#aaaaaa", "size": "sm", "flex": 4 },
                      { "type": "text", "text": f"{fmt(retail_kg)} 元", "wrap": True, "color": "#000000", "size": "sm", "flex": 5 }
                    ]
                  }
                ]
            })
            
            # 回傳 Flex Message 氣泡的 Dictionary 格式
            return {
              "type": "bubble",
              "hero": {
                "type": "image",
                "url": img_url,
                "size": "full",
                "aspectRatio": "20:13",
                "aspectMode": "cover"
              },
              "body": {
                "type": "box",
                "layout": "vertical",
                "contents": body_contents
              },
              "footer": {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": [
                  {
                    "type": "button",
                    "style": "link",
                    "height": "sm",
                    "action": {
                      "type": "uri",
                      "label": "查看來源",
                      "uri": short_url
                    }
                  }
                ],
                "flex": 0
              }
            }
        else:
            return None
    except Exception as e:
        print(f"Error fetching detail: {e}")
        return None

def get_vege_price(keyword: str):
    """去 twfood.cc 搜尋蔬果並回傳價格 Flex 格式"""
    query = urllib.parse.quote(keyword)
    url = f"https://www.twfood.cc/search?q={query}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    }

    try:
        res = requests.get(url, headers=headers, timeout=5)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')

        candidates = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            if ('/vege/' in href or '/fruit/' in href) and '/topic/' not in href:
                text = a.get_text(separator=' ', strip=True)
                if text and '更多細節' not in text:
                    candidates.append((a, text))
        
        matched_items = []
        if candidates:
            for a, text in candidates:
                if text.split('-')[0].strip() == keyword:
                    matched_items.append((a, text))
            if not matched_items:
                for a, text in candidates:
                    if f"({keyword}," in text or f" {keyword}," in text or f"{keyword})" in text or f"({keyword})" in text:
                        matched_items.append((a, text))
            if not matched_items:
                for a, text in candidates:
                    if keyword in text:
                        matched_items.append((a, text))
            if not matched_items:
                matched_items = [candidates[0]]
        
        if not matched_items:
            return f"找不到關於「{keyword}」的最新價格資訊哦！"
            
        matched_items = matched_items[:10]
        
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(fetch_detail, item, headers) for item in matched_items]
            for future in concurrent.futures.as_completed(futures):
                data = future.result()
                if data:
                    results.append(data)
                
        if not results:
            return f"找到「{keyword}」，但目前無法直接讀取它的預估零售價格 😭"
            
        return results

    except requests.exceptions.RequestException as e:
        print(f"Request Error: {e}")
        return "連線 twfood.cc 失敗，請稍後再試！"
    except Exception as e:
        print(f"Error: {e}")
        return "爬蟲解析發生錯誤 😭"


@app.route("/", methods=['GET'])
def ping():
    return "Bot is alive!"

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
    reply_data = get_vege_price(user_msg)
    
    if isinstance(reply_data, str):
        # 如果是字串，代表出錯或找不到
        messages = [TextMessage(text=reply_data)]
    elif isinstance(reply_data, list) and len(reply_data) > 0:
        # 如果是列表，組成 Carousel Flex Message
        carousel = {
            "type": "carousel",
            "contents": reply_data
        }
        flex_msg = FlexMessage(
            alt_text=f"【{user_msg}】最新市場行情",
            contents=FlexContainer.from_dict(carousel)
        )
        messages = [flex_msg]
    else:
        messages = [TextMessage(text=f"找不到關於「{user_msg}」的價格，系統異常！")]

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=messages
            )
        )

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
