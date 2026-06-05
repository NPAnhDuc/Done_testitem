import streamlit as st
import pandas as pd
import google.generativeai as genai
import json
import os
import requests
import re
import io
from requests.auth import HTTPBasicAuth
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
from datetime import datetime
from dotenv import load_dotenv

# Xác định đường dẫn gốc của script để đảm bảo tìm đúng các file cấu hình và dữ liệu
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

# ====================== CONFIG ======================
st.set_page_config(
    page_title="QCD_tool",
    page_icon="🛠️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ====================== CUSTOM CSS ======================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stApp { background-color: #f1f5f9; color: #1e293b; }
    .main-header { 
        font-size: 32px; font-weight: 800; 
        background: linear-gradient(90deg, #1e40af, #3b82f6, #6366f1);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        margin-bottom: 8px; letter-spacing: -1.5px; 
    }
    .sub-header { font-size: 15px; color: #475569; margin-bottom: 32px; font-weight: 500; }
    .stButton>button { 
        width: 100%; border-radius: 10px; font-weight: 700; height: 48px; 
        background: linear-gradient(90deg, #2563eb, #3b82f6); color: white; border: none;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); box-shadow: 0 4px 6px -1px rgba(37, 99, 235, 0.2);
    }
    .stButton>button:hover { transform: translateY(-2px); box-shadow: 0 10px 15px -3px rgba(59, 130, 246, 0.3); color: white; }
    .metric-card { 
        background: white; padding: 22px; border-radius: 16px; text-align: left; 
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); border-left: 5px solid #3b82f6;
        border-right: 1px solid #e2e8f0; border-top: 1px solid #e2e8f0; border-bottom: 1px solid #e2e8f0;
        transition: all 0.2s;
    }
    .metric-card:hover { transform: translateY(-3px); box-shadow: 0 12px 20px -5px rgba(0,0,0,0.1); }
    .metric-num { font-size: 32px; font-weight: 800; color: #0f172a; line-height: 1; }
    .metric-label { font-size: 11px; color: #64748b; text-transform: uppercase; font-weight: 700; letter-spacing: 1px; margin-bottom: 6px; }
    .stTabs [data-baseweb="tab-list"] { background-color: #f1f5f9; padding: 6px; border-radius: 12px; }
    .stTabs [data-baseweb="tab"] { border-radius: 8px; color: #475569; font-weight: 600; }
    .stTabs [aria-selected="true"] { background-color: white !important; box-shadow: 0 2px 4px rgba(0,0,0,0.05); color: #2563eb !important; }
    [data-testid="stDataFrame"] { background-color: white; padding: 10px; border-radius: 10px; border: 1px solid #e2e8f0; }
    [data-testid="stSidebar"] { background-color: #0f172a; border-right: 1px solid #1e293b; }
    [data-testid="stSidebar"] label, [data-testid="stSidebar"] .stMarkdown p,
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 { 
        color: #f8fafc !important; 
    }
    [data-testid="stSidebar"] section[data-testid="stFileUploadDropzone"] {
        background-color: #dbeafe !important;
        border: 2px dashed #2563eb !important;
        border-radius: 12px !important;
    }
    [data-testid="stSidebar"] [data-testid="stFileUploadDropzoneInstructions"] div,
    [data-testid="stSidebar"] [data-testid="stFileUploadDropzoneInstructions"] span,
    [data-testid="stSidebar"] [data-testid="stFileUploadDropzoneInstructions"] small { 
        color: #000000 !important;
        font-weight: 600 !important;
    }
    .stTextInput>div>div>input, .stSelectbox>div>div, .stTextArea>div>div>textarea, .stDateInput>div>div>input {
        background-color: #e0f2fe !important;
        color: #0f172a !important;
        border: 1px solid #bfdbfe !important;
        border-radius: 8px !important;
        font-weight: 500;
    }
    .stTextInput>div>div>input:focus, .stSelectbox>div>div:focus, .stTextArea>div>div>textarea:focus {
        border-color: #3b82f6 !important;
        box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2) !important;
        background-color: #ffffff !important;
    }
    .mandatory { color: #f43f5e; font-weight: 700; }
    .section-header { background: #eff6ff; padding: 10px 16px; border-radius: 8px; color: #1d4ed8; font-weight: 700; font-size: 14px; margin: 15px 0; border-left: 4px solid #3b82f6; }
    .stMain p, .stMain label, .stMain span:not(.metric-label) { color: #334155; }
</style>
""", unsafe_allow_html=True)

st.markdown('<h1 class="main-header">️ QCD_tool — Quản Lý Chất Lượng Hệ Thống</h1>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Jira Integration • AI-Powered Testing • Smart Analysis</p>', unsafe_allow_html=True)

# ====================== CẤU HÌNH TRUY CẬP ======================
with st.sidebar:
    st.markdown("### ⚙️ System Status")
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    jira_token = os.getenv("JIRA_API_TOKEN", "").strip()
    jira_url_env = os.getenv("JIRA_URL", "").strip()

    if not gemini_key or not jira_token or not jira_url_env:
        st.error("❌ Thiếu thông tin cấu hình (Jira URL/Token/Gemini Key) trong file .env!")
        st.stop()
    st.success("✅ API Keys loaded from .env")

# ====================== GEMINI SETUP ======================
def get_best_generation_model() -> str:
    """Tìm model Gemini khả dụng nhất."""
    try:
        available_models = [
            m.name for m in genai.list_models()
            if "generateContent" in m.supported_generation_methods
        ]
        for preferred in ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash-exp"]:
            if f"models/{preferred}" in available_models: return f"models/{preferred}"
            if preferred in available_models: return preferred
        return available_models[0] if available_models else "gemini-1.5-flash"
    except:
        return "gemini-1.5-flash"

genai.configure(api_key=gemini_key)
os.environ["GOOGLE_API_KEY"] = gemini_key

model = genai.GenerativeModel(
    get_best_generation_model(),
    generation_config={
        "temperature": 0,
        "response_mime_type": "application/json",
        "max_output_tokens": 8192,
    }
)

# ====================== JIRA CONFIG ======================
JIRA_URL      = os.getenv("JIRA_URL", "").rstrip("/")
JIRA_USERNAME = os.getenv("JIRA_USERNAME", "")
JIRA_PROJECT  = os.getenv("JIRA_PROJECT_KEY", "")

# ====================== SETUP SESSION VỚI RETRY ======================
def create_jira_session():
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=2, status_forcelist=[500, 502, 503, 504], raise_on_status=False)
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({
        "Authorization": f"Bearer {jira_token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })
    return session

jira_session = create_jira_session()

# ====================== PATH CONFIG ======================
TEST_DIR        = os.path.join(BASE_DIR, "test")
TEMPLATE_PATH   = os.getenv("TEMPLATE_PATH", os.path.join(TEST_DIR, "Test_Data_Structure_V3.xlsx"))
TRAIN_DATA_PATH = os.getenv("TRAIN_DATA_PATH", os.path.join(TEST_DIR, "Data_train.xlsx"))
MUC_TXT_PATH    = os.getenv("MUC_TXT_PATH", os.path.join(BASE_DIR, "muc.txt"))
DEPT_FILE_PATH  = os.getenv("DEPT_FILE_PATH", os.path.join(TEST_DIR, "Source of Issue.txt"))
DEPT_SCOPE_PATH = os.getenv("DEPT_SCOPE_PATH", os.path.join(BASE_DIR, "Department_Testing_Scope.xlsx"))

# ====================== HÀM HỖ TRỢ ======================
def parse_muc_config(file_path):
    config = {}
    if not os.path.exists(file_path):
        return config
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        matches = re.findall(r'([^=\n]+?)\s*=\s*"(.*?)"', content, re.DOTALL)
        for key, value in matches:
            key = key.strip()
            lines = [l.strip() for l in value.split('\n') if l.strip()]
            if not lines:
                config[key] = ""
            elif "Date" in lines[0]:
                config[key] = "DATE_TYPE"
            else:
                config[key] = lines
        return config
    except Exception as e:
        st.error(f"Lỗi đọc file muc.txt: {e}")
        return {}

MUC_CONFIG = parse_muc_config(MUC_TXT_PATH)

def get_template_headers():
    default_headers = [
        "Project", "Test Item", "Description", "PIC", "Label", "MasterTest", "Department",
        "Category", "Domain", "Original FIP", "Total TCs", "Apply Test",
        "Current FIP", "Other Ref"
    ]
    if os.path.exists(TEMPLATE_PATH):
        try:
            df_temp = pd.read_excel(TEMPLATE_PATH, nrows=0)
            if not df_temp.columns.empty:
                return list(df_temp.columns)
        except Exception as e:
            st.warning(f"⚠️ Không thể đọc header từ template: {e}. Sử dụng cột mặc định.")
    return default_headers

def extract_issue_keys(input_str: str) -> list:
    return list(dict.fromkeys(re.findall(r'([A-Z][A-Z0-9]+-[0-9]+)', input_str)))

def clean_cell_value(v):
    """Đảm bảo giá trị ô dữ liệu luôn là kiểu đơn giản (string/number), tránh lỗi unhashable dict."""
    if v is None:
        return ""
    if isinstance(v, (str, int, float, bool)):
        return v
    return str(v)

def fetch_single_jira_issue(issue_key: str):
    url = f"{JIRA_URL}/rest/api/2/issue/{issue_key}"
    resp = jira_session.get(url, verify=False, timeout=120)
    if resp.status_code == 200:
        return resp.json()
    elif resp.status_code == 404:
        raise Exception(f"❌ Không tìm thấy Issue: {issue_key}")
    raise Exception(f"❌ Lỗi Jira API {resp.status_code}: {resp.text[:200]}")

def get_jira_field_metadata():
    try:
        resp = jira_session.get(f"{JIRA_URL}/rest/api/2/field", verify=False, timeout=60)
        if resp.status_code == 200:
            return {f["name"].lower(): {"id": f["id"], "type": f.get("schema", {}).get("type", "string")} for f in resp.json()}
    except:
        pass
    return {}

def get_jira_all_fields():
    try:
        resp = jira_session.get(f"{JIRA_URL}/rest/api/2/field", verify=False, timeout=60)
        if resp.status_code == 200:
            return [{"id": f["id"], "name": f["name"]} for f in resp.json()]
    except:
        pass
    return []

def build_jira_payload(manual_data: dict, field_meta: dict):
    fields_payload = {}
    system_map = {
        "summary": "summary", "test item": "summary", "description": "description",
        "priority": "priority", "labels": "labels", "assignee": "assignee",
        "pic": "assignee", "project": "project", "issue type": "issuetype",
        "security level": "security", "resolution": "resolution"
    }
    for config_key, val in manual_data.items():
        val_str_raw = str(val).strip()
        if not val_str_raw or val_str_raw.lower() in ["nan", "none", "null"]:
            continue
        clean_key = config_key.replace("*", "").strip().lower()
        field_info = field_meta.get(clean_key)
        target_id = system_map.get(clean_key) or (field_info["id"] if field_info else None)
        if not target_id:
            continue
        field_type = field_info["type"] if field_info else "string"
        if target_id in ["summary", "description"]:
            fields_payload[target_id] = str(val)
        elif target_id in ["priority", "security", "resolution", "issuetype"]:
            fields_payload[target_id] = {"name": str(val)}
        elif target_id == "assignee":
            fields_payload[target_id] = {"name": str(val)}
        elif target_id == "project":
            val_str = str(val)
            project_key = val_str.split("(")[1].split(")")[0] if "(" in val_str else val_str
            fields_payload["project"] = {"key": project_key}
        elif target_id == "labels":
            fields_payload[target_id] = [l.strip() for l in str(val).replace(",", " ").split() if l.strip()]
        elif field_type == "number":
            try:
                fields_payload[target_id] = float(str(val).replace(',', '').strip())
            except:
                pass
        elif field_type == "option":
            fields_payload[target_id] = {"value": str(val)}
        elif field_type == "array":
            fields_payload[target_id] = [str(val)]
        elif field_type == "user":
            fields_payload[target_id] = {"name": str(val)}
        else:
            fields_payload[target_id] = str(val)
    return fields_payload

def get_metric_card(label, value, color="#3b82f6", bg_gradient=""):
    bg_style = f"background: {bg_gradient};" if bg_gradient else ""
    return f"""
    <div class="metric-card" style="border-left-color: {color}; {bg_style}">
        <div class="metric-label">{label}</div>
        <div class="metric-num" style="color: {color}">{value}</div>
    </div>"""

def create_jira_issue(manual_data: dict):
    field_meta = get_jira_field_metadata()
    fields = build_jira_payload(manual_data, field_meta)
    if "project" not in fields:
        fields["project"] = {"key": "EMT"}
    if "issuetype" not in fields:
        fields["issuetype"] = {"name": "Test Item"}
    resp = jira_session.post(f"{JIRA_URL}/rest/api/2/issue", json={"fields": fields}, verify=False, timeout=120)
    if resp.status_code == 201:
        return resp.json()
    raise Exception(f"❌ Lỗi tạo Jira: {resp.status_code} - {resp.text}")

def update_jira_issue(issue_key: str, manual_data: dict):
    field_meta = get_jira_field_metadata()
    payload = {"fields": build_jira_payload(manual_data, field_meta)}
    resp = jira_session.put(f"{JIRA_URL}/rest/api/2/issue/{issue_key}", json=payload, verify=False, timeout=120)
    if resp.status_code == 204:
        return True
    raise Exception(f"❌ Lỗi cập nhật Jira: {resp.status_code} - {resp.text}")

def delete_jira_issue(issue_key: str):
    resp = jira_session.delete(f"{JIRA_URL}/rest/api/2/issue/{issue_key}", verify=False, timeout=120)
    if resp.status_code == 204:
        return True
    raise Exception(f"❌ Lỗi xóa Jira: {resp.status_code} - {resp.text}")

def process_jira_with_ai(jira_issues: list, columns: list):
    try:
        dept_context = ""
        if os.path.exists(DEPT_SCOPE_PATH):
            try:
                df_scope = pd.read_excel(DEPT_SCOPE_PATH)
                dept_context = f"Dưới đây là bảng quy định phạm vi kiểm thử (Scope) và Department tương ứng, hãy dựa vào đây để phân loại:\n{df_scope.to_string(index=False)}"
            except Exception as e:
                st.warning(f"⚠️ Lỗi đọc file Department Scope: {e}")

        dept_instruction = f"- Cột 'Department': Phải dựa trên logic và bảng phân loại Scope cung cấp dưới đây để chọn giá trị đúng.\n{dept_context}"

        prompt = f"""Bạn là chuyên gia phân tích dữ liệu kiểm thử phần mềm.

Nhiệm vụ: Với mỗi Jira Issue bên dưới, hãy trích xuất thông tin và điền vào các cột sau:
{columns}

CÁCH TRÍCH XUẤT:
- Đọc toàn bộ 'summary' và 'description' của mỗi issue
- Mỗi issue tạo ra ÍT NHẤT 1 dòng kết quả
- Nếu description có nhiều test item/bug fix riêng biệt → tạo nhiều dòng
- Tìm các dòng có mã tham chiếu (CCB-xxxxx, LIMO-xxxxx, LTM-xxxxx...) và dùng làm nội dung
- Nếu không có mã tham chiếu → dùng summary làm nội dung chính
- {dept_instruction}
- Cột 'Key' hoặc tương đương: điền key của issue gốc (ví dụ VF6LHD-41707)

Trả về JSON list thuần, không markdown:
[
  {{ "<col1>": "...", "<col2>": "...", ... }},
  ...
]

DỮ LIỆU JIRA:
{json.dumps(jira_issues, ensure_ascii=False)}"""

        response = model.generate_content(prompt)
        text = response.text.strip()

        clean_text = text
        if "```json" in clean_text:
            clean_text = clean_text.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_text:
            clean_text = clean_text.split("```")[1].split("```")[0].strip()

        try:
            result = json.loads(clean_text)
        except json.JSONDecodeError:
            last_close = clean_text.rfind('}')
            if last_close != -1:
                truncated = clean_text[:last_close + 1]
                if not truncated.strip().startswith('['):
                    truncated = '[' + truncated
                if not truncated.strip().endswith(']'):
                    truncated += ']'
                try:
                    result = json.loads(truncated)
                except:
                    result = []
            else:
                result = []

        return result if isinstance(result, list) else []
    except Exception as e:
        st.error(f"❌ process_jira_with_ai lỗi: {e}")
        return []

# ====================== SIDEBAR ======================
st.sidebar.header("⚙️ Cấu hình")

menu = "Tạo Test Item"
st.sidebar.info("🚀 Chức năng: Tạo Test Item")

st.sidebar.markdown("---")

st.sidebar.markdown("🔍 **Công cụ tìm Field ID**")
if st.sidebar.button("📋 Liệt kê tất cả Jira Fields"):
    fields_list = get_jira_all_fields()
    if fields_list:
        st.sidebar.write("ID hỗ trợ cấu hình:")
        st.sidebar.dataframe(pd.DataFrame(fields_list), height=200)
st.sidebar.markdown("---")

if menu == "Tạo Test Item":
    tab_extract, tab_update, tab_manual, tab_delete = st.tabs(
        ["🔍 Trích xuất từ Jira", "🔧 Cập nhật Test Item", "📝 Tạo thủ công (muc.txt)", "🗑️ Xóa Test Item"]
    )

    with tab_extract:
        st.markdown("Dán đường link Jira để lấy thông tin và định dạng thành bảng.")
        jira_input       = st.text_area("Jira Issue Links hoặc Keys", placeholder="VFM-591822", height=150)
        include_subtasks = st.checkbox("Tự động lấy Sub-tasks", value=True)

        if st.button("🚀 Trích xuất dữ liệu", type="primary"):
            input_keys = extract_issue_keys(jira_input)
            if not input_keys:
                st.error("❌ Không tìm thấy mã Issue nào hợp lệ.")
            else:
                jira_data_to_ai = []
                processed_keys  = set()
                headers         = get_template_headers()
                with st.spinner(f"⏳ Đang xử lý {len(input_keys)} Issue..."):
                    try:
                        for key in input_keys:
                            if key in processed_keys:
                                continue
                            main_issue = fetch_single_jira_issue(key)
                            issues_to_process = [main_issue]
                            if include_subtasks:
                                for stak in main_issue.get("fields", {}).get("subtasks", []):
                                    issues_to_process.append(fetch_single_jira_issue(stak['key']))
                            for iss in issues_to_process:
                                if iss.get("key") not in processed_keys:
                                    desc = iss.get("fields", {}).get("description", "") or ""
                                    jira_data_to_ai.append({
                                        "key":         iss.get("key"),
                                        "summary":     iss.get("fields", {}).get("summary", ""),
                                        "description": str(desc)[:1500],
                                    })
                                    processed_keys.add(iss.get("key"))
                        final_results = process_jira_with_ai(jira_data_to_ai, headers)
                        st.session_state.extracted_df      = pd.DataFrame(final_results)
                        st.session_state.orig_keys_count   = len(input_keys)
                    except Exception as e:
                        st.error(str(e))

        if "extracted_df" in st.session_state:
            st.markdown("### 📊 Kết quả trích xuất")
            c1, c2, c3 = st.columns(3)
            c1.markdown(get_metric_card("Tổng số dòng", len(st.session_state.extracted_df), "#6366f1", "linear-gradient(135deg, #eef2ff 0%, #ffffff 100%)"), unsafe_allow_html=True)
            c2.markdown(get_metric_card("Số Issue gốc", st.session_state.orig_keys_count,   "#8b5cf6", "linear-gradient(135deg, #f5f3ff 0%, #ffffff 100%)"), unsafe_allow_html=True)
            c3.markdown(get_metric_card("Trạng thái",   "Sẵn sàng ✨",                       "#10b981", "linear-gradient(135deg, #f0fdf4 0%, #ffffff 100%)"), unsafe_allow_html=True)

            output_df = st.data_editor(st.session_state.extracted_df, use_container_width=True, num_rows="dynamic")
            col_web, col_local = st.columns(2)
            with col_web:
                buffer = io.BytesIO()
                output_df.to_excel(buffer, index=False)
                st.download_button("📥 Tải file Excel", buffer.getvalue(), "jira_data.xlsx", use_container_width=True)
            with col_local:
                if st.button("💾 Cập nhật Data_train.xlsx", type="primary", use_container_width=True):
                    try:
                        old_df = pd.read_excel(TRAIN_DATA_PATH) if os.path.exists(TRAIN_DATA_PATH) else pd.DataFrame()
                        pd.concat([old_df, output_df], ignore_index=True).to_excel(TRAIN_DATA_PATH, index=False)
                        st.success("✅ Đã lưu thành công!")
                    except:
                        st.error("❌ Lỗi: Hãy đóng file Data_train.xlsx trước.")

    with tab_update:
        update_mode = st.radio("Chế độ cập nhật:", ["Cập nhật 1 item", "Cập nhật hàng loạt (Bulk Update)"], horizontal=True)
        if update_mode == "Cập nhật 1 item":
            col_in, col_btn = st.columns([4, 1])
            update_input = col_in.text_input("Mã hoặc Link Issue Jira", placeholder="EMT-123")
            if col_btn.button("🔍 Load Thông tin", use_container_width=True) and update_input:
                keys = extract_issue_keys(update_input)
                if keys:
                    try:
                        st.session_state.u_data = fetch_single_jira_issue(keys[0])
                        st.session_state.u_key  = keys[0]
                    except Exception as e:
                        st.error(str(e))
            if "u_data" in st.session_state:
                with st.form("u_form"):
                    st.markdown(f"#### Chỉnh sửa Issue: **{st.session_state.u_key}**")
                    u_manual = {}
                    cols = st.columns(2)
                    f    = st.session_state.u_data.get("fields", {})
                    for i, (k, v) in enumerate(MUC_CONFIG.items()):
                        clean = k.replace("*", "").lower()
                        cur   = f.get(clean, "") if clean in ["summary", "description"] else ""
                        if isinstance(v, list):
                            u_manual[k] = cols[i % 2].selectbox(k, v, index=v.index(cur) if cur in v else 0)
                        elif v == "DATE_TYPE":
                            u_manual[k] = cols[i % 2].date_input(k).strftime("%Y-%m-%d")
                        else:
                            u_manual[k] = cols[i % 2].text_input(k, cur)
                    if st.form_submit_button("🚀 Cập nhật Jira", type="primary"):
                        try:
                            update_jira_issue(st.session_state.u_key, u_manual)
                            st.success("✅ Thành công!")
                        except Exception as e:
                            st.error(str(e))
        else:
            u_file = st.file_uploader("Chọn file Excel để cập nhật", type=["xlsx"])
            if u_file:
                df_up = pd.read_excel(u_file)
                k_col = next((c for c in df_up.columns if str(c).lower() in ['key', 'issue key']), None)
                if k_col:
                    df_up = st.data_editor(df_up, use_container_width=True)
                    if st.button("🚀 Bắt đầu cập nhật hàng loạt", type="primary"):
                        prog = st.progress(0)
                        rows = df_up.to_dict('records')
                        for i, r in enumerate(rows):
                            keys = extract_issue_keys(str(r.get(k_col, "")))
                            if keys:
                                try:
                                    update_jira_issue(keys[0], r)
                                except:
                                    pass
                            prog.progress((i + 1) / len(rows))
                        st.success("✅ Hoàn tất!")

    with tab_manual:
        manual_option = st.radio("Chọn hình thức tạo:", ["Tạo 1 item thủ công", "Tạo nhiều item (Import file)"], horizontal=True)
        if manual_option == "Tạo 1 item thủ công":
            if not MUC_CONFIG:
                st.warning(f"⚠️ Không tìm thấy cấu hình trong file: `{MUC_TXT_PATH}`. Vui lòng kiểm tra lại file cấu hình.")
            else:
                with st.form("m_form"):
                    m_data = {}
                    cols   = st.columns(2)
                    for i, (k, v) in enumerate(MUC_CONFIG.items()):
                        if isinstance(v, list):
                            m_data[k] = cols[i % 2].selectbox(k, v)
                        elif v == "DATE_TYPE":
                            m_data[k] = cols[i % 2].date_input(k).strftime("%Y-%m-%d")
                        else:
                            m_data[k] = cols[i % 2].text_input(k, value=v if isinstance(v, str) else "")
                    if st.form_submit_button("🔨 Tạo Issue", type="primary"):
                        try:
                            res = create_jira_issue(m_data)
                            st.success(f"✅ Đã tạo: {res['key']}")
                        except Exception as e:
                            st.error(str(e))
        else:
            bulk_f = st.file_uploader("Upload file dữ liệu (JSON/Excel)", type=["json", "xlsx"])
            if bulk_f:
                df_b = pd.read_excel(bulk_f) if bulk_f.name.endswith('xlsx') else pd.DataFrame(json.load(bulk_f))
                validated = []
                for idx, row in df_b.iterrows():
                    row_d     = {str(k).strip(): v for k, v in row.to_dict().items()}
                    clean_row = {}
                    for ck, cv in MUC_CONFIG.items():
                        val = row_d.get(ck) or row_d.get(ck.replace("*", ""))
                        try:
                            is_na = pd.isna(val)
                        except (TypeError, ValueError):
                            is_na = False
                        if val is None or is_na:
                            if isinstance(cv, list) and cv:
                                val = cv[0]
                            elif isinstance(cv, str) and cv not in ["", "DATE_TYPE"]:
                                val = cv
                        clean_row[ck] = clean_cell_value(val) if not is_na else ""
                    validated.append(clean_row)
                final_df = st.data_editor(pd.DataFrame(validated), use_container_width=True)
                if st.button("🚀 Bắt đầu tạo Issue hàng loạt", type="primary"):
                    prog    = st.progress(0)
                    status  = st.empty()
                    results = []
                    rows    = final_df.to_dict('records')
                    for i, r in enumerate(rows):
                        sum_val = r.get("Summary*") or r.get("Summary") or ""
                        status.text(f"⏳ Đang tạo: {sum_val}")
                        try:
                            res = create_jira_issue(r)
                            results.append({"STT": i + 1, "Item": sum_val, "Link": f"{JIRA_URL}/browse/{res['key']}"})
                        except Exception as e:
                            results.append({"STT": i + 1, "Item": sum_val, "Link": f"Lỗi: {str(e)}"})
                        prog.progress((i + 1) / len(rows))
                    st.dataframe(pd.DataFrame(results), use_container_width=True)

    with tab_delete:
        st.markdown("### 🗑️ Xóa Test Item")
        d_input = st.text_area("Mã hoặc Link Issue cần xóa", height=150)
        confirm = st.checkbox("Tôi xác nhận muốn xóa vĩnh viễn")
        if st.button("🔥 Thực hiện xóa", type="primary", disabled=not confirm):
            keys = extract_issue_keys(d_input)
            if not keys:
                st.error("❌ Không tìm thấy mã Issue.")
            else:
                prog = st.progress(0)
                for i, k in enumerate(keys):
                    try:
                        delete_jira_issue(k)
                    except:
                        pass
                    prog.progress((i + 1) / len(keys))
                st.success("✅ Đã hoàn thành lệnh xóa!")