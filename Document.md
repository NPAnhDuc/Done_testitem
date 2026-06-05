# BA Migration Note — QCD Tool
## Chuyển đổi từ Python (Streamlit) sang C# ASP.NET Core 8

> **Người ghi:** Business Analyst  
> **Ngày:** 2026-06-05  
> **Phiên bản nguồn:** `app2_cl.py` (Streamlit)  
> **Mục tiêu:** ASP.NET Core 8 Web Application (MVC hoặc Razor Pages + API)

---

## 1. Tổng quan hệ thống

**QCD_tool** là công cụ quản lý chất lượng nội bộ dành cho đội QA VinFast, tích hợp Jira và AI (Gemini) để:

- Trích xuất thông tin từ Jira Issues và định dạng lại thành bảng dữ liệu kiểm thử
- Tạo / Cập nhật / Xóa Jira Issues thủ công hoặc hàng loạt
- Dùng AI (Gemini) để phân tích, phân loại Test Item theo Department, Category
- Xuất kết quả ra file Excel, lưu vào file training data

---

## 2. Kiến trúc hiện tại (Python/Streamlit)

```
app2_cl.py
├── Config load (.env)
├── Gemini SDK (genai)
├── Jira REST API (requests + HTTPBasicAuth + Retry)
├── File config parse (muc.txt, Department_Testing_Scope.xlsx)
├── Excel I/O (pandas + openpyxl)
└── UI: 4 tabs (Streamlit)
    ├── Tab 1: Trích xuất từ Jira
    ├── Tab 2: Cập nhật Test Item
    ├── Tab 3: Tạo thủ công (muc.txt)
    └── Tab 4: Xóa Test Item
```

---

## 3. Mapping nghiệp vụ → C# Services

### 3.1 Configuration Service

**Python hiện tại:**
- Đọc `.env` bằng `python-dotenv`
- Biến: `GEMINI_API_KEY`, `JIRA_API_TOKEN`, `JIRA_URL`, `JIRA_USERNAME`, `JIRA_PROJECT_KEY`
- Validate ngay khi khởi động, dừng app nếu thiếu key

**C# tương đương:**
- Dùng `appsettings.json` + `IConfiguration` + `IOptions<T>`
- Validate bằng `DataAnnotations` hoặc `FluentValidation` trong `Program.cs`
- Nên tạo class `AppSettings` với các section: `Gemini`, `Jira`, `FilePaths`

```csharp
// appsettings.json
{
  "Jira": {
    "Url": "",
    "ApiToken": "",
    "Username": "",
    "ProjectKey": ""
  },
  "Gemini": {
    "ApiKey": ""
  }
}
```

> ⚠️ **Lưu ý:** Python dùng `Bearer Token` trong header. C# cần giữ nguyên header `Authorization: Bearer {token}` — **KHÔNG** dùng BasicAuth dù Jira có hỗ trợ cả hai, vì code Python đang dùng Bearer.

---

### 3.2 Jira HTTP Client Service (`IJiraService`)

**Nghiệp vụ:**

| Hàm Python | Endpoint Jira | Mô tả |
|---|---|---|
| `fetch_single_jira_issue(key)` | `GET /rest/api/2/issue/{key}` | Lấy thông tin 1 Issue |
| `get_jira_field_metadata()` | `GET /rest/api/2/field` | Lấy metadata tất cả fields |
| `get_jira_all_fields()` | `GET /rest/api/2/field` | Danh sách field ID + name |
| `create_jira_issue(data)` | `POST /rest/api/2/issue` | Tạo Issue mới |
| `update_jira_issue(key, data)` | `PUT /rest/api/2/issue/{key}` | Cập nhật Issue |
| `delete_jira_issue(key)` | `DELETE /rest/api/2/issue/{key}` | Xóa Issue |

**C# implementation:**
- Dùng `IHttpClientFactory` + named client `"JiraClient"`
- Cấu hình `Polly` retry policy: `3 lần`, `backoff x2`, retry các status `500/502/503/504`
- `verify=False` trong Python (bỏ qua SSL) → C# cần `HttpClientHandler` với `ServerCertificateCustomValidationCallback` nếu Jira server dùng self-signed cert
- Timeout: `120s` cho create/update/delete, `60s` cho metadata

