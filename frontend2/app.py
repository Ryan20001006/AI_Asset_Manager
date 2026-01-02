import streamlit as st
import requests
import pandas as pd
import json
import altair as alt


st.set_page_config(layout="wide", page_title="Stock AI Agent")

if 'active_symbol' not in st.session_state:
    st.session_state.active_symbol = None

def set_ticker(symbol):
    st.session_state.ticker_input = symbol  
    st.session_state.active_symbol = symbol
    st.session_state.auto_run_analysis = True     
    st.session_state.search_results = []

st.markdown("""
<h1 style='text-align: center; color: navy;'>
    Stock Fundamental Analysis Agent
</h1>
<p style='text-align: center; color: #100; font-size: 24px;'>
    Powered by AI-driven financial insights
</p>
""", unsafe_allow_html=True)

session = requests.Session()
session.trust_env = False  

if 'auto_run_analysis' not in st.session_state:
    st.session_state.auto_run_analysis = False

with st.sidebar:
    st.header("Control Panel")
    

    st.header("Data Source")
    data_source = st.radio(
    "",  
    ("Yahoo Finance (4 Years Historical)", "Alpha Vantage (5 Years Historical)"),
    help="Choose your preferred financial data source."
)
    
    if data_source == "Yahoo Finance (4 Years Historical)":
        BACKEND_URL = "http://localhost:8000"
    else:
        BACKEND_URL = "http://localhost:8001"

    st.success(f"Current Source: {data_source}")
    st.divider()
    # 1. 輸入框
    current_input = st.text_input("", value="", key="ticker_input").upper()

    if st.button("Start Searching"):
        if current_input:
            try:
                with st.spinner("Searching..."):
                    res = session.get(f"{BACKEND_URL}/api/search", params={"keyword": current_input})
                    if res.status_code == 200:
                        st.session_state.search_results = res.json().get("data", [])
                    else:
                        st.error("Searching Failed")
            except Exception as e:
                st.error(f"Connection Error: {e}")
        else:
            st.warning("Type in keywords")

    if 'search_results' in st.session_state and st.session_state.search_results:
        st.caption("Select a company:")
        for i, item in enumerate(st.session_state.search_results):
            st.markdown(f"**{item['symbol']}** - {item['name']}")
            st.button(
                f"Analyze {item['symbol']}", 
                key=f"btn_{item['symbol']}_{i}", 
                on_click=set_ticker,      
                args=(item['symbol'], )   
            )
            st.divider()
    ticker = st.session_state.active_symbol

    if not ticker:
        st.info("Please search and select a stock from the sidebar")
        st.stop()

    
  
tab1, tab2, tab3, tab4, tab5= st.tabs(["Investment memo", "Financial stats", "Ask AI", "Charts", "Tech Analysis"])


with tab1:
    st.subheader(f"{ticker} Investment Memo")

    if st.button("✨ Generate New AI Memo ", key="btn_ai_gen"):
        with st.spinner(f"AI is analyzing {ticker} ... (Please wait 10-20s)"):
            try:
                response = session.post(f"{BACKEND_URL}/api/analyze_ai/{ticker}")
                
                if response.status_code == 200:
                    st.success("Analysis Complete!")
                    st.rerun() 
                else:
                    st.error(f"Analysis failed: {response.text}")
            except Exception as e:
                st.error(f"Connection failed: {e}")

    st.divider()

    try:
        res = session.get(f"{BACKEND_URL}/api/get_ai_report/{ticker}")
        if res.status_code == 200:
            report_data = res.json()
            
            if "news_analysis" in report_data:
                st.caption(f"Last Updated: {report_data.get('date', 'Unknown')}")
                
                st.markdown("### News & Market Perspective")
                st.markdown(report_data['news_analysis'])
                
                #st.markdown("---")
                
                #st.markdown("### Competitor Analysis")
                #st.markdown(report_data['competitor_analysis'])
            else:
                st.info("No report found. Click the button above to generate one.")
        else:
            st.info("No report found. Click the button above to generate one.")
            
    except Exception as e:
        st.error(f"Failed to load report: {e}")

