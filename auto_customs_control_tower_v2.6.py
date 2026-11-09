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

# ================= 步骤 0：官方金蝶 SDK 预留接口 (含离线回退保护) =================
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
            self.api_sdk = K3CloudApiSdk()
            if self.acct_id and self.app_id and self.app_sec:
                self.api_sdk.InitConfig(
                    acct_id=self.acct_id,
                    user_name=self.user_name,
                    app_id=self.app_id,
                    app_sec=self.app_sec,
                    server_url=self.server_url
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
                    "FilterString": "",
                    "TopRowCount": 500
                }
                result_json_str = self.api_sdk.ExecuteBillQuery(query_param)
                result_data = json.loads(result_json_str) if isinstance(result_json_str, str) else result_json_str
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
                print("⚠️ 未检测到金蝶 ERP 导出台账 (kingdee_export.xlsx/csv)，跳过 ERP 账实比对。")
        except Exception as e:
            print(f"🔌 金蝶数据解析异常: {e}")
            
        return erp_data

# ================= 步骤 1：离线数据库（SQLite）监管条件检索模块 =================
def query_hs_db_compliance(hs_code="", raw_text="", db_path="customs_hs_sample.db"):
    if not os.path.exists(db_path):
        return None

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 1. 优先通过 HS Code 查询
        if hs_code:
            clean_code = str(hs_code).replace('.', '').strip()
            row = None
            code, name, cond, quaran = None, None, None, None
            try:
                cursor.execute("SELECT * FROM hs_rules WHERE `HS编码` LIKE ?", (f"%{clean_code}%",))
                row = cursor.fetchone()
                if row:
                    col_names = [description[0] for description in cursor.description]
                    row_dict = dict(zip(col_names, row))
                    code = row_dict.get('HS编码', clean_code)
                    name = row_dict.get('商品名称', '')
                    cond = row_dict.get('监管条件', '')
                    quaran = row_dict.get('检疫类别', '')
            except sqlite3.OperationalError:
                cursor.execute("SELECT hs_code, goods_name, supervision_cond, quarantine_cat FROM hs_rules WHERE hs_code = ?", (clean_code,))
                row = cursor.fetchone()
                if row:
                    code, name, cond, quaran = row[0], row[1], row[2], row[3]

            if row:
                conn.close()
                if cond and "Q" in str(cond):
                    return f"⚠️ [库匹配] HS:{code} 命中监管条件【Q】(卫生检疫审批)，须核对《出入境特殊物品检疫审批单》"
                elif cond or quaran:
                    return f"⚠️ [库匹配] HS:{code} 监管条件【{cond or '无'}】 检疫类别【{quaran or '无'}】"
                else:
                    return "合规(普通货物)"

        # 2. 若无精准 HS Code，模糊匹配品名关键词
        keywords = ["血", "细胞", "试剂", "干冰", "冷链", "疫苗", "生物"]
        matched_results = []
        for kw in keywords:
            if kw in raw_text:
                try:
                    cursor.execute("SELECT `HS编码`, `商品名称`, `监管条件` FROM hs_rules WHERE `商品名称` LIKE ? LIMIT 1", (f"%{kw}%",))
                    row = cursor.fetchone()
                except sqlite3.OperationalError:
                    cursor.execute("SELECT hs_code, goods_name, supervision_cond FROM hs_rules WHERE goods_name LIKE ? LIMIT 1", (f"%{kw}%",))
                    row = cursor.fetchone()
                if row and len(row) >= 3 and row[2]:
                    matched_results.append(f"品名含[{kw}](参考HS:{row[0]} 监管:{row[2]})")

        conn.close()
        if matched_results:
            return f"⚠️ [库提醒] " + " | ".join(matched_results) + "，需核对出入境特殊物品检疫要求"

    except Exception as e:
        print(f"⚠️ 离线 DB 检索提示: {e}")

    return None

# ================= 步骤 2：自动唤醒大模型引擎 =================
def ensure_ollama_running():
    import requests  
    print("🔄 正在检测本地 AI 引擎状态...")
    try:
        requests.get("http://localhost:11434/", timeout=2)
        print("✅ 核心 AI 引擎已在线，准备就绪！")
    except requests.exceptions.RequestException:
        print("⚠️ 核心引擎未响应，正在后台静默唤醒 Ollama...")
        subprocess.Popen(
            ["ollama", "serve"], 
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL,
            shell=True
        )
        for i in range(8):  
            time.sleep(2)
            try:
                requests.get("http://localhost:11434/", timeout=3)
                print("✅ 引擎唤醒成功，算力已接管！\n")
                return
            except requests.exceptions.RequestException:
                print(f"⏳ 正在预热神经网络底层引擎... (已等待 {2*(i+1)} 秒)")
        print("❌ 引擎唤醒超时，请手动启动 Ollama！")

