import os
import sys
import json
import time
import subprocess
import argparse
import sqlite3
import asyncio
import httpx
from datetime import datetime
import pandas as pd

# 全局变量声明
ocr_engine = None

# ================= 步骤 0：官方金蝶 SDK 预留接口 =================
class OfficialKingdeeSDKBridge:
    def __init__(self, acct_id="", user_name="", app_id="", app_sec="", server_url=""):
        self.acct_id = acct_id
        self.user_name = user_name
        self.app_id = app_id
        self.app_sec = app_sec
        self.server_url = server_url
        self.api_sdk = None
        self.is_connected = False
        self._initialize_sdk()

    def _initialize_sdk(self):
        try:
            from k3cloud_webapi_sdk.main import K3CloudApiSdk
            # 修复：显式传入 server_url 避免缺参报错
            self.api_sdk = K3CloudApiSdk(server_url=self.server_url)
            if self.acct_id and self.app_id and self.app_sec:
                self.api_sdk.InitConfig(
                    acct_id=self.acct_id, user_name=self.user_name,
                    app_id=self.app_id, app_sec=self.app_sec, server_url=self.server_url
                )
                self.is_connected = True
                print("✅ [金蝶官方 SDK] 账号密钥校验通过，实时 API 通道已建立！")
        except ImportError:
            print("💡 提示: 未在环境中检测到 k3cloud_webapi_sdk，将保持离线 Excel/CSV 台账模式运行。")
        except Exception as e:
            print(f"⚠️ [金蝶官方 SDK] 握手失败 ({e})，自动回退至离线 Mock 模式。")

    def query_stock_ledger(self, input_folder="."):
        if self.is_connected and self.api_sdk:
            try:
                query_param = {
                    "FormId": "STK_Inventory",
                    "FieldKeys": "FMaterialId.FNumber,FMaterialId.FName,FBaseQty,FGrossWeight",
                    "FilterString": "", "TopRowCount": 500
                }
                self.api_sdk.ExecuteBillQuery(query_param)
                print("🔌 成功通过官方 SDK 拉取金蝶云·星空即时台账！")
                return {"expected_weight": None, "expected_qty": None, "status_msg": "API_Mock"}
            except Exception as e:
                print(f"❌ 官方 SDK 查询异常: {e}")

        return self._load_local_fallback_mock(input_folder)

    def _load_local_fallback_mock(self, folder_path):
        erp_data = {"expected_weight": None, "expected_qty": None}
        kingdee_excel = os.path.join(folder_path, "kingdee_export.xlsx")
        kingdee_csv = os.path.join(folder_path, "kingdee_export.csv")
        
        try:
            if os.path.exists(kingdee_excel):
                df = pd.read_excel(kingdee_excel)
                erp_data["expected_weight"] = float(df['台账总毛重'].sum())
                erp_data["expected_qty"] = int(df['台账总件数'].sum())
                print(f"📂 [离线模式] 成功接入本地台账 ({kingdee_excel})：预计毛重 {erp_data['expected_weight']} KG, 预计件数 {erp_data['expected_qty']} 件")
            elif os.path.exists(kingdee_csv):
                df = pd.read_csv(kingdee_csv)
                erp_data["expected_weight"] = float(df['台账总毛重'].sum())
                erp_data["expected_qty"] = int(df['台账总件数'].sum())
                print(f"📂 [离线模式] 成功接入本地台账 ({kingdee_csv})：预计毛重 {erp_data['expected_weight']} KG, 预计件数 {erp_data['expected_qty']} 件")
            else:
                print("⚠️ 未检测到金蝶 ERP 导出台账，跳过 ERP 账实比对。")
        except Exception as e:
            print(f"🔌 金蝶数据解析异常: {e}")
        return erp_data