> ⚠️ **Lưu ý SSL:** Python dùng `verify=False` — đây là môi trường Jira on-premise có thể dùng self-signed cert. Khi sang C# phải xử lý rõ ràng, không để mặc định reject.

---

### 3.3 Jira Field Mapping (`build_jira_payload`)

Đây là **logic phức tạp nhất** cần chú ý khi chuyển sang C#.

**Luồng xử lý:**
1. Nhận `Dictionary<string, object>` từ form hoặc file Excel
2. Normalize key (bỏ `*`, lowercase)
3. Map tên field người dùng nhập → Jira field ID (system fields + custom fields)
4. Tùy theo `field_type` mà build payload khác nhau:

| Field type | Jira payload format |
|---|---|
| `summary`, `description` | `"fieldId": "value"` |
| `priority`, `security`, `issuetype`, `resolution` | `"fieldId": {"name": "value"}` |
| `assignee` | `"fieldId": {"name": "username"}` |
| `project` | `"fieldId": {"key": "PROJECT_KEY"}` — parse từ `"Name (KEY)"` |
| `labels` | `"fieldId": ["label1", "label2"]` — split theo space/comma |
| `number` | `"fieldId": 123.0` — parse float |
| `option` | `"fieldId": {"value": "option_text"}` |
| `array` | `"fieldId": ["value"]` |
| `user` | `"fieldId": {"name": "username"}` |

**C# gợi ý:** Tạo `JiraFieldMapper` service, có thể dùng `Dictionary<string, Func<string, object>>` để map từng loại field.

> ⚠️ **Lưu ý project key parsing:** Python parse theo pattern `"Name (KEY)"` → tách key trong ngoặc đơn. Phải giữ nguyên logic này.

---

### 3.4 Gemini AI Service (`IGeminiService`)

**Python hiện tại:**
- Model discovery: tự động tìm model tốt nhất từ danh sách, ưu tiên `gemini-1.5-flash` → `gemini-1.5-pro` → `gemini-2.0-flash-exp`
- Config: `temperature=0`, `response_mime_type="application/json"`, `max_output_tokens=8192`
- Input: Mảng JSON gồm `{key, summary, description}` của các Jira Issues (description cắt `[:1500]` ký tự)
- Output: JSON array các dòng data theo template headers

**C# tương đương:**
- Gọi Gemini REST API (`https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`)
- Hoặc dùng NuGet: `Google.Ai.Generativelanguage`
- Parse response: bóc text từ `candidates[0].content.parts[0].text`

**Prompt logic quan trọng:**
- Đọc file `Department_Testing_Scope.xlsx` trước, đưa nội dung vào prompt để AI phân loại Department đúng
- Prompt yêu cầu AI tách 1 Issue thành nhiều dòng nếu description có nhiều test item riêng biệt
- Tìm mã tham chiếu dạng `CCB-xxxxx`, `LIMO-xxxxx`, `LTM-xxxxx` trong description

> ⚠️ **JSON parsing fallback:** Python có logic sửa JSON bị truncate (tìm `}` cuối cùng, bọc `[...]`). C# cần giữ nguyên fallback này vì Gemini đôi khi trả JSON không hoàn chỉnh khi response dài.

---

### 3.5 File Config Service

**3.5.1 `muc.txt` parser**

File cấu hình dạng `key = "value"`, định nghĩa các field và giá trị dropdown cho form tạo Issue.

**Regex parse (Python):** `r'([^=\n]+?)\s*=\s*"(.*?)"'` (DOTALL mode)

**Logic phân loại value:**
- Nếu value trống → `string.Empty` (text input)
- Nếu value chứa từ `"Date"` → field kiểu date (`DatePicker`)
- Nếu value có nhiều dòng → list dropdown (`SelectBox`)
- Ngược lại → text input với default value