with tab2:
    st.subheader(f"{ticker} Fundamental Finance Data")
    
    if st.button(f"Download {ticker} Data", key="btn_fetch_data"):
        st.session_state.auto_run_analysis = True
        st.rerun()

    should_run = False
    
        
    if st.session_state.get('auto_run_analysis'):
        should_run = True
        st.session_state.auto_run_analysis = False  

    if should_run:
        with st.spinner(f"Downloading {ticker} data..."):
            try:
                payload = {"ticker": ticker}
                response = session.post(f"{BACKEND_URL}/api/analyze", json=payload)
                
                if response.status_code == 200:
                    data = response.json().get("data", [])
                    if data:
                        df = pd.DataFrame(data)
                        st.session_state['fundamental_df'] = df
                        display_cols = ['ReportYear', 'Category', 'RatioName', 'RatioValue', 'Formula']
                        st.dataframe(df[display_cols], use_container_width=True)
                    else:
                        st.warning("No data found")
                else:
                    st.error(f"API error: {response.text}")
            except Exception as e:
                st.error(f"Connection fail: {e}")

            
with tab3:
    st.subheader("Ask BDFGPT")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input(""):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            
            with st.spinner("Please wait for response"):
                try:
                    payload = {"message": prompt}
                    res = session.post(f"{BACKEND_URL}/api/agent-chat", json=payload)
                    
                    if res.status_code == 200:
                        result = res.json()
                        ai_reply = result.get("reply", result.get("message", "無回應"))
                        
                        if result.get("status") == "analysis_complete":
                            st.toast(f"Loaded {result.get('ticker')} data to the chat", icon="✅")
                        
                        message_placeholder.markdown(ai_reply)
                        full_response = ai_reply
                    else:
                        message_placeholder.error(f"API Error: {res.text}")
                except Exception as e:
                    message_placeholder.error(f"Connection Error: {e}")
            
            if full_response:
                st.session_state.messages.append({"role": "assistant", "content": full_response})