# ================= 步骤 1：离线数据库检索模块 =================
def query_hs_db_compliance(hs_code="", raw_text="", db_path="customs_hs_sample.db"):
    if not os.path.exists(db_path): return None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        if hs_code:
            clean_code = str(hs_code).replace('.', '').strip()
            row, code, name, cond, quaran = None, None, None, None, None
            try:
                cursor.execute("SELECT * FROM hs_rules WHERE `HS编码` LIKE ?", (f"%{clean_code}%",))
                row = cursor.fetchone()
                if row:
                    col_names = [description[0] for description in cursor.description]
                    row_dict = dict(zip(col_names, row))
                    code, cond, quaran = row_dict.get('HS编码', clean_code), row_dict.get('监管条件', ''), row_dict.get('检疫类别', '')
            except sqlite3.OperationalError:
                cursor.execute("SELECT hs_code, goods_name, supervision_cond, quarantine_cat FROM hs_rules WHERE hs_code = ?", (clean_code,))
                row = cursor.fetchone()
                if row:
                    code, cond, quaran = row[0], row[2], row[3]

            if row:
                conn.close()
                if cond and "Q" in str(cond): return f"⚠️ [库匹配] HS:{code} 命中监管条件【Q】(卫生检疫审批)"
                elif cond or quaran: return f"⚠️ [库匹配] HS:{code} 监管条件【{cond or '无'}】 检疫类别【{quaran or '无'}】"
                else: return "合规(普通货物)"

        # 兜底词库（中英文，忽略大小写）
        keywords = ["血", "细胞", "试剂", "干冰", "冷链", "疫苗", "生物", "blood", "cell", "reagent", "plasma", "dry ice", "cold chain", "vaccine", "biological"]
        matched_results = []
        for kw in keywords:
            if kw.lower() in raw_text.lower():
                try:
                    cursor.execute("SELECT `HS编码`, `商品名称`, `监管条件` FROM hs_rules WHERE `商品名称` LIKE ? LIMIT 1", (f"%{kw}%",))
                    row = cursor.fetchone()
                except sqlite3.OperationalError:
                    cursor.execute("SELECT hs_code, goods_name, supervision_cond FROM hs_rules WHERE goods_name LIKE ? LIMIT 1", (f"%{kw}%",))
                    row = cursor.fetchone()
                if row and len(row) >= 3 and row[2]:
                    matched_results.append(f"品名含[{kw}](参考HS:{row[0]} 监管:{row[2]})")

        conn.close()
        if matched_results: return f"⚠️ [库提醒] " + " | ".join(list(set(matched_results)))
    except Exception as e:
        print(f"⚠️ 离线 DB 检索提示: {e}")
    return None

# ================= 步骤 2 & 3：Ollama 引擎与 OCR =================
def ensure_ollama_running():
    import requests  
    print("🔄 正在检测本地 AI 引擎状态...")
    try:
        requests.get("http://localhost:11434/", timeout=2)
        print("✅ 核心 AI 引擎已在线，准备就绪！")
    except requests.exceptions.RequestException:
        print("⚠️ 核心引擎未响应，正在后台静默唤醒 Ollama...")
        subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=True)
        for i in range(8):  
            time.sleep(2)
            try:
                requests.get("http://localhost:11434/", timeout=3)
                print("✅ 引擎唤醒成功，算力已接管！\n")
                return
            except requests.exceptions.RequestException: pass
        print("❌ 引擎唤醒超时，请手动启动 Ollama！")

def get_ocr_engine():
    global ocr_engine
    if ocr_engine is None:
        from rapidocr_onnxruntime import RapidOCR  
        ocr_engine = RapidOCR()
    return ocr_engine

