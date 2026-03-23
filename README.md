# 蔬果即時價格查詢 LINE Bot

這是一個專為台灣使用者設計的 LINE 聊天機器人。只需在 LINE 聊天室中輸入蔬果名稱（如「高麗菜」、「香蕉」），機器人便會即時從 [台灣當季蔬果 (twfood.cc)](https://www.twfood.cc/) 網站抓取並換算最新的零售與批發價格，讓你隨時掌握市場行情！

## ✨ 核心特色功能
1. **精美圖像輪播卡 (Flex Message)**：跳脫單調純文字！自動抓取高品質蔬果圖片，以並排可滑動的商品圖卡（Carousel）華麗呈現。
2. **多品種同步查詢**：若輸入關鍵字包含多個同類品種（例如：白大米苦瓜、山苦瓜），機器人會透過多執行緒（Multi-threading）光速一次列出所有品種的價格卡片。
3. **歷史大數據波動警示**：結合隱藏版 API，自動比對該品項近期「兩週」的歷史平均批發價。若出現明顯波動會立即跳出顏色警語，例如：
   - `🚨 價格暴漲中！` (> +50%)
   - `📈 目前價格偏高` (+20% ~ +50%)
   - `📉 目前價格便宜` (-20% ~ -50%)
   - `💸 價格大跳水，超划算！` (< -50%)
4. **智慧單位換算**：自動將價格同時換算為「100g」、「臺斤」和「公斤」，無論去超市還是傳統市場都能直覺對照。
5. **內建防休眠與縮網址**：整合 UptimeRobot 檢查端點維持 Render Server 24 小時清醒，並透過 TinyURL 自動縮短太長的來源網址。

---

## 🚀 專案檔案結構
- `app.py`：主程式（包含 Flask 伺服器、LINE Webhook 處理，以及 twfood.cc 的非同步爬蟲邏輯）。
- `requirements.txt`：Python 依賴套件清單。
- `Procfile`：Render 或 Heroku 等雲端平台的啟動指令檔。
- `.gitignore`：Git 版本控制的忽略清單。

---

## 🛠️ 部署與設定指南

### 1. 申請 LINE 官方帳號
- 前往 [LINE Developers](https://developers.line.biz/) 建立新的 Provider 與 Channel (選擇 Messaging API)。
- 在 Channel settings 取得 **Channel Access Token** 與 **Channel Secret**。
- 關閉官方帳號管理後台的「自動回應訊息」，並啟用 Webhook。

### 2. 部署到 Render 雲端平台
- 將此專案上傳至 GitHub（可以透過網頁介面的 "Upload files" 或使用 git 指令）。
- 登入 [Render](https://render.com/)，建立一個新的 **Web Service**，並綁定剛建立的 GitHub Repo。
- 設定 Environment Variables (環境變數)：
  - `LINE_CHANNEL_ACCESS_TOKEN` = 你的 Token
  - `LINE_CHANNEL_SECRET` = 你的 Secret
- 部署成功後，將 Render 提供的專屬網址加上 `/callback`（例如：`https://你的專案.onrender.com/callback`），填入 LINE Developers 的 Webhook URL 並點擊 Verify。

### 3. 設定 24 小時不休眠 (UptimeRobot)
- 由於 Render 的免費方案在閒置 15 分鐘後會進入休眠，導致 LINE 機器人第一次回覆會超時。
- 請到 [UptimeRobot](https://uptimerobot.com/) 註冊免費帳號。
- 建立一個新的 HTTP(s) Monitor，目標為你的 Render 網址（結尾**不加** `/callback`）。
- 設定每 5~10 分鐘檢查一次，機器人就會永遠保持上線狀態。

---

## 💡 後續新增功能建議 (Future Work)

如果你未來想繼續擴充這個專案，以下幾個方向會讓機器人變得更強大：

1. **圖文選單 (Rich Menu)**：
   在 LINE 加上圖文選單，把常見的「葉菜類」、「根莖類」、「當季水果」做成按鈕，使用者點擊就能直接查價，不用自己打字。

2. **走勢圖表直接傳到 LINE**：
   twfood.cc 其實有提供一整年的價格折線圖。未來可透過 Python 的 `matplotlib` 套件把半年的走勢畫成圖片，直接傳送圖片到 LINE 裡面，看趨勢更明顯。

3. **花卉行情查詢**：
   目前只針對 `/vege` (蔬菜) 和 `/fruit` (水果) 進行查詢。未來可以擴展搜尋範圍，連 `/flower` (花卉) 的拍賣價格也能一併整合進來。
