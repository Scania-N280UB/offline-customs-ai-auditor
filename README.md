# 🚀 Offline Customs & Capacity Control Tower (离线关务与运力风控引擎 v2.6)

[ 🇨🇳 点击跳转至中文文档 / Click here for Chinese ](#chinese-version) | [ 🇬🇧 Click here for English README ](#english-version)

---

<a id="english-version"></a>
## 🇬🇧 English

> **An Enterprise-grade, 100% Offline AI Risk Control Engine for Bio-Pharma Supply Chain, Customs Auditing, and ERP Integration.**
> Zero cloud data upload · Async LLM Extraction · SQLite HS Tariff Reconciliation · Native Streamlit Web UI · Context-Aware Rule Engine

### 📌 Background & Pain Points

In international bio-pharma and cold-chain import/export freight operations, customs brokers and operations teams must manually cross-verify complex multi-document sets, including **Booking Confirmations**, **Air Waybills (HAWB/MAWB)**, **Commercial Invoices**, **Packing Lists**, and **Trade Contracts**.

Traditional manual verification faces several critical challenges:

* **High Risk of Document Discrepancies**: Inconsistencies in Package Count, Gross Weight, or Line-Item Amounts across multiple documents cause severe customs delays or fines.
* **Complex Compliance Requirements**: Special goods (e.g., cell cultures, reagents, dry ice) require mandatory quarantine approvals (**Q-type supervision condition**). Manual checking of HS codes against tariff databases is prone to visual fatigue.
* **Strict Data Security & Privacy**: Commercial secrets and pricing structures are strictly prohibited from being uploaded to public cloud AI services.

**Version 2.6 completely addresses these challenges via a hybrid native architecture: "Offline RapidOCR + Async Local LLM + SQLite Rule Engine + In-Memory Web UI."**

---

### ✨ Core Features (v2.6 Updates)

* 🖥️ **Native In-Memory Streamlit Web UI**: Seamlessly integrated UI execution eliminating subprocess loops. Double-click `start.bat` to launch the full-stack visualization dashboard in any browser.
* ⚡ **High-Performance Async Concurrency**: Built on `AsyncIO` and `httpx.AsyncClient`, processing multi-page PDF sets concurrently to minimize total processing time.
* ⚖️ **Context-Aware Logic Rule Engine**: Penetrates line items to validate `Quantity × Unit Price = Total Amount` with a 5% tolerance filter. Smart doc-type routing automatically applies line checks to Invoices/Contracts while exempting Air Waybills (HAWB weight-rate models).
* 🗄️ **SQLite HS Code & Tariff Alignment**: Automatically syncs official tariff CSV data into an offline SQLite database (`customs_hs_sample.db`). Automatically cross-checks extracted HS codes for **Condition Q (Quarantine Inspection)**.
* 🎯 **Optimized LLM Inference**: Fine-tuned for `Qwen2.5:3b` with deterministic options (`temperature: 0.0`, `num_predict: 1024`) and prompt engineering to eliminate AI hallucination.
* 🔗 **Kingdee ERP SDK Bridge**: Pre-packaged integration bridge for Kingdee K3Cloud WebAPI, supporting offline mock fallback when network connection is absent.
* 🚀 **Portable Launcher (`start.bat`)**: Auto-detects local Python/WinPython environments, installs missing dependencies via mirror servers, and ensures UTF-8 execution without CMD encoding crashes.

---

### 📂 Project Directory Structure

```text
auto-customs-control-tower/
├── README.md                           # Documentation
├── requirements.txt                    # Python dependencies list
├── auto_customs_control_tower_v2.6.py  # Core Full-Stack Engine (Web + CLI + Logic)
├── start.bat                           # Robust One-Click Windows Launcher
├── customs_hs_sample.db                # Offline generated SQLite tariff database
├── P020251231607833453633.csv          # Official customs tariff CSV (Auto-synced)
└── PDF_test_folder/                    # Test sample folder (Bio-pharma documents)
```

---

### 🛠️ Prerequisites & Quick Start

#### 1. Prerequisites
* **Python**: 3.9+ (System Python or Portable WinPython)
* **Ollama**: Download [Ollama](https://ollama.com/) locally and pull the target model:
```bash
ollama pull qwen2.5:3b
```

#### 2. Usage Guide

##### Method 1: Web UI Dashboard (Recommended)
1. Double-click **`start.bat`** in the root directory.
2. The launcher will verify dependencies and open your browser automatically.
3. Paste your document folder path (e.g., `E:\path\to\PDF_test_folder`) and click **"🚀 开始全栈关务交叉核对"**.
4. View real-time RGB risk indicators and download auto-formatted Excel reports.

##### Method 2: CLI Command Line
```bash
python auto_customs_control_tower_v2.6.py -i ./PDF_test_folder -o ./Result --json
```

---

### ⚙️ Architecture & Data Pipeline

```text
       ┌────────────────────────┐
       │ Multi-Document PDFs    │ (Booking, HAWB, Invoice, PL, Contract)
       └───────────┬────────────┘
                   │
         [RapidOCR + PyMuPDF] (Multi-page Full Text Extraction)
                   │
       ┌───────────┴────────────┐
       │ Async Ollama AI Client │ (httpx + asyncio, temp=0.0)
       └───────────┬────────────┘
                   │
     ┌─────────────┼─────────────────────────┐
     ▼             ▼                         ▼
[SQLite Tariff]  [Gross Weight/Qty]   [Context Rule Engine]
 Match HS Code   Cross-Check Docs     Doc-Type Filtering
 Condition Q?    mismatch check       Invoice Itemized: Qty * Price == Total?
     │             │                         │
     ▼             ▼                         ▼
 ⚠️ Bio Warning  🔴 Conflict Red Flag   ⚠️ Amount Calculation Exception
```

---

### ⚖️ License & Disclaimer
**All demonstration documents included in this project are synthetic, anonymized, and created strictly for testing purposes.**
This project is open-sourced under the [MIT License](LICENSE).

<br>

---

<a id="chinese-version"></a>
## 🇨🇳 中文说明

> **专为生物医药进出口、关务合规及冷链运力追踪设计的 100% 离线 AI 自动化风控引擎**
> 零数据上云 · 异步大模型并发抓取 · SQLite税则库对撞 · Streamlit原生Web端 · 上下文感知逻辑引擎

### 📌 项目背景与业务痛点

在国际空海运进出口及特种生物医药物流中，关务与单证人员需要对**订舱确认书 (Booking)**、**分运单 (HAWB)**、**商业发票 (Invoice)**、**装箱单 (Packing List)** 及 **买卖合同 (Contract)** 等多份 PDF 进行繁重的交叉比对。

传统人工审核存在以下瓶颈：
* **多单据一致性难保证**：件数（Package Count）、毛重（Gross Weight）跨单据不一致，极易引发海关报关报错或海关缉私扣货。
* **合规准入门槛高**：特种货物（细胞培养基、诊断试剂、人血浆制品）涉及**卫生检疫审批（Q类监管条件）**，人工逐行检索海关税则效率低且易漏看。
* **数据安全红线限制**：运单价格与客户单证包含核心商业机密，严禁上传至公有云大模型。

**v2.6 版本通过“离线视觉识别 + 异步大模型提取 + SQLite税则对撞 + 上下文逻辑校验引擎”架构彻底解决以上痛点。**

---

### ✨ v2.6 核心特性

* 🖥️ **原生内存直连 Web UI**：彻底重构为内存级 Streamlit 集成，告别多进程死循环与命令行闪退。双击 `start.bat` 即可拉起浏览器可视化看板。
* ⚡ **AsyncIO 异步并发引擎**：基于 `httpx` 实现多 PDF 单据 AI 提取任务的全异步并发，大幅压缩多单据处理的总等待时间。
* ⚖️ **上下文感知明细校验引擎 (RuleEngine)**：深入行明细校验 `数量 × 单价 = 总价`（包含 5% 浮动容错与负数防撞）；智能感知单据类型，自动对发票/合同卡关，豁免运单（HAWB 计费重量模式）与箱单。
* 🗄️ **SQLite 离线税则对撞**：自动将最新海关税则 CSV 数据同步入库 (`customs_hs_sample.db`)。自动比对单据 HS Code 并实时预警“**监管条件 Q（卫生检疫审批）**”及生物准入要求。
* 🎯 **本地大模型确定性调优**：深度调校 `Qwen2.5:3b` 推理参数（`temperature: 0.0`，`num_predict: 1024`），配合精准提示词工程消除幻觉，确保输出纯净 JSON。
* 🔗 **金蝶 ERP SDK 预留通道**：内置金蝶云·星空 (`k3cloud_webapi_sdk`) 官方 API 接口，支持断网自动回退至本地 CSV/Excel 台账账实比对。
* 🚀 **极简启动器 (`start.bat`)**：智能感应系统及绿色版 Python 环境，缺失依赖自动通过清华镜像补齐，彻底解决 CMD 字符断字与乱码问题。

---

### 📂 项目目录结构

```text
auto-customs-control-tower/
├── README.md                           # 详细说明文档
├── requirements.txt                    # Python 依赖包清单
├── auto_customs_control_tower_v2.6.py  # 核心风控引擎 (WebUI + 逻辑引擎 + API)
├── start.bat                           # 一键启动批处理脚本 (自动环境装配)
├── customs_hs_sample.db                # 离线 SQLite 税则数据库
├── P020251231607833453633.csv          # 海关官方税则 CSV 源文件 (用于自动同步)
└── PDF_test_folder/                    # 测试单据样例库 (含生物医药单证)
```

---

### 🛠️ 环境准备与快速上手

#### 1. 前置依赖环境
* **Python**：3.9+ (支持全局 Python 或便携版 WinPython)
* **Ollama**：安装 [Ollama](https://ollama.com/) 并提前拉取本地模型：
```bash
ollama pull qwen2.5:3b
```

#### 2. 使用指南

##### 方式一：Web 可视化控制台（推荐）
1. 双击运行根目录下的 **`start.bat`**。
2. 脚本会自动检查依赖并启动浏览器控制台。
3. 输入待扫描的 PDF 文件夹路径（如 `E:\path\to\PDF_test_folder`），点击 **“🚀 开始全栈关务交叉核对”**。
4. 网页端将实时渲染红黄绿风控看板，并同步生成格式化 Excel 与 JSON 数据文件。

##### 方式二：CLI 命令行模式
```bash
python auto_customs_control_tower_v2.6.py -i ./PDF_test_folder -o ./Result --json
```

---

### ⚙️ 数据处理与风控流程图

```text
       ┌────────────────────────┐
       │ 待审单据 PDF 集合      │ (包含 Booking, HAWB, Invoice, PL, Contract)
       └───────────┬────────────┘
                   │
         [RapidOCR + PyMuPDF] (多页图像/文本识别)
                   │
       ┌───────────┴────────────┐
       │ Async Ollama AI 提取   │ (httpx + asyncio 异步并发, temp=0.0)
       └───────────┬────────────┘
                   │
     ┌─────────────┼─────────────────────────┐
     ▼             ▼                         ▼
【SQLite 税则库】 【件重尺交叉核对】   【单据上下文规则引擎】
 匹配 HS Code     核心单据毛重/件数     判定单据类型:
 预警监管条件 Q   一致性比对           发票/合同行明细: 数量 × 单价 == 总价?
     │             │                         │
     ▼             ▼                         ▼
 ⚠️ 检疫准入预警  🔴 件重冲突红牌        ⚠️ 行明细金额异常拦截
```

---

### 🔒 免责与合规声明
**本仓库演示所用的所有单据均为脱敏合成数据，不包含任何真实企业 Logo、客户信息或商业机密。系统全程基于本地端侧运行，符合数据出境安全评估相关合规要求。**

### ⚖️ 开源许可证
本项目采用 [MIT License](LICENSE) 开源。
---

## 📅 版本演进历史 (Changelog)

* **v2.6 (Current)**：重构为原生内存直连与 `AsyncIO` 协程并发；引入 `RuleEngine` 单据类型卡关过滤（自动豁免 HAWB 运费模式）；优化 Ollama 确定性采样与 Token 截断控制。
* **v2.5**：集成海关官方税则 CSV 自动 ETL 进 SQLite 离线数据库；实现生物医药“Q类检疫条件”自动对撞预警。
* **v2.1 - v2.4**：引入多行明细逻辑防碰撞校验（`qty × unit_price = total_price`）；完成 Streamlit 网页可视化看板建设。
* **v2.0**：项目首次发布，实现基于 RapidOCR + Ollama(Qwen2.5) 的离线多单据件重尺基础交叉核对。