# 🔥 核心提速改造：电子版直接提取文本，扫描件才走 OCR
def extract_text_from_pdf(file_path):
    import pymupdf  
    print(f"正在扫描解析: {file_path} ...")
    doc = pymupdf.open(file_path)
    full_text = []
    
    for page_num in range(len(doc)):
        page = doc[page_num] 
        
        # 第一步：尝试直接提取原生文字（电子版 PDF 秒出结果）
        text = page.get_text()
        
        # 如果提取出的文字超过一定长度，说明是电子版，直接用！
        if text and len(text.strip()) > 50:
            full_text.append(text)
        else:
            # 第二步：如果没字（扫描件或图片页），再启动极耗 CPU 的 OCR
            print(f"  -> 发现扫描图片页/文字极少，启动 OCR 识别...")
            engine = get_ocr_engine()
            pix = page.get_pixmap(dpi=150) # DPI 从 200 降到 150，稍微提速且不降精度
            ocr_result, _ = engine(pix.tobytes("png"))
            if ocr_result: 
                full_text.append("\n".join([line[1] for line in ocr_result]))
                
    return "\n".join(full_text) if full_text else ""

# ================= 步骤 4：异步 AI 字段提取 =================
async def extract_data_with_ai_async(client, raw_text, filename, db_path="customs_hs_sample.db"):
    truncated_text = raw_text[:8000] if len(raw_text) > 8000 else raw_text

    system_prompt = f"""
    你是一个极其严谨的国际空海运单证与生物医药特种冷链数据提取程序。
    当前处理文件：【{filename}】。
    
    【绝对强制规则】
    1. Doc_Type: 从这6个中选1个："订舱确认书(Booking)", "运单(HAWB/MAWB)", "发票(Invoice)", "箱单(Packing List)", "报关单(Customs Declaration)", "贸易合同(Contract)"。
       - 文件名含 PACKING LIST、PL 判定为 "箱单(Packing List)"。
       - 含 Booking Confirmation、Booking、订舱确认、S/O、Departure Booking 统一识别为 "订舱确认书(Booking)"。
    2. HS_Code: 提取总结性的海关编码 (HS Code)。找不到填 ""。
    3. Gross_Weight: 提取“毛重(Gross Weight / G.W.)”数值，严禁提取净重！找不到填 0.0。
    4. Quantity: 提取 QTY, PKGS 附近的纯整数件数。提取不到填 0。
    5. Cut_Off_Time: 提取 截货/截关/ETD 时间，格式 "YYYY-MM-DD HH:MM"。提取不到填 "NONE"。
    6. Biopharma_Compliance: 扫描文本中是否有"试剂(Reagent)","细胞(Cell)","血液(Blood/Plasma)","温控(Cold Chain/Temperature)","干冰(Dry Ice)","生物(Biological)","疫苗(Vaccine)"等中英文字眼。只要出现任何相关词汇，都必须填："⚠️ 命中特种货物，需核对《出入境特殊物品卫生检疫审批单》与相变温控要求"；如果全篇都没有，才能填 "合规(普通货物)"。
    7. items: 提取明细行数组。必须原封不动提取数值，严禁自行计算！格式：item_no, desc, qty, unit_price, total_price。如果明细行内有对应的 HS Code，请一并提取到 "hs_code" 字段中。
       【极度重要】：提取表格明细时，务必逐行对齐！绝对严禁发生“串行”错误！上一行的数量绝对不能填给下一行！比如：Item 1 是 30箱，Item 2 是 20箱，就老老实实提取 30 和 20，绝对不准把 Item 1 的 30 抄给 Item 2！
       如果表格排版混乱，请根据上下文逻辑（如：数量 × 单价 = 总价）进行反向推导补齐。
    
    必须且只能输出纯 JSON，格式如下(以下数值仅为格式占位，切勿照抄)：
    {{"Doc_Type": "订舱确认书(Booking)", "HS_Code": "3002909000", "Gross_Weight": 0.0, "Quantity": 0, "Cut_Off_Time": "NONE", "Biopharma_Compliance": "合规(普通货物)", "items": [{{"item_no": 1, "desc": "Cell Culture", "hs_code": "3822190000", "qty": 0, "unit_price": 0.0, "total_price": 0.0}}]}}
    """
    payload = {
        "model": "qwen2.5:3b",  
        "prompt": f"{system_prompt}\n\n待处理文本：\n{truncated_text}",
        "stream": False, "format": "json",
        "options": {"num_predict": 1280, "num_ctx": 8192, "temperature": 0.0, "top_p": 0.1}
    }

    for attempt in range(3):
        try:
            # 超时时间 300 秒，防止 CPU 处理慢卡死
            response = await client.post("http://localhost:11434/api/generate", json=payload, timeout=300.0)
            response.raise_for_status()
            
            resp_json = response.json()
            if 'response' not in resp_json:
                raise ValueError(f"API 返回格式异常: {resp_json}")

            data_dict = json.loads(resp_json['response'])
            
            fn_lower = filename.lower()
            if any(k in fn_lower for k in ["booking", "bkg", "so", "confirm"]): data_dict["Doc_Type"] = "订舱确认书(Booking)"
            elif "packing_list" in fn_lower or "pl" in fn_lower: data_dict["Doc_Type"] = "箱单(Packing List)"
            elif "invoice" in fn_lower or "inv" in fn_lower: data_dict["Doc_Type"] = "发票(Invoice)"
            elif "hawb" in fn_lower or "mawb" in fn_lower or "waybill" in fn_lower: data_dict["Doc_Type"] = "运单(HAWB/MAWB)"
                
            if "items" not in data_dict: data_dict["items"] = []
            
            # ================= 核心升级：多 HS Code 遍历查库 =================
            all_hs_codes = set()
            if data_dict.get("HS_Code"):
                all_hs_codes.add(str(data_dict["HS_Code"]).replace('.', '').replace(' ', ''))
            
            for item in data_dict.get("items", []):
                if isinstance(item, dict):
                    code = item.get("hs_code") or item.get("HS_Code")
                    if code: all_hs_codes.add(str(code).replace('.', '').replace(' ', ''))

            db_compliance_msgs = []
            for code in all_hs_codes:
                msg = query_hs_db_compliance(hs_code=code, raw_text=raw_text, db_path=db_path)
                if msg and msg != "合规(普通货物)":
                    db_compliance_msgs.append(msg)
            
            if db_compliance_msgs:
                data_dict["Biopharma_Compliance"] = " | ".join(list(set(db_compliance_msgs)))
            else:
                fallback_msg = query_hs_db_compliance(hs_code="", raw_text=raw_text, db_path=db_path)
                if fallback_msg: data_dict["Biopharma_Compliance"] = fallback_msg

            return filename, data_dict
        except Exception as e:
            print(f"⚠️ [{filename}] AI 处理出错 (第{attempt+1}次尝试): {repr(e)}")
            if attempt < 2: await asyncio.sleep(3)

    return filename, {"Doc_Type": "解析失败", "HS_Code": "", "Gross_Weight": 0.0, "Quantity": 0, "Cut_Off_Time": "NONE", "Biopharma_Compliance": "N/A", "items": []}