def get_ocr_engine():
    global ocr_engine
    if ocr_engine is None:
        print("正在加载离线 OCR 视觉识别引擎...")
        from rapidocr_onnxruntime import RapidOCR  
        ocr_engine = RapidOCR()
    return ocr_engine

# ================= 步骤 3：多页全量 OCR 扫描函数 =================
def extract_text_from_pdf(file_path):
    import pymupdf  
    print(f"正在扫描解析: {file_path} ...")
    engine = get_ocr_engine()
    doc = pymupdf.open(file_path)
    full_text = []

    for page_num in range(len(doc)):
        page = doc[page_num] 
        pix = page.get_pixmap(dpi=200)
        img_data = pix.tobytes("png")
        ocr_result, _ = engine(img_data)

        if ocr_result:
            page_text = "\n".join([line[1] for line in ocr_result])
            full_text.append(page_text)

    return "\n".join(full_text) if full_text else ""

# ================= 步骤 4：异步 AI 字段提取 (支持明细项) =================
async def extract_data_with_ai_async(client, raw_text, filename, db_path="customs_hs_sample.db"):
    truncated_text = raw_text[:4000] if len(raw_text) > 4000 else raw_text

    system_prompt = f"""
    你是一个极其严谨的国际空海运单证与生物医药特种冷链数据提取程序。
    当前处理文件：【{filename}】。
    
    【绝对强制规则】
    1. Doc_Type: 从这6个中选1个："订舱确认书(Booking)", "运单(HAWB/MAWB)", "发票(Invoice)", "箱单(Packing List)", "报关单(Customs Declaration)", "贸易合同(Contract)"。
       - 文件名或标题含 PACKING LIST、PL 的优先判定为 "箱单(Packing List)"。
       - 包含 Air Freight Departure Booking Confirmation 的识别为 "订舱确认书(Booking)"。
    2. HS_Code: 提取文本中的海关编码 (HS Code, 8位到10位数字)。找不到填 ""。
    3. Gross_Weight: 必须提取“毛重(Gross Weight / G.W.)”数值，严禁提取“净重(N.W.)”！找不到填 0.0。
    4. Quantity: 提取 QTY, PKGS 附近的纯整数件数。提取不到填 0。
    5. Cut_Off_Time: 提取 截货/截关/ETD/SI Cut-off 时间，格式 "YYYY-MM-DD HH:MM"。提取不到填 "NONE"。
    6. Biopharma_Compliance: 扫描文本中是否有"试剂(Reagent)","细胞(Cell)","血液(Blood)","温控(Temperature)","冷链(Cold Chain)","干冰(Dry Ice)"等字眼。如果有，填："⚠️ 命中特种货物，需核对《出入境特殊物品卫生检疫审批单》与相变温控要求"；如果没有，填 "合规(普通货物)"。
    7. items: 提取明细行数组。必须【原封不动】提取单据原文数值，严禁自行计算！
       提取格式：item_no(项号), desc(品名), qty(数量纯数字), unit_price(单价纯数字), total_price(总价纯数字)。
       例如：发票中写着 "30 CTNS", "$150.00", "$4,500.00"，你必须输出 {{"qty": 30, "unit_price": 150.0, "total_price": 4500.0}}。
    
    必须且只能输出纯 JSON，格式如下：
    {{"Doc_Type": "箱单(Packing List)", "HS_Code": "3002909000", "Gross_Weight": 1250.5, "Quantity": 50, "Cut_Off_Time": "NONE", "Biopharma_Compliance": "合规(普通货物)", "items": [{{"item_no": 1, "desc": "Cell Culture", "qty": 50, "unit_price": 5.0, "total_price": 250.0}}]}}
    """
    payload = {
        "model": "qwen2.5:3b",  
        "prompt": f"{system_prompt}\n\n待处理文本：\n{truncated_text}",
        "stream": False,
        "format": "json",
        # ✨ 新增速度与稳定性控制选项
        "options": {
            "num_predict": 512,    # 限制单次生成的最大 Token 数，防止大模型吐出冗长重复数据
            "temperature": 0.0     # 采用确定性采样，提升推理计算速度并保证数字防幻觉
        }
    }

    for attempt in range(3):
        try:
            response = await client.post("http://localhost:11434/api/generate", json=payload, timeout=60.0)
            response.raise_for_status()
            data_dict = json.loads(response.json()['response'])
            
            # 1. 原生规则干预
            fn_lower = filename.lower()
            if "packing_list" in fn_lower or "pl" in fn_lower:
                data_dict["Doc_Type"] = "箱单(Packing List)"
            elif "invoice" in fn_lower or "inv" in fn_lower:
                data_dict["Doc_Type"] = "发票(Invoice)"
            elif "hawb" in fn_lower or "mawb" in fn_lower or "waybill" in fn_lower:
                data_dict["Doc_Type"] = "运单(HAWB/MAWB)"
                
            if "items" not in data_dict:
                data_dict["items"] = []
            
            # 2. SQLite 数据库对撞
            hs_code_val = data_dict.get("HS_Code", "")
            db_compliance = query_hs_db_compliance(hs_code=hs_code_val, raw_text=raw_text, db_path=db_path)
            if db_compliance:
                data_dict["Biopharma_Compliance"] = db_compliance

            return filename, data_dict

        except Exception as e:
            print(f"⚠️ [{filename}] AI 处理出错 (第 {attempt+1} 次尝试): {e}")
            await asyncio.sleep(2)

    return filename, {"Doc_Type": "解析失败", "HS_Code": "", "Gross_Weight": 0.0, "Quantity": 0, "Cut_Off_Time": "NONE", "Biopharma_Compliance": "N/A", "items": []}

