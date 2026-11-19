# 台股看盤與持股分析(Streamlit)— 親友版

全部免費、不需要任何付費金鑰。資料存在雲端,學校電腦重灌也不會遺失。
登入方式:帳號 + 密碼 + 邀請碼(不需要 email)。

## 功能

| 頁面 | 登入? | 內容 |
|---|---|---|
| 個股看盤 | 不用 | 智慧走勢圖(日/週/月/5 分 K、均線、布林、MACD/KD/RSI、交叉訊號)、五檔報價(盤中 5 秒更新)、籌碼、基本資料 |
| 國際情勢 | 不用 | 全球指數/匯率/商品、走勢比較、新聞標題 |
| 個股分析 | 不用 | 技術/籌碼/基本三面資料整理(規則式、免費);登入後會多一段針對你成本與比重的說明 |
| 配息日程 | 不用 | 除權息日、股利發放日(含倒數) |
| 持股管理 | 要 | 持股紀錄、持股健康度、自選股 |

> 股東會與財報日期沒有完整可靠的免費資料,所以**不提供**。AI 付費分析已移除。

## 部署(全程用瀏覽器,學校電腦不用裝任何東西)

### 1. GitHub
建立 repository,用網頁 **Add file → Upload files** 上傳所有檔案(含 `.streamlit/config.toml`)。不要上傳任何密碼或金鑰。

### 2. Supabase(免費方案,存持股資料)
1. supabase.com 建立專案。
2. **Authentication → Sign In / Providers → Email**:**關閉 Confirm email**,按 Save(這樣註冊不需要收信)。
3. (不需要設定 SMTP,也不用改信件範本。)
4. **SQL Editor** 貼上執行:

```sql
create table holdings (
  id bigint generated always as identity primary key,
  user_id uuid not null default auth.uid() references auth.users on delete cascade,
  symbol text not null, shares numeric not null, cost numeric not null,
  note text default '', created_at timestamptz default now()
);
create table watchlist (
  id bigint generated always as identity primary key,
  user_id uuid not null default auth.uid() references auth.users on delete cascade,
  symbol text not null, created_at timestamptz default now(),
  unique (user_id, symbol)
);
alter table holdings  enable row level security;
alter table watchlist enable row level security;
create policy "own rows" on holdings  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "own rows" on watchlist for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
```
5. **Project Settings → API**:複製 `Project URL` 與 `anon public` key。

### 3. Streamlit Community Cloud
1. share.streamlit.io 用 GitHub 登入 → Create app → 選 repo,Main file 填 `app.py`。
2. **Advanced settings → Secrets**:
```toml
SUPABASE_URL = "https://xxxx.supabase.co"
SUPABASE_ANON_KEY = "eyJ..."
INVITE_CODE = "自己取一組,只給你信任的人"
FINMIND_TOKEN = ""   # 選填
```
3. Deploy。

### 只讓身邊的人用(建議)
- **邀請碼**:沒有 `INVITE_CODE` 的人無法註冊。
- **私人 App(更嚴格)**:Streamlit Cloud 可在 App 的 Share 設定把 App 設為私人,只有你邀請的 email 能打開。
- 不要把網址貼到公開社群。

## 已知限制
- 久沒人用會休眠,第一次開要等十幾秒。
- 重新整理網頁需重新登入(資料不會遺失)。
- 沒有 email,忘記密碼無法自助重設:到 Supabase 的 Authentication → Users 刪掉該帳號,請對方重新註冊(原持股資料會一併刪除)。
- 五檔來自證交所 MIS(約 5 秒延遲,非交易時段顯示最後一筆);歷史價量來自 Yahoo(盤中延遲 15–20 分鐘)。
- 籌碼、營收、EPS、股利來自 FinMind 免費額度;ETF 通常沒有營收/EPS。
- 持股健康度與個股分析都是依公開資料自動整理,不是買賣建議。