**C# model:**
```csharp
public class MucFieldConfig
{
    public string Key { get; set; }
    public FieldType Type { get; set; } // Text, Date, Dropdown
    public List<string> Options { get; set; } // nếu Dropdown
    public string DefaultValue { get; set; }
}
```

**3.5.2 `Department_Testing_Scope.xlsx`**

Chỉ đọc để đưa vào prompt AI, không xử lý logic phức tạp. Dùng `ClosedXML` hoặc `EPPlus` để đọc, convert sang string table.

---

### 3.6 Excel I/O Service

| Tác vụ Python | C# tương đương |
|---|---|
| `pd.read_excel(file)` | `ClosedXML` hoặc `EPPlus` |
| `df.to_excel(buffer)` | `ClosedXML` ghi vào `MemoryStream` |
| `pd.concat([old_df, new_df])` | Đọc file cũ, append rows mới, ghi lại |
| Download file | `File(bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "filename.xlsx")` |

---

### 3.7 Regex Utilities

**`extract_issue_keys`:** Parse Jira Issue key từ text tự do (URL hoặc key thuần)

Pattern: `r'([A-Z][A-Z0-9]+-[0-9]+)'`

Ví dụ: từ `"https://jira.company.com/browse/VFM-591822"` → `["VFM-591822"]`

```csharp
// C#
var matches = Regex.Matches(input, @"([A-Z][A-Z0-9]+-[0-9]+)");
var keys = matches.Select(m => m.Value).Distinct().ToList();
```

---

## 4. Mapping UI → Razor Pages / MVC Controllers

| Tab Streamlit | Trang C# đề xuất | Controller/Action |
|---|---|---|
| Trích xuất từ Jira | `/TestItem/Extract` | `TestItemController.Extract` |
| Cập nhật Test Item | `/TestItem/Update` | `TestItemController.Update` |
| Tạo thủ công | `/TestItem/Create` | `TestItemController.Create` |
| Xóa Test Item | `/TestItem/Delete` | `TestItemController.Delete` |
| Sidebar: Liệt kê Jira Fields | `/TestItem/Fields` hoặc partial | `TestItemController.GetFields` |

**Session state (Python) → C# TempData / Session:**
- `st.session_state.extracted_df` → `TempData` hoặc `IMemoryCache` với key per-user
- `st.session_state.u_data` (issue đang edit) → `TempData["CurrentIssue"]`

---

## 5. Luồng nghiệp vụ chi tiết

### 5.1 Tab Trích xuất (Extract Flow)

```
[User nhập Jira keys/URLs]
        ↓
[Parse keys bằng Regex]
        ↓
[Foreach key: GET /api/2/issue/{key}]
        ↓ (nếu include_subtasks = true)
[GET subtasks từ fields.subtasks[].key]
        ↓
[Build jira_data_to_ai: [{key, summary, description[:1500]}]]
        ↓
[Đọc Department_Testing_Scope.xlsx → string table]
        ↓
[Gọi Gemini API với prompt + data]
        ↓
[Parse JSON response (có fallback)]
        ↓
[Hiển thị table có thể edit]
        ↓
[Download Excel | Lưu vào Data_train.xlsx]
```

> ⚠️ **Performance:** Nếu có nhiều Issue, các lần gọi Jira API đang là sequential trong Python. C# nên dùng `Parallel.ForEachAsync` hoặc `Task.WhenAll` để tăng tốc, nhưng cần kiểm soát concurrency để tránh rate limit Jira.

### 5.2 Tab Cập nhật (Update Flow — Single)

```
[Nhập Issue key]
        ↓
[GET /api/2/issue/{key}]
        ↓
[Đọc MUC_CONFIG để render form fields]
        ↓
[Pre-fill giá trị hiện tại từ Issue (summary, description)]
        ↓
[User chỉnh sửa → Submit]
        ↓
[build_jira_payload → PUT /api/2/issue/{key}]
```

### 5.3 Tab Cập nhật hàng loạt (Bulk Update)

```
[Upload file Excel]
        ↓
[Tìm cột Key/Issue Key]
        ↓
[Foreach row: extract_issue_keys → update_jira_issue]
        ↓
[Progress bar → success]
```

