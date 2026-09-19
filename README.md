# 📊 Advanced Student Analytics Portal (學生學習深度分析系統)

Welcome to the Advanced Student Analytics Portal! This project is a Streamlit-based web application designed to help teachers, students, and parents easily track and analyze academic performance. 

By replacing complex spreadsheets with an interactive, visual dashboard, this tool empowers educators to make data-driven decisions and helps students understand their learning progress.

---

## ✨ Features

* **🎓 Student/Parent Dashboard:** Secure login for students to view their personal performance, including Z-scores, PR values, and historical trends.
* **🕸️ Interactive Visualizations:** Automatically generates Radar Charts, Box Plots, Grouped Bar Charts, and Score Distribution Charts.
* **👨‍🏫 Teacher Admin Panel:** A secure portal for teachers to view class overviews, track student progress/regression between exams, and bulk-download personalized HTML report cards for the entire class.
* **☁️ Cloud-Based:** Powered by Streamlit and Google Sheets, meaning no software installation is required for users.

---

## 🏗️ Project Architecture

Our application follows a modular architecture for maintainability and clean code organization:

* **`app.py`**: The main entry point that routes traffic and initializes the Streamlit application.
* **`core/`**: Core utilities and data management.
  * `data_loader.py`: Connects to Google Sheets, loads the DataFrame, and parses exams.
  * `auth.py`: Encapsulates login logic and session state initialization.
* **`reports/`**: 
  * `html_generator.py`: Contains the logic for bulk HTML report generation and Plotly charts.
* **`views/`**: Streamlit UI pages.
  * `admin.py`: The Teacher Admin Panel tabs.
  * `dashboard.py`: The Student and Class Overview Dashboard tabs.

---

## 🚀 Step-by-Step Deployment Guide for Teachers

If you are a teacher with no programming background, don't worry! You can set up your own version of this system by following these four phases.

### Phase 1: Prepare Your Database (Google Sheets)
1. Create a new Google Sheet and name it exactly `School_Master_Score`.
2. Create columns for `StudentID`, `Name`, and `Pin` (password).
3. Add your exam columns using this exact naming format: `AcademicYear_Semester_Type_Number_{Subject & Grade Metrics}_{Detail}` 
   * *Example:* `115_1_E_1_{國文}_{分數}`
   * {Subject & Grade Metrics}:
   {國文Chienese}{英文English}{數學Math}{社會Sociology}{生物Biology}{理化Physics&Chemistry}
   {總分TotalScore}{平均Average}{班排ClassRank}{校排schoolRank}
   * {Detail}: your_Note/Remarks*Example:*取消Cancel、延期Postpone / Delay
   

