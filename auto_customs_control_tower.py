import os
import sys
import json
import time
import subprocess
import argparse
from datetime import datetime

# 全局变量声明
ocr_engine = None

# ================= 步骤 0：自动唤醒大模型引擎 =================
def ensure_ollama_running():
    import requests  # 延迟导入轻量网络库
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

# ================= 步骤 1：多页全量 OCR 扫描函数 =================
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

# ================= 步骤 2：AI 字段提取 =================
def extract_data_with_ai(raw_text, filename):
    import requests  
    system_prompt = f"""
    你是一个极其严谨的国际空海运单证数据提取程序。
    当前处理文件：【{filename}】。
    
    【绝对强制规则】
    1. Doc_Type: 从这5个中选1个："订舱确认书(Booking)", "运单(HAWB/MAWB)", "发票(Invoice)", "箱单(Packing List)", "贸易合同(Contract)"。
       - 文件名或标题含 PACKING LIST、PL 的优先判定为 "箱单(Packing List)"（哪怕里面含有 Waybill No 字段）。
       - 包含 Air Freight Departure Booking Confirmation、AFDBC、Flight 的识别为 "订舱确认书(Booking)"。
    2. Gross_Weight: 寻找 G.W., Gross Weight, WEIGHT 附近的最大浮点数 (如 1250.5)。
       - 【特别注意】：如果单据同时存在 N.W. (Net Weight) 和 G.W. (Gross Weight)，必须提取 G.W. (毛重)！绝对不要误提取 N.W.！找不到填 0.0。
    3. Quantity: 寻找 QTY, PKGS, PACKAGES 附近的整数件数 (如 50)。找不到填 0。
    4. Cut_Off_Time: 提取 截货/截关/ETD/SI Cut-off 时间，格式标准化为 "YYYY-MM-DD HH:MM"。若提取不到，填 "NONE"。
    
    必须且只能输出纯 JSON，格式如下：
    {{"Doc_Type": "箱单(Packing List)", "Gross_Weight": 1250.5, "Quantity": 50, "Cut_Off_Time": "NONE"}}
    """
    payload = {
        "model": "qwen2.5:3b",  
        "prompt": f"{system_prompt}\n\n待处理文本：\n{raw_text}",
        "stream": False,
        "format": "json"
    }

    try:
        response = requests.post("http://localhost:11434/api/generate", json=payload)
        response.raise_for_status()
        return json.loads(response.json()['response'])
    except Exception as e:
        print(f"[{filename}] AI 处理出错: {e}")
        return {"Doc_Type": "解析失败", "Gross_Weight": 0.0, "Quantity": 0, "Cut_Off_Time": "NONE"}

