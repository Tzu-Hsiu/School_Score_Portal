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
3. Click **Upload files** and drag-and-drop the following files into your repository:
   * `app.py` (The main program code)
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
pin = "your_demo_password_here"
*(This account just presents simple static data. You can use it as a demo account.)*

[gcp_service_account]
type = "service_account"
project_id = "paste_from_json"
private_key_id = "paste_from_json"
private_key = "paste_from_json"
client_email = "paste_from_json"
client_id = "paste_from_json"
auth_uri = "[https://accounts.google.com/o/oauth2/auth](https://accounts.google.com/o/oauth2/auth)"
token_uri = "[https://oauth2.googleapis.com/token](https://oauth2.googleapis.com/token)"
auth_provider_x509_cert_url = "[https://www.googleapis.com/oauth2/v1/certs](https://www.googleapis.com/oauth2/v1/certs)"
client_x509_cert_url = "paste_from_json"
universe_domain = "googleapis.com"