### Phase 2: Get Your API Keys (Google Cloud)
1. Go to the [Google Cloud Console](https://console.cloud.google.com/) and sign in with your Google account.
2. Click **Create Project**.
3. Search for and enable the **Google Sheets API** and the **Google Drive API**.
4. Go to **Credentials** -> **Create Credentials** -> **Service Account**. Name it something like "score-reader".
5. Click on your new Service Account, go to the **Keys** tab, click **Add Key**, and choose **JSON**. This will download a file to your computer.
6. **CRITICAL:** Open the downloaded JSON file, find the `client_email` address, copy it, and share your `School_Master_Score` Google Sheet with that email address (give it "Viewer" or "Editor" access).

### Phase 3: Upload to the Cloud (GitHub)
1. Create a free account on [GitHub](https://github.com/).
2. Create a **New Repository** (name it something like `student-score-portal`) and make it Public.
3. Click **Upload files** and drag-and-drop the following folders and files into your repository:
   * `app.py` (The main program orchestrator)
   * `core/` folder (Contains data loading and authentication logic)
   * `views/` folder (Contains UI dashboards for admins and students)
   * `reports/` folder (Contains report generation logic)
   * `requirements.txt` (Tells the server what tools to install)
   * `.gitignore` (Keeps your passwords safe)
4. Click **Commit changes** to save.

### Phase 4: Launch Your Website (Streamlit)
1. Go to [Streamlit Community Cloud](https://share.streamlit.io/) and log in using your GitHub account.
2. Click **New app**.
3. Select your repository, the `main` branch, and type `app.py` as the Main file path.
4. **CRITICAL:** Before clicking Deploy, click **Advanced settings...**. In the **Secrets** box, paste your passwords and your Google JSON data in this exact format:

```toml
[teacher]
pin = "your_teacher_password_here"

[virtual]
pin = "your_demo_password_here"#(This account just presents simple static data. You can use it as a demo account.)

[gcp_service_account]
type = "service_account"
project_id = "paste_from_json"
private_key_id = "paste_from_json"
private_key = "paste_from_json"
client_email = "paste_from_json"
client_id = "paste_from_json"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "paste_from_json"
universe_domain = "googleapis.com"
```

---

## 🎯 國中教育會考模擬考 (Mock Exam) 模組

系統現已支援完整的會考模擬考（第一次、第二次、第三次、第四次...）成績查詢與深度學習診斷分析！

### 核心功能

1. **學生與家長儀表板 (`views/mock_dashboard.py`)**：
   * **總體落點與會考標示**：即時顯示五科總積分（35分制）、標示組合（如 `1A++,2A+,1B++,1B`）、班級排名、全校排名（含校排前 % 與 PR）、基北區全區排名參考。
   * **五科能力雷達圖與長條對比**：直觀比對「學生得分 vs 班級平均 vs 全校平均」。
   * **總積分常模累積百分比曲線**：清晰掌握自己在班級、全校與全區常模中所處的競爭力階梯。
   * **弱項診斷與晉級突破點**：精準計算「距離晉升下一標示等級之題數或分數差距」（如：國文僅差 1 題即可晉級 A 精熟），給予正向、具體的複習指引。
   * **題目作答與知識點追蹤**：逐題呈現錯題明細、評量目標、學習內容主題、個人選答、正確答案及班級與全校答對率。
   * **定期評量 vs 模擬考綜合對比**：採用統計標準化指標（百分等級 PR、Z-score）對比平常段考與大範圍模考適應力，分析學生屬於「平穩優勢」、「模擬考突出」或「段考優於模考」。
   * **歷次模擬考趨勢追蹤**：跨次比對第一次 ➔ 第二次 ➔ 第三次模考成長軌跡。

2. **教師管理決策後台 (`views/mock_admin.py`)**：
   * **班級常模統計**：五科平均積分、中位數、標準差、最高/最低分及該科在全校之班排名。
   * **能力等級分布**：5A、4A1B 等標示組合全班/全校/全區佔比，以及各科 A/B/C 三等級堆疊長條圖。
   * **全班成績總表與匯出**：依班排名排序之全班完整名冊，支援一鍵匯出 UTF-8-SIG 編碼之 CSV 報表。
   * **學生個別深度診斷**：教師可選取任一學生檢視其完整錯題知識點與雷達圖（學生端則受到嚴密權限隔離，絕無跨生存取可能）。
   * **試題弱項與教學指引**：自動篩選全班答對率落後全校達 5% 以上之試題與知識點，輔助任課教師精準安排補強教學。

---

---

## ☁️ 雲端架構與 Google Sheets 整合 (Cloud & Google Sheets Integration)

正式環境部署（Streamlit Cloud / 線上主機）不依賴本地檔案系統，所有正式成績與常模均統一存儲於 Google 試算表 `School_Master_Score`：

### 1. 關聯式工作表架構 (Relational Worksheets)
系統自動維護 5 張結構化工作表（具備 `SchemaVersion=1` 與 `ExamID` 關聯鍵）：
* **`MockExam_Index`**：考試基本資訊（代號、名稱、測驗日期、班級/全校/全區母體人數、作文狀態）。
* **`MockExam_Results`**：學生總體落點（學號、姓名、總積分、標示組合、班/校/區排名、PR值、優劣勢診斷標籤）。
* **`MockExam_Subjects`**：各科細項指標（答對題數、加權分數、換算積分、能力等級 A++~C、晉級差距題數、校班平均差、非選/聽力細項）。
* **`MockExam_Questions`**：個別錯題知識點診斷（題號、學生選答、正確答案、學習領域、知識點、評量目標、班校答對率）。
* **`MockExam_Benchmarks`**：官方常模母體基準（五科平均積分、等級組合分布、積分累積百分等級曲線、班級共同弱項題清單）。

> [!NOTE]
> 系統具備智慧快取與離線回退機制：平時優先由 Google Sheets 即時讀取；若處於本機離線開發或工作表尚未建立時，系統將自動回退使用 `data/mock_exams/` 本地快取。

### 2. Google Service Account 權限設定 (必要步驟)
* 本系統透過 `.streamlit/secrets.toml` 中的 GCP 服務帳號進行授權：
  * **Service Account Email**：`school-api@student-score-portal.iam.gserviceaccount.com`
* **重要權限需求**：
  * 原有定期評量僅需「檢視者」(Viewer) 權限。
  * **匯入模擬考成績至雲端試算表時，必須將試算表設定為「編輯者」(Editor)**：
    1. 開啟 [School_Master_Score 試算表](https://docs.google.com/spreadsheets/d/1wlVD_J3ZPP94BqpgNqvAgsBqPsvNyRW4YtZ9fVu83Ak/edit)。
    2. 點擊右上角「共用」(Share)。
    3. 將 `school-api@student-score-portal.iam.gserviceaccount.com` 的權限由「檢視者」改為「**編輯者**」(Editor) 並儲存。

---

## 📥 如何匯入模擬考資料 (Import Pipeline)

本系統具備標準化自動匯入管線，未來收到「第二次模擬考」、「第三次模擬考」時，無需修改任何程式碼即可快速匯入。

### 1. 支援的廠商報表格式
將廠商匯出的 Excel 檔案放置於同一資料夾中（支援 `.xls` 與 `.xlsx`）：
* `RN201` 或 `RN202`：班級能力等級成績總表（學生基本成績、各科題數、標示、積分、排名）
* `RN204`：班級學生各科知識點作答分析表（題目層級作答、晉級差距、知識點主題與評量目標）
* `RN205`：班級成績統計總表（班級/校/區常模平均、5A等級分布、總積分累積百分比）
* `RN207`：班級各科試題選項分析表（各題選答率、正確答案、鑑別度）
* `RN208`：班級學生數學非選成績統計表（非選第1題、第2題得分與級分）

### 2. 執行匯入指令

#### 預覽驗證 (Dry-run, 不寫入檔案與雲端)：
```bash
conda run -n school_app python import_mock_exam.py \
    --data-dir "/path/to/MockTest_1" \
    --dry-run
```

#### 本地匯入並同步上傳至 Google Sheets：
```bash
conda run -n school_app python import_mock_exam.py \
    --data-dir "/path/to/MockTest_1" \
    --upload-google-sheets
```

#### 未來匯入第二次模擬考範例：
```bash
conda run -n school_app python import_mock_exam.py \
    --data-dir "/Users/tzu-hsiukao/Documents/A_Work/E_SchoolMain/115_YSJH_Homeroom/data/MockTest_2" \
    --exam-id "mock_115_2" \
    --upload-google-sheets
```

### 3. 自動化校驗與正規化流程
匯入管線會自動執行：
1. **名冊自動關聯**：比對班級、座號、姓名，並連線至 Google Sheet 自動解析帶入 `StudentID` 與登入 `Pin`。
2. **數據正確性雙向校驗**：由底層學生作答數據獨立反推班級平均與總積分，並與 `RN205` 官方常模比對，若有異常立即告警。
3. **晉級差距運算**：自動提取國英數社自晉級下一標示門檻所需題數或分數。
4. **弱項題篩選**：自動比對全班各題答對率 vs 校平均答對率，標記落後 5% 以上之考題。
5. **冪等性同步 (Idempotent Sync)**：更新指定 `ExamID` 時僅抽換該次考試資料，絕不影響原有定期評量 `ScoreRecord.xls` 或其他模考紀錄。

---

## 🔒 隱私與安全機制 (Privacy & Security)

1. **未成年學生個資保護**：
   * 所有包含學生姓名、學號的原始檔與匯入產物（`*.csv`, `*.xlsx`, `*.json`, `*.html`）均已設定於 `.gitignore`，嚴禁提交至 GitHub。
2. **權限隔離（嚴格以身分證驗證）**：
   * 學生登入後，前端所有查詢均嚴格鎖定於 `st.session_state.student_data['StudentID']`，學生**絕不可能**透過修改 URL 參數或下拉選單存取他人成績與錯題。
   * 教師後台專用 PIN 碼獨立存放於 `.streamlit/secrets.toml`，唯有教師權限方可存取全班總表及個別學生檢視器。

---

## 🛠️ 開發與測試指令 (Development & Testing)

本專案使用 Conda 環境：`school_app`

```bash
# 1. 啟動環境
conda activate school_app

# 2. 執行自動化測試 (包含模擬考校驗、常模驗證、安全性測試與向後相容性)
pytest tests/ -v

# 3. 本地啟動網頁應用程式
streamlit run app.py
```