# ================= 步骤 3：数据对撞 + 控制塔红黄绿渲染 =================
def process_and_cross_check(input_folder=".", output_folder=".", export_json=False):
    import pandas as pd  
    import openpyxl
    from openpyxl.styles import PatternFill, Font, Alignment, Border, Side

    ensure_ollama_running()

    print("\n" + "="*60)
    print(f" 📂 v1.0 控制塔自动化引擎启动，开始扫描目录: {input_folder} ...")
    print("="*60)
    
    os.makedirs(output_folder, exist_ok=True)
    
    pdf_files = [f for f in os.listdir(input_folder) if f.lower().endswith('.pdf')]
    if not pdf_files:
        print("❌ 当前目录下未找到 PDF 文件。")
        return

    extracted_results = {}
    for file in pdf_files:
        file_path = os.path.join(input_folder, file)
        raw_text = extract_text_from_pdf(file_path)
        data_dict = extract_data_with_ai(raw_text, file)
        extracted_results[file] = data_dict
        
    records_for_excel = []
    weights_for_check = {}
    qty_for_check = {}
    
    print("\n" + "="*60)
    print(" 🔍 AI 离线数据抓取完毕，开始多单交叉核对 (Cross-Check)...")
    print("="*60)

    now = datetime.now()
    for filename, data in extracted_results.items():
        doc_type = data.get('Doc_Type', '未知')
        w = float(data.get('Gross_Weight', 0.0))
        q = int(data.get('Quantity', 0))
        cut_time_str = data.get('Cut_Off_Time', 'NONE')
        
        time_to_ddl_hrs = "N/A"
        if cut_time_str != "NONE":
            try:
                dt_target = datetime.strptime(cut_time_str, "%Y-%m-%d %H:%M")
                hours_diff = round((dt_target - now).total_seconds() / 3600, 1)
                time_to_ddl_hrs = hours_diff
            except Exception:
                pass

        print(f"📄 文件: {filename:<32} | 类型: {doc_type:<15} | 毛重: {w} KG | 件数: {q} | DDL: {cut_time_str}")
        
        records_for_excel.append({
            "原文件名": filename,
            "识别单据类型": doc_type,
            "提取毛重(KG)": w,
            "提取件数": q,
            "截关时间(DDL)": cut_time_str,
            "剩余倒计时(Hrs)": time_to_ddl_hrs,
            "核对状态": "待判定"
        })
        
        if w > 0: weights_for_check[doc_type] = w
        if q > 0: qty_for_check[doc_type] = q

    weight_mismatch = len(set(weights_for_check.values())) > 1 if len(weights_for_check) > 1 else False
    qty_mismatch = len(set(qty_for_check.values())) > 1 if len(qty_for_check) > 1 else False
    has_data_error = weight_mismatch or qty_mismatch

    excel_name = os.path.join(output_folder, "【控制塔看板】单证交叉核对及运力预警.xlsx")
    df = pd.DataFrame(records_for_excel)

    with pd.ExcelWriter(excel_name, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Control_Tower')
        ws = writer.sheets['Control_Tower']
        
        header_fill = PatternFill(start_color="203764", end_color="203764", fill_type="solid")
        header_font = Font(color="FFFFFF", bold=True)
        safe_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
        warning_fill = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
        danger_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
        safe_font = Font(color="006100", bold=True)
        warning_font = Font(color="9C5700", bold=True)
        danger_font = Font(color="9C0006", bold=True)
        center_align = Alignment(horizontal="center", vertical="center")
        
        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = center_align

        for i, row in enumerate(ws.iter_rows(min_row=2, max_row=len(records_for_excel)+1, min_col=1, max_col=7)):
            for cell in row:
                cell.alignment = center_align
            status_cell = row[6]
            ddl_val = row[5].value

            if has_data_error:
                status_cell.fill = danger_fill
                status_cell.font = danger_font
                status_cell.value = "❌ 高危：件重尺数据冲突"
            elif isinstance(ddl_val, (int, float)):
                if ddl_val < 0:
                    status_cell.fill = danger_fill
                    status_cell.font = danger_font
                    status_cell.value = "⚠️ 逾期：截关节点已超时"
                elif 0 <= ddl_val <= 24:
                    status_cell.fill = warning_fill
                    status_cell.font = warning_font
                    status_cell.value = "⏳ 警告：24h内即将截关"
                else:
                    status_cell.fill = safe_fill
                    status_cell.font = safe_font
                    status_cell.value = "✅ 正常：单据一致且时间充裕"
            else:
                if not has_data_error:
                    status_cell.fill = safe_fill
                    status_cell.font = safe_font
                    status_cell.value = "✅ 正常：单据一致"

        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = col[0].column_letter
            ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    print("\n" + "="*60)
    print(f"🎉 自动化完成！红黄绿控制塔看板已保存至: {excel_name}")
    
    if export_json:
        json_name = os.path.join(output_folder, "audit_result.json")
        with open(json_name, 'w', encoding='utf-8') as f:
            json.dump(records_for_excel, f, ensure_ascii=False, indent=4)
        print(f"🔄 系统级接口数据已同步导出至: {json_name}")
        
    print("="*60 + "\n")

# ================= 步骤 4：原生轻量 GUI 界面 =================
def launch_gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox

    root = tk.Tk()
    root.title("🚀 离线关务单证风控引擎 v1.0")
    root.geometry("480x280")
    root.resizable(False, False)

    input_path_var = tk.StringVar(value=os.getcwd())
    export_json_var = tk.BooleanVar(value=True)

    def select_folder():
        folder = filedialog.askdirectory(title="选择包含单证 PDF 的文件夹")
        if folder:
            input_path_var.set(folder)

    def start_audit():
        folder = input_path_var.get()
        if not os.path.exists(folder):
            messagebox.showerror("错误", "指定的文件夹路径不存在！")
            return
        
        btn_start.config(state="disabled", text="⏳ 正在风控核对中...")
        root.update()
        
        # 【关键修改】：使用 os.path.dirname(folder) 获取上一级目录 (notebooks 目录)
        output_dir = os.path.join(os.path.dirname(folder), "Result")
        
        try:
            process_and_cross_check(
                input_folder=folder, 
                output_folder=output_dir,  # 👈 结果将直接输出到 notebooks\Result
                export_json=export_json_var.get()
            )
            messagebox.showinfo("成功", f"🎉 单证风控已完成！\n看板及结果已存至：\n{output_dir}")
        except Exception as e:
            messagebox.showerror("异常", f"运行出错：{str(e)}")
        finally:
            btn_start.config(state="normal", text="🚀 开始单证交叉核对")
    tk.Label(root, text="离线关务单证风控引擎", font=("Microsoft YaHei", 14, "bold")).pack(pady=15)

    frame_path = tk.Frame(root)
    frame_path.pack(fill="x", padx=20, pady=5)
    tk.Entry(frame_path, textvariable=input_path_var, width=38).pack(side="left", padx=5)
    tk.Button(frame_path, text="选择文件夹", command=select_folder).pack(side="left")

    tk.Checkbutton(root, text="同步导出 JSON 数据文件 (供 ERP / EDI 接入)", variable=export_json_var).pack(pady=10)

    btn_start = tk.Button(root, text="🚀 开始单证交叉核对", font=("Microsoft YaHei", 11, "bold"), bg="#203764", fg="white", command=start_audit)
    btn_start.pack(ipady=5, ipadx=20, pady=15)

    root.mainloop()

# ================= 入口路由 (统一判断运行模式) =================
if __name__ == "__main__":
    # 只要带有任何参数 (比如 --help，或者 -i folder)，就走终端命令行模式
    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser(description="🚀 离线关务单证风控引擎 (Offline Customs AI Auditor)")
        parser.add_argument("-i", "--input", default=".", help="指定包含待核对 PDF 的文件夹路径 (默认: 当前目录)")
        parser.add_argument("-o", "--output", default=".", help="指定 Excel 及 JSON 的输出目录 (默认: 当前目录)")
        parser.add_argument("--json", action="store_true", help="启用后，将同步输出 json 格式文件")
        
        args = parser.parse_args()
        process_and_cross_check(input_folder=args.input, output_folder=args.output, export_json=args.json)
    
    # 没有任何参数（鼠标直接双击运行），就弹出 GUI 图形界面
    else:
        launch_gui()