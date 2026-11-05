# 🚀 Offline Customs AI Auditor (离线关务单证风控引擎)

[ 🇨🇳 点击跳转至中文文档 / Click here for Chinese ](#chinese-version) | [ 🇬🇧 Click here for English README ](#english-version)

---

<a id="english-version"></a>
## 🇬🇧 English

> **An offline AI automated data reconciliation system designed for international logistics and customs risk control.**
> Zero cloud data upload · Millisecond-level lazy loading response · Offline LLM extraction · Visual RGB Control Tower dashboard

### 📌 Background & Pain Points

In international air and ocean freight import/export operations, customs and documentation personnel must manually cross-verify multiple PDF files, including **Booking Confirmations**, **Commercial Invoices**, **Packing Lists**, and **Trade Contracts**.

Traditional manual verification faces several critical challenges:

* **Inefficiency and Omission Risks**: Inconsistencies in Commodity Name, Package Count, or Gross Weight across multiple documents lead to customs declaration errors.
* **Uncontrollable Cut-Off Risks**: Cut-Off Time nodes are scattered within unstructured documents. A lack of dynamic countdown alerts easily leads to demurrage fees or rolled cargo risks.
* **Strict Data Security Compliance**: Commercial secrets and confidential customer documents are strictly prohibited from being uploaded to public cloud LLMs.

**This tool completely resolves the above challenges via a hybrid architecture: "Offline Visual Recognition + Local LLM Extraction + Logical Data Reconciliation."**

---

### ✨ Core Features

* 🔒 **Fully Offline Risk Control & Data Security**: Built on the `RapidOCR` visual recognition engine and the `Ollama` (Qwen2.5:3b) local neural network. All data processing is strictly executed on the local host or portable USB environment—zero cloud data leakage.
* ⚡ **High-Performance Lazy Loading**: Heavy dependencies (OCR weights, Pandas, OpenPyXL) utilize function-level delayed imports. The command-line `--help` and desktop GUI achieve a **millisecond-level instant startup (0.05s)**.
* 🤖 **AI Engine Silent Wake-up**: Built-in background daemon logic automatically detects Ollama's offline status to complete background pre-warming and compute thread takeover, requiring no manual CLI commands to launch the service.
* 🖥️ **Dual-Modal Seamless Routing (CLI & GUI)**:
  * **GUI Desktop Mode**: Non-technical operators can double-click the `.bat` file to open a clean, lightweight graphical window and drag-and-drop folders for one-click verification.
  * **CLI Pipeline Mode**: Supports `-i`, `-o`, `--json` parameters for seamless integration into existing enterprise ERP / EDI pipelines.
* 📊 **Control Tower Warning Dashboard**:
  * Automatically outputs a colored Excel dashboard with a dark blue stylized header that meets enterprise aesthetic standards.
  * **Red Alert (High Risk)**: Critical discrepancy in Package/Weight/Volume across documents, or Cut-Off deadline expired.
  * **Yellow Warning**: Cut-Off node enters the 24-hour warning window.
  * **Green Pass**: Highly consistent data with a sufficient time buffer.
  * Synchronously exports structured `.json` files for downstream API consumption.

---

### 📂 Project Directory Structure

```text
auto-customs-control-tower/
├── .gitignore                          # Git ignore rules
├── README.md                           # Documentation
├── requirements.txt                    # Python dependencies list
├── auto_customs_control_tower.py       # Core Engine source code (CLI/GUI)
├── 【双击启动】关务风控引擎.bat          # Windows batch script to auto-detect env and launch GUI
└── PDF_test_folder/                    # Test sample folder
    ├── AFDB_sample.pdf                 # Booking Confirmation sample
    ├── Commercial_Invoice_AGS.pdf      # Commercial Invoice sample
    ├── Packing_List_AGS.pdf            # Packing List sample
    └── Trade_Contract_AGS.pdf          # Sales Contract sample
```

---

### 🛠️ Prerequisites & Installation

#### 1. Prerequisites

* **Python**: 3.9+ (or portable WinPython release with a complete environment)
* **Ollama**: Need to install [Ollama](https://ollama.com/) and pull the LLM in advance:
```bash
ollama pull qwen2.5:3b
```

#### 2. Install Dependencies

Run the following command in the project root directory:

```bash
pip install -r requirements.txt
```

*(Contents of `requirements.txt`:)*
```text
pymupdf
pandas
openpyxl
rapidocr_onnxruntime
requests
```

---

### 🚀 Usage Guide

#### Method 1: GUI Desktop Mode (For Business Operators)

Directly double-click the **`【双击启动】关务风控引擎.bat`** in the run directory:

1. Select the folder containing PDF documents in the pop-up window (e.g., `PDF_test_folder`).
2. Click **"🚀 开始单证交叉核对"** (Start Cross-Verification).
3. The system will automatically generate a colored Excel warning dashboard and JSON file in the sibling `notebooks/Result` directory.

#### Method 2: CLI Mode / System Automation Integration

```bash
# Display standard help menu (millisecond response)
python auto_customs_control_tower.py --help

# Specify input & output directories, and export JSON
python auto_customs_control_tower.py -i ./PDF_test_folder -o ./Result --json
```

---

### ⚙️ Risk Reconciliation Logic

After offline field extraction, the system automatically executes the following cross-verification rules:

```text
       ┌────────────────────────┐
       │ PDF Document Library   │
       └───────────┬────────────┘
                   │
         [RapidOCR + Qwen2.5]
                   │
       ┌───────────┴────────────┐
       │ Extract Weight/Qty/DDL │
       └───────────┬────────────┘
                   │
     ┌─────────────┴─────────────┐
     ▼                           ▼
[Qty/Weight Validation]     [Cut-off Countdown Validation]
 len(set(Weights)) > 1?     hours_to_ddl < 0  => 🔴 Expired/Overdue
         │                  0 <= hours <= 24  => 🟡 24h Warning
         ├─ Yes ───────────► hours > 24       => 🟢 Sufficient Time
         │                  (🔴 Conflict Priority Highest)
         ▼
 🔴 Data Conflict Flagged
```

---

### ⚖️ License

This project is open-sourced under the [MIT License](https://www.google.com/search?q=LICENSE). Issues and PRs are welcome to collaboratively improve the customs automation risk control algorithm!

<br>
<br>
<img width="2878" height="1688" alt="屏幕截图 2026-11-05 111924" src="https://github.com/user-attachments/assets/672edbc6-6ad5-4807-899c-dade4cab0efc" />
<img width="2878" height="1799" alt="屏幕截图 2026-11-05 112010" src="https://github.com/user-attachments/assets/4b057ca2-1821-4cc8-8c3c-897a0526fd87" />


---

<a id="chinese-version"></a>
## 🇨🇳 中文说明

> **专为国际物流与关务风控设计的离线 AI 自动化数据核对系统**
> 零数据上云 · 毫秒级懒加载响应 · 离线大模型抽取 · 视觉红黄绿控制塔看板

### 📌 项目背景与痛点

在国际空海运进出口业务中，关务与单证人员需要手工核对**订舱确认书 (Booking)**、**商业发票 (Invoice)**、**装箱单 (Packing List)** 及 **贸易合同 (Contract)** 等多份 PDF 文件。

传统人工审核存在以下痛点：

* **效率低下且易漏看**：品名、件数、毛重（Gross Weight）在多单据间数据不一致导致报关报错。
* **截关风险难把控**：截关 / 截货时间（Cut-Off Time）节点混杂在单据中，缺乏动态倒计时预警，易产生滞港费或掉船风险。
* **数据安全合规要求极高**：商业机密及客户单据严禁上传至公有云大模型。

**本工具通过“离线视觉识别 + 本地大模型抽取 + 逻辑数据对撞”架构，彻底解决上述难题。**

---

### ✨ 核心特性

* 🔒 **全离线风控 & 数据安全**：基于 `RapidOCR` 视觉识别引擎与 `Ollama` (Qwen2.5:3b) 本地神经网络，所有数据处理均在本地或 U 盘便携环境中完成，数据零上云。
* ⚡ **高能懒加载架构 (Lazy Loading)**：重型依赖库（OCR 权重、Pandas、OpenPyXL）采用函数级延迟导入，命令行 `--help` 及桌面 GUI 界面实现 **0.05 秒毫秒级秒开**。
* 🤖 **AI 引擎静默唤醒**：内置后台守护逻辑，检测到 Ollama 离线时自动完成后台预热与算力接管，无需手动敲命令行拉起服务。
* 🖥️ **双模态无缝路由 (CLI & GUI)**：
  * **GUI 桌面模式**：普通业务人员双击 `.bat` 启动干净的轻量图形窗口，拖选文件夹即可一键核对。
  * **CLI 命令行模式**：支持 `-i`、`-o`、`--json` 参数，可无缝嵌入企业现有的 ERP / EDI 系统流水线。
* 📊 **控制塔预警看板 (Control Tower)**：
  * 自动输出符合企业审美标准的深蓝表头彩色 Excel 报表。
  * **红色高危**：单据间件重尺冲突，或 DDL 截关已超时。
  * **黄色警告**：截关节点进入 24 小时临期预警。
  * **绿色正常**：数据高度一致且时间充裕。
  * 同步输出结构化 `.json` 文件供下游 API 调用。

---

### 📂 项目目录结构

```text
auto-customs-control-tower/
├── .gitignore                          # Git 忽略规则文件
├── README.md                           # 项目说明文档
├── requirements.txt                    # 项目 Python 依赖清单
├── auto_customs_control_tower.py       # 核心风控引擎源码 (含 CLI/GUI)
├── 【双击启动】关务风控引擎.bat          # Windows 自动寻找环境并拉起 GUI 的批处理脚本
└── PDF_test_folder/                    # 测试样例文件夹
    ├── AFDB_sample.pdf                 # 订舱确认书样例
    ├── Commercial_Invoice_AGS.pdf      # 发票样例
    ├── Packing_List_AGS.pdf            # 箱单样例
    └── Trade_Contract_AGS.pdf          # 贸易合同样例
```

---

### 🛠️ 环境准备与依赖安装

#### 1. 前置环境要求

* **Python**：3.9+ (或环境完整的 WinPython 便携版)
* **Ollama**：需安装 [Ollama](https://ollama.com/) 并提前拉取大模型：
```bash
ollama pull qwen2.5:3b
```

#### 2. 安装依赖库

在项目根目录下运行：

```bash
pip install -r requirements.txt
```

*(附 `requirements.txt` 内容：)*
```text
pymupdf
pandas
openpyxl
rapidocr_onnxruntime
requests
```

---

### 🚀 使用指南

#### 方式一：GUI 桌面图形界面（适合业务人员）

直接双击运行目录下的 **`【双击启动】关务风控引擎.bat`**：

1. 在弹出的窗口中选择包含 PDF 单证的文件夹（如 `PDF_test_folder`）。
2. 点击 **“🚀 开始单证交叉核对”**。
3. 系统将自动在同级 `notebooks/Result` 目录下生成彩色 Excel 预警看板及 JSON 文件。

#### 方式二：CLI 命令行 / 系统自动化集成

```bash
# 查阅标准说明菜单 (毫秒级响应)
python auto_customs_control_tower.py --help

# 指定输入与输出目录，并导出 JSON
python auto_customs_control_tower.py -i ./PDF_test_folder -o ./Result --json
```

---

### ⚙️ 风控比对逻辑

系统在离线抓取单证字段后，会自动执行以下交叉核值得核对规则：

```text
       ┌────────────────────────┐
       │ PDF 待测单据库 (扫描)   │
       └───────────┬────────────┘
                   │
         [RapidOCR + Qwen2.5]
                   │
       ┌───────────┴────────────┐
       │ 提取毛重 / 件数 / DDL   │
       └───────────┬────────────┘
                   │
     ┌─────────────┴─────────────┐
     ▼                           ▼
【件重尺校验】             【截关倒计时校验】
 len(set(Weights)) > 1?     hours_to_ddl < 0  => 🔴 超时逾期
         │                  0 <= hours <= 24  => 🟡 24h 警告
         ├─ Yes ───────────► hours > 24       => 🟢 时间充裕
         │                  (🔴 冲突优先级最高)
         ▼
 🔴 数据冲突打红标
```

---

### ⚖️ 许可证

本项目基于 [MIT License](https://www.google.com/search?q=LICENSE) 开源，欢迎提交 Issue 与 PR 共同完善关务自动化风控算法。