with tab4:
    st.subheader(f"📈 {ticker} Historical Financial Trends")
    
    # Check if data exists in session state
    if 'fundamental_df' in st.session_state and not st.session_state['fundamental_df'].empty:
        df = st.session_state['fundamental_df'].copy()
        
        # 1. FIX: Convert Year to String to remove comma (e.g., 2,025 -> 2025)
        df['ReportYear'] = df['ReportYear'].astype(str)
        
        # 2. Define Metrics Groups
        metrics_groups = {
            "Profitability (Margins)": [
                'Gross Margin', 
                'Operating Margin', 
                'Net Profit Margin'
            ],
            "Return Ratios": [
                'Return on Equity (ROE)', 
                'ROIC'
            ],
            "Growth Rates": [
                'Revenue Growth', 
                'Net Income Growth', 
                'EPS Growth', 
                'FCF Growth'
            ],
            "Leverage & Solvency": [
                'Debt-to-Equity Ratio', 
                'Current Ratio', 
                'Interest Coverage Ratio', 
                'Net Debt / EBITDA'
            ],
            "Efficiency": [
                'Asset Turnover', 
                'Inventory Turnover', 
                'Receivables Turnover'
            ]
        }
        
        # 3. Define Percentage Metrics (Data is 0.15, we want to show 15%)
        percentage_metrics = [
            'Gross Margin', 'Operating Margin', 'Net Profit Margin',
            'Return on Equity (ROE)', 'ROIC',
            'Revenue Growth', 'Net Income Growth', 'EPS Growth', 'FCF Growth',
            'Debt-to-Equity Ratio' 
        ]

        # 4. UI Selection
        selected_group = st.selectbox("📊 Select Analysis Category:", list(metrics_groups.keys()) + ["Custom Metrics"])

        if selected_group == "Custom Metrics":
            # Get all unique ratio names
            all_ratios = df['RatioName'].unique().tolist()
            selected_metrics = st.multiselect("Select Metrics to Compare:", all_ratios, default=['Return on Equity (ROE)'])
        else:
            target_metrics = metrics_groups[selected_group]
            # Filter metrics that exist in the data
            available_metrics = df['RatioName'].unique().tolist()
            selected_metrics = [m for m in target_metrics if m in available_metrics]

        # 5. Filter Data for Charting
        if selected_metrics:
            st.markdown(f"##### {selected_group} Trends")
            
            # Filter rows based on selection
            chart_df = df[df['RatioName'].isin(selected_metrics)]
            
            # Check if we should format as Percentage
            # (If ALL selected metrics are percentage types, apply % formatting)
            is_percentage = all(m in percentage_metrics for m in selected_metrics)
            
            # 6. Build Altair Chart
            # Altair handles "Long Format" data natively (no need to pivot!)
            
            # Base Chart
            base = alt.Chart(chart_df).encode(
                x=alt.X('ReportYear', axis=alt.Axis(title='Year')), # Year as X-axis
                color=alt.Color('RatioName', legend=alt.Legend(title="Metric")) # Line color by Metric
            )
            
            if is_percentage:
                # Apply % formatting to Y-axis and Tooltip
                line_chart = base.mark_line(point=True).encode(
                    y=alt.Y('RatioValue', axis=alt.Axis(format='%', title='Percentage')),
                    tooltip=[
                        alt.Tooltip('ReportYear', title='Year'),
                        alt.Tooltip('RatioName', title='Metric'),
                        alt.Tooltip('RatioValue', format='.2%', title='Value') # Shows 15.20%
                    ]
                )
            else:
                # Standard formatting (e.g., for Turnover ratios)
                line_chart = base.mark_line(point=True).encode(
                    y=alt.Y('RatioValue', axis=alt.Axis(title='Value')),
                    tooltip=[
                        alt.Tooltip('ReportYear', title='Year'),
                        alt.Tooltip('RatioName', title='Metric'),
                        alt.Tooltip('RatioValue', format='.2f', title='Value')
                    ]
                )

            st.altair_chart(line_chart, use_container_width=True)
            
            # 7. Data Table Display
            with st.expander("View Detailed Historical Data"):
                # Pivot for readable table view
                table_view = chart_df.pivot(index='ReportYear', columns='RatioName', values='RatioValue')
                
                # Apply Style formatting
                # We build a format dictionary: {'ROE': '{:.2%}', 'Current Ratio': '{:.2f}'}
                format_dict = {
                    col: "{:.2%}" if col in percentage_metrics else "{:.2f}" 
                    for col in table_view.columns
                }
                
                # Display styled dataframe
                st.dataframe(table_view.style.format(format_dict))
                
        else:
            st.warning("⚠️ Insufficient historical data for this category.")
            
    else:
        st.info("💡 Please go to **Tab 1** or use the **Search** sidebar to fetch data first.")
    
    st.divider()

    st.subheader("🕯️ Daily Price History (Last 2 Years)")
    price_hist_key = f"price_hist_{ticker}"

    try:
        with st.spinner("Loading price history..."):
            hist_res = session.get(f"{BACKEND_URL}/api/history/{ticker}", params={"period": "2y"})
            
            if hist_res.status_code == 200:
                hist_data = hist_res.json()
                if hist_data.get("status") == "success":
                    prices = hist_data.get("data", [])
                    price_df = pd.DataFrame(prices)
                    
                    if not price_df.empty:
                        # 建立 Altair 圖表
                        # 上半部：股價線圖
                        price_chart = alt.Chart(price_df).mark_line(color='#2962FF').encode(
                            x=alt.X('Date:T', axis=alt.Axis(title='Date', format='%Y-%m')),
                            y=alt.Y('Close:Q', scale=alt.Scale(zero=False), axis=alt.Axis(title='Price')),
                            tooltip=['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
                        ).properties(
                            height=300,
                            title=f"{ticker} Close Price"
                        )
                        
                        # 下半部：成交量棒狀圖
                        vol_chart = alt.Chart(price_df).mark_bar(color='#cfd8dc').encode(
                            x=alt.X('Date:T', axis=alt.Axis(labels=False)), # 隱藏 X 軸標籤以免重疊
                            y=alt.Y('Volume:Q', axis=alt.Axis(title='Volume', format='.2s')),
                            tooltip=['Date', 'Volume']
                        ).properties(
                            height=100
                        )
                        
                        # 組合圖表 (上下排列)
                        combined_chart = alt.vconcat(price_chart, vol_chart).resolve_scale(
                            x='shared' # 共用 X 軸
                        )
                        
                        st.altair_chart(combined_chart, use_container_width=True)
                    else:
                        st.warning("No price data available.")
                else:
                    st.warning(f"Could not load history: {hist_data.get('message')}")
    except Exception as e:
        st.error(f"Failed to load chart: {e}")

    st.divider()

    st.subheader("🔙 5-Year Return Backtest (vs S&P 500)")
    
    if st.button("Run Backtest"):
        with st.spinner("Calculating historical returns..."):
            try:
                res = session.get(f"{BACKEND_URL}/api/backtest/{ticker}")
                if res.status_code == 200:
                    bt_data = res.json()
                    
                    if bt_data.get("status") == "success":
                        metrics = bt_data['metrics']['stock']
                        bench = bt_data['metrics']['benchmark']
                        
                        # 1. 顯示指標卡片
                        col1, col2, col3, col4 = st.columns(4)
                        col1.metric("Total Return", f"{metrics['total_return']:.2%}", delta=f"{metrics['total_return'] - bench['total_return']:.2%}")
                        col2.metric("CAGR (Yearly)", f"{metrics['cagr']:.2%}")
                        col3.metric("Max Drawdown", f"{metrics['max_drawdown']:.2%}")
                        col4.metric("Sharpe Ratio", f"{metrics['sharpe_ratio']:.2f}")
                        
                        # 2. 畫圖 (累計報酬率)
                        chart_data = pd.DataFrame(bt_data['chart_data'])
                        
                        # Altair 繪圖
                        base = alt.Chart(chart_data).encode(x='date:T')
                        
                        line1 = base.mark_line(color='blue').encode(
                            y=alt.Y('stock_cumulative', title='Cumulative Return'),
                            tooltip=['date', 'stock_cumulative']
                        ).properties(title=f"{ticker} Return")
                        
                        line2 = base.mark_line(color='gray', strokeDash=[5,5]).encode(
                            y='benchmark_cumulative',
                            tooltip=['date', 'benchmark_cumulative']
                        ).properties(title="S&P 500 (Benchmark)")
                        
                        st.altair_chart((line1 + line2).interactive(), use_container_width=True)
                        
                    else:
                        st.error(f"Backtest failed: {bt_data.get('message')}")
                else:
                    st.error("API Connection failed")
            except Exception as e:
                st.error(f"Error: {e}")

with tab5:
    st.subheader(f" {ticker} Technical Analysis Agent")
    
    st.markdown("""
    > This agent uses **Moving Averages (MA)**, **Support & Resistance**, and **Backtesting** > to generate a trading signal (Buy/Sell/Hold).
    """)
    
    if st.button("Run Technical Analysis", key="btn_tech"):
        with st.spinner("Analyzing price patterns and trends..."):
            try:
                res = session.post(f"{BACKEND_URL}/api/analyze_technical/{ticker}")
                if res.status_code == 200:
                    data = res.json()
                    if data.get("status") == "success":
                        report = data.get("report")
                        st.success("Analysis Complete!")
                        st.markdown("### 📝 Technical Trade Note")
                        st.markdown(report)
                    else:
                        st.error(f"Error: {data.get('message')}")
                else:
                    st.error("Connection failed")
            except Exception as e:
                st.error(f"Error: {e}")