async def process_all_files_async(pdf_files, input_folder, db_path):
    extracted_results = {}
    async with httpx.AsyncClient() as client:
        tasks = []
        for file in pdf_files:
            file_path = os.path.join(input_folder, file)
            raw_text = extract_text_from_pdf(file_path)
            tasks.append(extract_data_with_ai_async(client, raw_text, file, db_path))
        
        results = await asyncio.gather(*tasks)
        for filename, data_dict in results:
            extracted_results[filename] = data_dict
            
    return extracted_results

# ================= 步骤 4.5：逻辑矛盾规则引擎 (RuleEngine) =================
def rule_engine_check(data):
    warnings = []
    doc_type = data.get("Doc_Type", "")
    items = data.get("items", [])
    
    # 【新增拦截】仅对发票和合同进行 [数量 × 单价 = 总金额] 的商品明细校验
    # 运单(HAWB/MAWB)的运费计算规则是 Chargeable Weight × Rate，不适用件数乘法；箱单/订舱单无金额
    if doc_type not in ["发票(Invoice)", "贸易合同(Contract)"]:
        return "✅ 逻辑校验通过"
    
    # 🛡️ 防崩溃 1：如果大模型发神经，把 items 返回成了字符串或空值，强行变成列表
    if not isinstance(items, list):
        items = []

    for item in items:
        # 🛡️ 防崩溃 2：如果列表里的元素不是字典（比如大模型直接扔了个字符串进去）
        if not isinstance(item, dict):
            continue

        desc = item.get("desc", "未知项")
        
        # 🛡️ 防崩溃 3：极其暴力的类型转换，不管返回什么，只要转不了数字，统统变成 0
        try:
            qty = int(float(item.get("qty") or 0))
        except (ValueError, TypeError):
            qty = 0
            
        try:
            u_price = float(item.get("unit_price") or 0)
        except (ValueError, TypeError):
            u_price = 0.0
            
        try:
            t_price = float(item.get("total_price") or 0)
        except (ValueError, TypeError):
            t_price = 0.0
        
        # 现在绝对是数字了，不可能报错
        if u_price < 0 or t_price < 0:
            warnings.append(f"负数异常 (项:{desc})")
        if qty > 0 and u_price > 0 and t_price > 0:
            if abs((qty * u_price) - t_price) > 0.05 * t_price:
                warnings.append(f"金额计算不符 (项:{desc})")
                
    return " | ".join(warnings) if warnings else "✅ 逻辑校验通过"

