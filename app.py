import os
import sys
import subprocess

if __name__ == "__main__":
    if os.environ.get("STREAMLIT_RUNNING") == "1":
        try:
            from auto_customs_control_tower_v2_6_2 import render_streamlit_ui
            render_streamlit_ui()
        except Exception as e:
            import streamlit as st
            st.error(f"❌ 加载核心模块失败: {e}")
    else:
        engine_file = "auto_customs_control_tower_v2_6_2.py"
        if not os.path.exists(engine_file):
            print(f"\n❌ 未找到核心文件：{engine_file}，请检查文件名中是否混入了空格！\n")
            sys.exit(1)

        print("🌐 正在启动 Streamlit 控制塔主界面，请稍候...")
        my_env = os.environ.copy()
        my_env["STREAMLIT_RUNNING"] = "1"
        cmd = [sys.executable, "-m", "streamlit", "run", os.path.abspath(__file__)]
        subprocess.run(cmd, env=my_env)