async def process_all_files_async(pdf_files, input_folder, db_path):
    extracted_results = {}
    # 使用 Semaphore 限制同时发给 AI 的请求数为 2，防止本地模型被撑爆
    sem = asyncio.Semaphore(2)

    async def limited_extract(client, f):
        async with sem:
            text = extract_text_from_pdf(os.path.join(input_folder, f))
            return await extract_data_with_ai_async(client, text, f, db_path)

    async with httpx.AsyncClient() as client:
        tasks = [limited_extract(client, f) for f in pdf_files]
        results = await asyncio.gather(*tasks)
        for filename, data_dict in results:
            extracted_results[filename] = data_dict
    return extracted_results

# ================= 步骤 4.5：逻辑矛盾规则引擎 =================
def rule_engine_check(data):
    warnings = []
    doc_type = data.get("Doc_Type", "")
    items = data.get("items", []) if isinstance(data.get("items", []), list) else []
    
    if doc_type not in ["发票(Invoice)", "贸易合同(Contract)"]: return "✅ 逻辑校验通过"
    
    for item in items:
        if not isinstance(item, dict): continue
        desc = item.get("desc", "未知项")
        try: qty = int(float(item.get("qty") or 0))
        except: qty = 0
        try: u_price, t_price = float(item.get("unit_price") or 0), float(item.get("total_price") or 0)
        except: u_price, t_price = 0.0, 0.0
        
        if u_price < 0 or t_price < 0: warnings.append(f"负数异常 (项:{desc})")
        if qty > 0 and u_price > 0 and t_price > 0 and abs((qty * u_price) - t_price) > 0.05 * t_price:
            warnings.append(f"金额不符 (项:{desc})")
                
    return " | ".join(warnings) if warnings else "✅ 逻辑校验通过"