# ================= 步骤 5：自动同步税则 CSV 到 SQLite 数据库 =================
def init_tariff_database(input_folder="."):
    csv_filename = os.path.join(input_folder, "P020251231607833453633.csv")
    db_path = os.path.join(input_folder, "customs_hs_sample.db")
    
    if os.path.exists(csv_filename):
        try:
            print(f"🔄 检测到税则 CSV 文件 ({csv_filename})，正在自动更新离线 SQLite 数据库...")
            import pandas as pd
            import re
            df = pd.read_csv(csv_filename)
            df = df.replace(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', regex=True)
            df.columns = [re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', col) for col in df.columns]
            
            conn = sqlite3.connect(db_path)
            df.to_sql("hs_rules", conn, if_exists="replace", index=False)
            conn.close()
            print("✅ 最新《税则》数据已完美编入离线 SQLite 数据库！")
        except Exception as e:
            print(f"⚠️ 汇入税则 CSV 失败: {e}")

# ================= 步骤 6：核心处理主逻辑 (直接供 CLI 或 Streamlit 内置调用) =================
def process_and_cross_check(input_folder=".", output_folder=".", export_json=False):
    import openpyxl
    from openpyxl.styles import PatternFill, Font, Alignment

    ensure_ollama_running()
    init_tariff_database(input_folder)

    print("\n" + "="*60)
    print(f" 📂 v2.6 (无缝内存直连版) 启动，扫描目录: {input_folder} ...")
    print("="*60)
    
    os.makedirs(output_folder, exist_ok=True)
    db_path = os.path.join(input_folder, "customs_hs_sample.db")
    if not os.path.exists(db_path):
        db_path = "customs_hs_sample.db"
        
    kingdee_bridge = OfficialKingdeeSDKBridge()
    erp_base_data = kingdee_bridge.query_stock_ledger(input_folder)
    
    pdf_files = [f for f in os.listdir(input_folder) if f.lower().endswith('.pdf')]
    if not pdf_files:
        print("❌ 当前目录下未找到 PDF 文件。")
        return None, None

    # 异步并发执行大模型提取
    extracted_results = asyncio.run(process_all_files_async(pdf_files, input_folder, db_path))
        
    records_for_excel = []
    print("\n" + "="*60)
    print(" 🔍 AI 并发提取完毕，开始多单交叉核对与逻辑校验...")
    print("="*60)

    now = datetime.now()
    CORE_SHIPPING_DOCS = ["运单(HAWB/MAWB)", "发票(Invoice)", "箱单(Packing List)", "报关单(Customs Declaration)"]
    
    core_weights = [float(d.get('Gross_Weight', 0)) for d in extracted_results.values() if d.get('Doc_Type') in CORE_SHIPPING_DOCS and float(d.get('Gross_Weight', 0)) > 0]
    core_packages = [int(d.get('Quantity', 0)) for d in extracted_results.values() if d.get('Doc_Type') in CORE_SHIPPING_DOCS and int(d.get('Quantity', 0)) > 0]

    weight_mismatch = len(set(core_weights)) > 1 if core_weights else False
    qty_mismatch = len(set(core_packages)) > 1 if core_packages else False
    doc_internal_error = weight_mismatch or qty_mismatch

    for filename, data in extracted_results.items():
        doc_type = data.get('Doc_Type', '未知')
        w = float(data.get('Gross_Weight', 0.0) or 0.0)
        q = int(data.get('Quantity', 0) or 0)
        cut_time_str = data.get('Cut_Off_Time', 'NONE')
        bio_compliance = data.get('Biopharma_Compliance', '合规(普通货物)')
        
        logic_check_result = rule_engine_check(data)
        if logic_check_result != "✅ 逻辑校验通过":
            logic_check_result = "⚠️ 规则拦截: " + logic_check_result
            
        time_to_ddl_hrs = "N/A"
        if cut_time_str != "NONE":
            try:
                dt_target = datetime.strptime(cut_time_str, "%Y-%m-%d %H:%M")
                hours_diff = round((dt_target - now).total_seconds() / 3600, 1)
                time_to_ddl_hrs = hours_diff
            except Exception:
                pass

        # 1. 单据内部核对状态
        final_doc_status = "待判定"
        if doc_type in CORE_SHIPPING_DOCS:
            if doc_internal_error:
                diff_reasons = []
                if weight_mismatch: diff_reasons.append("毛重冲突")
                if qty_mismatch: diff_reasons.append("件数冲突")
                final_doc_status = f"❌ 单证不符（{','.join(diff_reasons)}）"
            else:
                final_doc_status = "✅ 单证通过"
        elif doc_type == "贸易合同(Contract)":
            final_doc_status = "不适用"

        # 2. 金蝶 ERP 核对
        erp_status = "未接入台账"
        if erp_base_data.get("expected_weight") is not None and erp_base_data.get("expected_qty") is not None:
            if doc_type in CORE_SHIPPING_DOCS:
                if w != erp_base_data["expected_weight"] or q != erp_base_data["expected_qty"]:
                    erp_status = "❌ 账实不符(冲突)"
                else:
                    erp_status = "✅ 账实一致"
        
        print(f"📄 {filename:<25} | {doc_type:<15} | 内部逻辑: {logic_check_result} | ERP: {erp_status}")
        
        records_for_excel.append({
            "原文件名": filename,
            "识别单据类型": doc_type,
            "生物/检疫准入": bio_compliance,
            "提取毛重(KG)": w,
            "提取件数": q,
            "截关时间(DDL)": cut_time_str,
            "剩余倒计时(Hrs)": time_to_ddl_hrs,
            "单证一致性": final_doc_status,
            "明细逻辑校验": logic_check_result,
            "金蝶ERP核对": erp_status
        })

    time_suffix = now.strftime("%Y%m%d_%H%M%S")
    default_excel_name = os.path.join(output_folder, "【控制塔看板】单证_明细_ERP核对预警.xlsx")
    fallback_excel_name = os.path.join(output_folder, f"【控制塔看板】单证_明细_ERP核对预警_{time_suffix}.xlsx")
    
    excel_name = default_excel_name
    df = pd.DataFrame(records_for_excel)

    def write_excel(target_path):
        from openpyxl.utils import get_column_letter
        with pd.ExcelWriter(target_path, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Control_Tower')
            ws = writer.sheets['Control_Tower']
            
            header_fill = PatternFill(start_color="203764", end_color="203764", fill_type="solid")
            header_font = Font(color="FFFFFF", bold=True)
            safe_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
            warning_fill = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
            danger_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
            
            for cell in ws[1]:
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center", vertical="center")

            for row in ws.iter_rows(min_row=2, max_row=len(records_for_excel)+1, min_col=1, max_col=10):
                for cell in row:
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                
                bio_cell = row[2]
                if "⚠️" in str(bio_cell.value):
                    bio_cell.fill = warning_fill
                    bio_cell.font = Font(color="9C0006", bold=True)
                    
                ddl_val = row[6].value
                if isinstance(ddl_val, (int, float)):
                    if ddl_val < 0:
                        row[5].fill = danger_fill
                        row[5].font = Font(color="9C0006", bold=True)
                        row[5].value = "⚠️ 逾期超时"
                    elif 0 <= ddl_val <= 24:
                        row[5].fill = warning_fill
                        row[5].font = Font(color="9C5700", bold=True)
                    else:
                        row[5].fill = safe_fill
                        row[5].font = Font(color="006100", bold=True)

                doc_status = row[7]
                logic_status = row[8]
                erp_status_cell = row[9]
                
                if "❌" in str(doc_status.value): doc_status.fill = danger_fill
                elif "✅" in str(doc_status.value): doc_status.fill = safe_fill
                
                if "⚠️" in str(logic_status.value): 
                    logic_status.fill = warning_fill
                    logic_status.font = Font(color="9C0006", bold=True)
                elif "✅" in str(logic_status.value): 
                    logic_status.fill = safe_fill
                    
                if "❌" in str(erp_status_cell.value):
                    erp_status_cell.fill = danger_fill
                    erp_status_cell.font = Font(color="9C0006", bold=True)
                elif "✅" in str(erp_status_cell.value):
                    erp_status_cell.fill = safe_fill

            for i, col_name in enumerate(df.columns):
                col_title_len = len(str(col_name).encode('gbk', errors='ignore'))
                try:
                    max_data_len = max(df[col_name].astype(str).apply(lambda x: len(x.encode('gbk', errors='ignore'))))
                except (ValueError, TypeError):
                    max_data_len = 0
                adjusted_width = min(max(col_title_len, max_data_len) + 4, 80)
                ws.column_dimensions[get_column_letter(i + 1)].width = adjusted_width

    try:
        write_excel(default_excel_name)
    except PermissionError:
        excel_name = fallback_excel_name
        write_excel(fallback_excel_name)

    print("\n" + "="*60)
    print(f"🎉 自动化完成！红黄绿控制塔看板已保存至: {excel_name}")
    
    if export_json:
        json_name = os.path.join(output_folder, f"audit_result_{time_suffix}.json" if excel_name == fallback_excel_name else "audit_result.json")
        with open(json_name, 'w', encoding='utf-8') as f:
            json.dump(extracted_results, f, ensure_ascii=False, indent=4)
        print(f"🔄 包含明细项的 JSON 数据已导出至: {json_name}")
        
    print("="*60 + "\n")
    
    return df, extracted_results

# ================= 步骤 7：原生 Streamlit UI 逻辑（无子进程、直接函数导入） =================
def render_streamlit_ui():
    import streamlit as st
    st.set_page_config(page_title="关务控制塔 v2.6", layout="wide")
    st.title("🚀 离线关务单证风控引擎 v2.6")
    st.markdown("集成最新税则对撞、大模型并发提取与行明细逻辑校验")

    input_folder = st.text_input("请输入包含单证 PDF 的文件夹路径:", value=os.getcwd())
    export_json = st.checkbox("同步导出 JSON 数据文件 (供外部 EDI 接入)", value=True)

    if st.button("🚀 开始全栈关务交叉核对", type="primary"):
        if not os.path.exists(input_folder):
            st.error("指定的文件夹路径不存在，请检查！")
        else:
            with st.spinner('⏳ 正在并发对接 SQLite 数据库与底层 AI 进行风控核对...'):
                output_dir = os.path.join(os.path.dirname(input_folder), "Result")
                
                # ✨ 【核心改进】直接在 Python 当前进程内存里调用主逻辑，无需生成 subprocess 外部命令！
                df, extracted_json = process_and_cross_check(
                    input_folder=input_folder,
                    output_folder=output_dir,
                    export_json=export_json
                )
                
                if df is not None:
                    st.success(f"🎉 审核完成！红黄绿控制塔看板及数据结果已存至：{output_dir}")
                    
                    st.subheader("📊 风控核对结果看板")
                    def color_format(val):
                        color = ''
                        if '❌' in str(val): color = '#FFC7CE'
                        elif '⚠️' in str(val): color = '#FFEB9C'
                        elif '✅' in str(val): color = '#C6EFCE'
                        return f'background-color: {color}' if color else ''
                    
                    st.dataframe(
                        df.style.map(color_format, subset=['生物/检疫准入', '单证一致性', '明细逻辑校验', '金蝶ERP核对']),
                        use_container_width=True
                    )
                    
                    if extracted_json:
                        st.subheader("📄 AI 提取与项号明细原始数据 (JSON)")
                        st.json(extracted_json)
                else:
                    st.warning("⚠️ 该目录下未扫描到可解析的单证 PDF 文件。")

if __name__ == "__main__":
    is_streamlit_run = False
    # 优先通过环境变量判定，彻底避免 API 版本差异导致的判断失效
    if os.environ.get("STREAMLIT_RUNNING") == "1":
        is_streamlit_run = True
    else:
        try:
            from streamlit.runtime.scriptrunner import get_script_run_ctx
            if get_script_run_ctx() is not None:
                is_streamlit_run = True
        except Exception:
            pass

    if is_streamlit_run:
        render_streamlit_ui()
    else:
        parser = argparse.ArgumentParser(description="🚀 离线关务单证风控引擎 v2.6")
        parser.add_argument("-i", "--input", help="指定包含待核对 PDF 的文件夹路径")
        parser.add_argument("-o", "--output", default=".", help="指定 Excel 及 JSON 的输出目录")
        parser.add_argument("--json", action="store_true", help="启用后，将同步输出 json 格式文件")
        parser.add_argument("--web", action="store_true", help="在当前 Python 环境下启动 Streamlit Web 界面")
        
        args = parser.parse_args()
        
        if args.web or (len(sys.argv) == 1):
            print("🌐 正在启动 Streamlit 可视化网页界面...")
            my_env = os.environ.copy()
            my_env["STREAMLIT_RUNNING"] = "1"
            cmd = [sys.executable, "-m", "streamlit", "run", os.path.abspath(__file__)]
            subprocess.run(cmd, env=my_env)
        else:
            process_and_cross_check(input_folder=args.input, output_folder=args.output, export_json=args.json)