> ⚠️ **Lỗi bị nuốt:** Python dùng `except: pass` trong bulk update, tức là lỗi từng row sẽ bị bỏ qua. C# nên collect errors và hiển thị summary cuối.

### 5.4 Tab Tạo hàng loạt (Bulk Create)

**Logic validate data trước khi tạo:**
1. Đọc MUC_CONFIG để biết cột nào bắt buộc và giá trị mặc định
2. Foreach row: nếu value là `null/NaN` → dùng giá trị mặc định từ config
3. Nếu dropdown field mà không có giá trị → dùng option đầu tiên

> ⚠️ `clean_cell_value()`: Python có hàm này để đảm bảo mọi value đều là kiểu primitive (string/number). C# serialize JSON sẽ xử lý tốt hơn, nhưng cần xử lý `null` và kiểu `object` đặc biệt.

---

## 6. Các điểm cần chú ý đặc biệt

### 6.1 SSL Certificate
Python dùng `verify=False` → Jira server dùng self-signed cert hoặc cert nội bộ. C# cần:
```csharp
var handler = new HttpClientHandler
{
    ServerCertificateCustomValidationCallback = (_, _, _, _) => true
};
// Chỉ dùng cho môi trường internal, không dùng production public
```

### 6.2 Jira Field Type Discovery
Python gọi `GET /rest/api/2/field` mỗi lần create/update để biết type của custom field. Đây là overhead lớn. C# nên cache kết quả này (`IMemoryCache`, TTL 30 phút).

### 6.3 Gemini Model Selection
Python tự động chọn model tốt nhất khi startup. C# có thể đơn giản hóa: hardcode `gemini-1.5-flash` trong config, cho phép override qua `appsettings.json`.

### 6.4 Description Truncation
Python cắt description tại 1500 ký tự trước khi gửi AI. C# phải giữ nguyên giới hạn này để tránh vượt context window và tăng chi phí token.

### 6.5 Template Headers
Python đọc headers từ file `Test_Data_Structure_V3.xlsx` (row đầu tiên). Nếu file không tồn tại, fallback về hardcoded list 14 cột. C# cần xử lý cả hai trường hợp.

### 6.6 User-Agent Header
Python set `User-Agent` giả lập Chrome browser khi gọi Jira API. Giữ nguyên để tránh bị Jira block.

---

## 7. Dependencies cần thay thế

| Python Package | C# NuGet tương đương |
|---|---|
| `requests` + `urllib3.util.Retry` | `HttpClient` + `Polly` |
| `google-generativeai` | `Google.Ai.Generativelanguage` hoặc gọi REST trực tiếp |
| `pandas` (read/write Excel) | `ClosedXML` hoặc `EPPlus` |
| `python-dotenv` | `Microsoft.Extensions.Configuration` + `appsettings.json` |
| `streamlit` (UI) | Razor Pages / MVC Views + Bootstrap |
| `re` (regex) | `System.Text.RegularExpressions` |
| `io.BytesIO` (download) | `MemoryStream` |

---

## 8. Phạm vi KHÔNG cần chuyển

- Toàn bộ CSS styling (Streamlit-specific) → thay bằng Bootstrap/Tailwind
- `st.session_state` → thay bằng TempData hoặc Session
- `st.spinner`, `st.progress` → thay bằng loading spinner JS phía frontend
- `st.markdown(unsafe_allow_html=True)` → HTML thuần trong Razor

---

## 9. Thứ tự triển khai gợi ý

1. `AppSettings` + Config validation
2. `JiraHttpClient` với Polly retry + SSL bypass
3. `JiraFieldMapper` (`build_jira_payload`)
4. `MucConfigParser` (parse `muc.txt`)
5. `ExcelService` (read/write)
6. `GeminiService` (AI call + JSON fallback parse)
7. Controllers + Views theo từng tab
8. Integration test với Jira test environment

---

*Ghi chú: Document này chỉ mô tả nghiệp vụ và mapping kỹ thuật, không bao gồm code hoàn chỉnh. Các đoạn code snippet chỉ mang tính minh họa.*