# ================= 步骤 5：自动同步税则 CSV =================
def init_tariff_database(input_folder="."):
    csv_filename = os.path.join(input_folder, "P020251231607833453633.csv")
    db_path = os.path.join(input_folder, "customs_hs_sample.db")
    if os.path.exists(csv_filename):
        try:
            import pandas as pd, re
            df = pd.read_csv(csv_filename).replace(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', regex=True)
            df.columns = [re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', col) for col in df.columns]
            conn = sqlite3.connect(db_path)
            df.to_sql("hs_rules", conn, if_exists="replace", index=False)
            conn.close()
        except Exception as e: print(f"⚠️ 汇入税则失败: {e}")

# ================= 步骤 6：核心处理主逻辑 =================
def process_and_cross_check(input_folder=".", output_folder=".", export_json=False):
    from openpyxl.styles import PatternFill, Font, Alignment
    from openpyxl.utils import get_column_letter

    ensure_ollama_running()
    init_tariff_database(input_folder)

    print(f"\n📂 v2.6.2 启动，扫描目录: {input_folder} ...")
    os.makedirs(output_folder, exist_ok=True)
    db_path = os.path.join(input_folder, "customs_hs_sample.db") if os.path.exists(os.path.join(input_folder, "customs_hs_sample.db")) else "customs_hs_sample.db"
        
    erp_base_data = OfficialKingdeeSDKBridge().query_stock_ledger(input_folder)
    pdf_files = [f for f in os.listdir(input_folder) if f.lower().endswith('.pdf')]
    if not pdf_files:
        print("❌ 未找到 PDF 文件。")
        return None, None

    extracted_results = asyncio.run(process_all_files_async(pdf_files, input_folder, db_path))
    records_for_excel = []
    now = datetime.now()
    
    CORE_SHIPPING_DOCS = ["订舱确认书(Booking)", "运单(HAWB/MAWB)", "发票(Invoice)", "箱单(Packing List)", "报关单(Customs Declaration)"]
    core_weights = [float(d.get('Gross_Weight', 0)) for d in extracted_results.values() if d.get('Doc_Type') in CORE_SHIPPING_DOCS and float(d.get('Gross_Weight', 0)) > 0]
    core_packages = [int(d.get('Quantity', 0)) for d in extracted_results.values() if d.get('Doc_Type') in CORE_SHIPPING_DOCS and int(d.get('Quantity', 0)) > 0]

    weight_mismatch = len(set(core_weights)) > 1 if core_weights else False
    qty_mismatch = len(set(core_packages)) > 1 if core_packages else False
    doc_internal_error = weight_mismatch or qty_mismatch

    for filename, data in extracted_results.items():
        doc_type, w, q = data.get('Doc_Type', '未知'), float(data.get('Gross_Weight', 0.0) or 0.0), int(data.get('Quantity', 0) or 0)
        cut_time_str, bio_compliance = data.get('Cut_Off_Time', 'NONE'), data.get('Biopharma_Compliance', '合规(普通货物)')
        
        logic_check_result = rule_engine_check(data)
        if logic_check_result != "✅ 逻辑校验通过": logic_check_result = "⚠️ 规则拦截: " + logic_check_result
            
        time_to_ddl_hrs = None  # 使用 None，避免 str 和 float 混用导致 Arrow 报错
        if cut_time_str != "NONE":
            try: time_to_ddl_hrs = round((datetime.strptime(cut_time_str, "%Y-%m-%d %H:%M") - now).total_seconds() / 3600, 1)
            except Exception: pass

        final_doc_status = "待判定"
        if doc_type in CORE_SHIPPING_DOCS:
            if doc_internal_error:
                diffs = []
                if weight_mismatch: diffs.append("毛重冲突")
                if qty_mismatch: diffs.append("件数冲突")
                final_doc_status = f"❌ 单证不符（{','.join(diffs)}）"
            else: final_doc_status = "✅ 单证通过"
        elif doc_type == "贸易合同(Contract)": final_doc_status = "不适用"

        erp_status = "未接入台账"
        if erp_base_data.get("expected_weight") is not None and erp_base_data.get("expected_qty") is not None:
            if doc_type in CORE_SHIPPING_DOCS:
                erp_status = "❌ 账实不符(冲突)" if w != erp_base_data["expected_weight"] or q != erp_base_data["expected_qty"] else "✅ 账实一致"
        
        records_for_excel.append({
            "原文件名": filename, "识别单据类型": doc_type, "生物/检疫准入": bio_compliance,
            "提取毛重(KG)": w, "提取件数": q, "截关时间(DDL)": cut_time_str, "剩余倒计时(Hrs)": time_to_ddl_hrs,
            "单证一致性": final_doc_status, "明细逻辑校验": logic_check_result, "金蝶ERP核对": erp_status
        })

    time_suffix = now.strftime("%Y%m%d_%H%M%S")
    default_excel = os.path.join(output_folder, "【控制塔看板】单证_明细_ERP核对预警.xlsx")
    fallback_excel = os.path.join(output_folder, f"【控制塔看板】单证_明细_ERP核对预警_{time_suffix}.xlsx")
    df = pd.DataFrame(records_for_excel)

    # 修复 Streamlit Arrow 序列化报错问题：在输出前，将混合类型的列强制转为字符串
    if '剩余倒计时(Hrs)' in df.columns:
        df['剩余倒计时(Hrs)'] = df['剩余倒计时(Hrs)'].fillna('N/A').astype(str)

    def write_excel(target_path):
        with pd.ExcelWriter(target_path, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Control_Tower')
            ws = writer.sheets['Control_Tower']
            h_fill, h_font = PatternFill("solid", fgColor="203764"), Font(color="FFFFFF", bold=True)
            s_fill, w_fill, d_fill = PatternFill("solid", fgColor="C6EFCE"), PatternFill("solid", fgColor="FFEB9C"), PatternFill("solid", fgColor="FFC7CE")
            
            for cell in ws[1]: cell.fill, cell.font, cell.alignment = h_fill, h_font, Alignment(horizontal="center", vertical="center")

            for row in ws.iter_rows(min_row=2, max_row=len(records_for_excel)+1, min_col=1, max_col=10):
                for cell in row: cell.alignment = Alignment(horizontal="center", vertical="center")
                if "⚠️" in str(row[2].value): row[2].fill, row[2].font = w_fill, Font(color="9C0006", bold=True)
                
                ddl_val = row[6].value
                try:
                    ddl = float(ddl_val)
                    if ddl < 0: row[5].fill, row[5].font, row[5].value = d_fill, Font(color="9C0006", bold=True), "⚠️ 逾期超时"
                    elif 0 <= ddl <= 24: row[5].fill, row[5].font = w_fill, Font(color="9C5700", bold=True)
                    else: row[5].fill, row[5].font = s_fill, Font(color="006100", bold=True)
                except (ValueError, TypeError):
                    row[5].value = "N/A"

                for cell, text in [(row[7], row[7].value), (row[8], row[8].value), (row[9], row[9].value)]:
                    if "❌" in str(text): cell.fill, cell.font = d_fill, Font(color="9C0006", bold=True)
                    elif "⚠️" in str(text): cell.fill, cell.font = w_fill, Font(color="9C0006", bold=True)
                    elif "✅" in str(text): cell.fill = s_fill

            for i, col in enumerate(df.columns):
                ws.column_dimensions[get_column_letter(i + 1)].width = min(max(len(str(col).encode('gbk', 'ignore')), max(df[col].astype(str).apply(lambda x: len(x.encode('gbk', 'ignore'))), default=0)) + 4, 80)

    try: excel_name = default_excel; write_excel(default_excel)
    except PermissionError: excel_name = fallback_excel; write_excel(fallback_excel)

    print(f"🎉 自动化完成！看板已保存至: {excel_name}")
    if export_json:
        j_name = os.path.join(output_folder, f"audit_result_{time_suffix}.json" if excel_name == fallback_excel else "audit_result.json")
        with open(j_name, 'w', encoding='utf-8') as f: json.dump(extracted_results, f, ensure_ascii=False, indent=4)
    return df, extracted_results

# ================= 步骤 7：原生 Streamlit UI 逻辑 =================
def render_streamlit_ui():
    import streamlit as st
    st.set_page_config(page_title="关务控制塔", layout="wide")
    st.title("🚀 离线关务单证风控引擎")
    st.markdown("集成最新税则对撞、大模型并发提取与行明细逻辑校验")

    input_folder = st.text_input("请输入包含单证 PDF 的文件夹路径:", value=os.getcwd())
    export_json = st.checkbox("同步导出 JSON 数据文件 (供外部 EDI 接入)", value=True)

    if st.button("🚀 开始全栈关务交叉核对", type="primary"):
        if not os.path.exists(input_folder): st.error("指定的文件夹路径不存在，请检查！")
        else:
            with st.spinner('⏳ 正在并发对接 SQLite 数据库与底层 AI 进行风控核对...'):
                output_dir = os.path.join(os.path.dirname(input_folder), "Result")
                df, extracted_json = process_and_cross_check(input_folder=input_folder, output_folder=output_dir, export_json=export_json)
                
                if df is not None:
                    st.success(f"🎉 审核完成！红黄绿控制塔看板及数据结果已存至：{output_dir}")
                    st.subheader("📊 风控核对结果看板")
                    def color_format(val):
                        if '❌' in str(val): return 'background-color: #FFC7CE'
                        elif '⚠️' in str(val): return 'background-color: #FFEB9C'
                        elif '✅' in str(val): return 'background-color: #C6EFCE'
                        return ''
                    # 替换 use_container_width 为 width='stretch' 解决警告
                    try:
                        st.dataframe(df.style.map(color_format, subset=['生物/检疫准入', '单证一致性', '明细逻辑校验', '金蝶ERP核对']), width='stretch')
                    except Exception:
                        st.dataframe(df.style.map(color_format, subset=['生物/检疫准入', '单证一致性', '明细逻辑校验', '金蝶ERP核对']), use_container_width=True)
                        
                    if extracted_json:
                        st.subheader("📄 AI 提取与项号明细原始数据 (JSON)")
                        st.json(extracted_json)
                else: st.warning("⚠️ 该目录下未扫描到可解析的单证 PDF 文件。")

# 当直接执行当前 Python 文件时的 CLI 回退支持
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="🚀 离线关务单证风控引擎")
    parser.add_argument("-i", "--input", default=".", help="指定包含待核对 PDF 的文件夹路径")
    parser.add_argument("-o", "--output", default=".", help="指定 Excel 及 JSON 的输出目录")
    parser.add_argument("--json", action="store_true", help="启用后，将同步输出 json 格式文件")
    args = parser.parse_args()
    process_and_cross_check(input_folder=args.input, output_folder=args.output, export_json=args.json)