import time
import logging
from pathlib import Path
import pandas as pd
import streamlit as st
from streamlit_option_menu import option_menu
import plotly.graph_objects as go
from sqlalchemy import text

# Import modules from our project
from config import DEFAULT_TICKERS, LOG_FILE
from load_to_db import get_db_engine
from pipeline import run_pipeline

# -------------------------------------------------------------
# Page Configuration
# -------------------------------------------------------------
st.set_page_config(
    page_title="Stock Market Analytics Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------------------------------------------------
# Premium Dark Theme Custom CSS
# -------------------------------------------------------------
def inject_custom_css():
    st.markdown(
        """
        <style>
        /* Base page styling override */
        .stApp {
            background-color: #0b0f19;
            color: #e2e8f0;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        }
        
        /* Headers styling */
        h1, h2, h3 {
            color: #ffffff;
            font-weight: 700 !important;
            letter-spacing: -0.025em;
        }
        
        .main-title {
            background: linear-gradient(135deg, #6366f1 0%, #a855f7 50%, #ec4899 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-size: 2.8rem !important;
            font-weight: 800 !important;
            margin-bottom: 0.2rem !important;
            padding-bottom: 0.2rem;
        }
        
        .sub-title {
            color: #94a3b8;
            font-size: 1.1rem !important;
            margin-bottom: 2rem !important;
        }

        /* Sidebar Styling */
        section[data-testid="stSidebar"] {
            background-color: #111827 !important;
            border-right: 1px solid #1f2937;
        }
        
        /* Cards Styling (Glassmorphism & Gradients) */
        .glass-card {
            background: rgba(17, 24, 39, 0.7);
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1rem;
            box-shadow: 0 4px 20px 0 rgba(0, 0, 0, 0.2);
            transition: transform 0.2s ease, border-color 0.2s ease;
        }
        
        .glass-card:hover {
            border-color: rgba(99, 102, 241, 0.4);
            transform: translateY(-2px);
        }
        
        /* Custom Metric Cards */
        .metric-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 1rem;
            margin-bottom: 1.5rem;
        }
        
        .metric-card {
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            border: 1px solid rgba(255, 255, 255, 0.03);
            border-left: 4px solid #6366f1;
            border-radius: 10px;
            padding: 1.25rem;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }
        
        .metric-card.positive {
            border-left: 4px solid #10b981;
        }
        
        .metric-card.negative {
            border-left: 4px solid #ef4444;
        }
        
        .metric-card-title {
            color: #94a3b8;
            font-size: 0.85rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.5rem;
        }
        
        .metric-card-value {
            color: #ffffff;
            font-size: 1.8rem;
            font-weight: 700;
            line-height: 1;
            margin-bottom: 0.4rem;
        }
        
        .metric-card-delta {
            font-size: 0.9rem;
            font-weight: 600;
            display: flex;
            align-items: center;
        }
        
        .delta-up {
            color: #10b981;
        }
        
        .delta-down {
            color: #ef4444;
        }
        
        /* Custom Tab styling */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
            background-color: #111827;
            padding: 6px 12px;
            border-radius: 8px;
            border: 1px solid #1f2937;
        }
        
        .stTabs [data-baseweb="tab"] {
            height: 40px;
            white-space: pre-wrap;
            background-color: transparent;
            border-radius: 6px;
            color: #94a3b8;
            font-weight: 600;
            transition: all 0.2s;
            padding: 0 16px;
        }
        
        .stTabs [data-baseweb="tab"]:hover {
            color: #ffffff;
            background-color: rgba(255, 255, 255, 0.03);
        }
        
        .stTabs [aria-selected="true"] {
            background-color: #6366f1 !important;
            color: #ffffff !important;
        }
        
        /* Buttons styling */
        .stButton>button {
            background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
            color: white;
            border: none;
            border-radius: 8px;
            padding: 0.6rem 1.5rem;
            font-weight: 600;
            box-shadow: 0 4px 6px -1px rgba(99, 102, 241, 0.2);
            transition: all 0.2s;
            width: 100%;
        }
        
        .stButton>button:hover {
            background: linear-gradient(135deg, #4f46e5 0%, #3730a3 100%);
            box-shadow: 0 10px 15px -3px rgba(99, 102, 241, 0.3);
            transform: translateY(-1px);
            color: white;
        }

        .stButton>button:active {
            transform: translateY(0px);
        }

        /* Success alerts override */
        div[data-testid="stNotification"] {
            background-color: #064e3b;
            color: #34d399;
            border: 1px solid #047857;
            border-radius: 8px;
        }
        
        /* Table Styling */
        div[data-testid="stTable"] table {
            background-color: #111827;
            color: #e2e8f0;
            border: 1px solid #1f2937;
            border-radius: 8px;
        }
        
        /* Expander styling */
        .st-ae {
            background-color: #111827 !important;
            border: 1px solid #1f2937 !important;
            border-radius: 8px !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

# -------------------------------------------------------------
# Database Utility Functions
# -------------------------------------------------------------
@st.cache_resource
def get_db_connection():
    """Returns a connection engine."""
    return get_db_engine()

def run_query(query: str, params: dict = None) -> pd.DataFrame:
    """Executes a SQL query and returns a pandas DataFrame."""
    engine = get_db_connection()
    try:
        with engine.connect() as conn:
            df = pd.read_sql(text(query), conn, params=params)
            return df
    except Exception as e:
        st.error(f"Database Query Error: {e}")
        return pd.DataFrame()

# -------------------------------------------------------------
# Data Retrieval Functions
# -------------------------------------------------------------
def get_database_status():
    """Retrieves high-level stats of the database."""
    price_count = run_query("SELECT COUNT(*) as count FROM stock_prices").iloc[0]['count']
    metrics_count = run_query("SELECT COUNT(*) as count FROM pipeline_metrics").iloc[0]['count']
    
    last_update = "N/A"
    if price_count > 0:
        last_update_df = run_query("SELECT MAX(timestamp) as last_ts FROM stock_prices")
        if not last_update_df.empty:
            last_update = last_update_df.iloc[0]['last_ts']
            if isinstance(last_update, pd.Timestamp) or hasattr(last_update, 'strftime'):
                last_update = last_update.strftime('%Y-%m-%d %H:%M:%S')
                
    return {
        "price_count": price_count,
        "metrics_count": metrics_count,
        "last_update": last_update
    }

def get_latest_price_metrics(ticker: str) -> pd.DataFrame:
    """Fetches the single latest record with metrics for a ticker."""
    query = """
        SELECT * 
        FROM stock_prices 
        WHERE ticker = :ticker 
        ORDER BY timestamp DESC 
        LIMIT 1
    """
    return run_query(query, {"ticker": ticker})

def get_stock_history(ticker: str, limit: int = 100) -> pd.DataFrame:
    """Fetches historical records for a ticker."""
    query = """
        SELECT * 
        FROM stock_prices 
        WHERE ticker = :ticker 
        ORDER BY timestamp DESC 
        LIMIT :limit
    """
    df = run_query(query, {"ticker": ticker, "limit": limit})
    if not df.empty:
        df = df.sort_values(by='timestamp')
    return df

def get_performance_leaderboard() -> pd.DataFrame:
    """Retrieves the latest record of all tickers to compare performance."""
    query = """
        WITH latest_ranks AS (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY timestamp DESC) as rn
            FROM stock_prices
        )
        SELECT ticker, timestamp, open_price, close_price, volume, ma_5d, ma_20d, daily_return
        FROM latest_ranks
        WHERE rn = 1
        ORDER BY daily_return DESC
    """
    return run_query(query)

# -------------------------------------------------------------
# Main Application Layout
# -------------------------------------------------------------
def main():
    inject_custom_css()
    
    # -------------------------------------------------------------
    # Sidebar
    # -------------------------------------------------------------
    with st.sidebar:
        st.markdown("<h2 style='text-align: center;'>⚡ Pipeline Control</h2>", unsafe_allow_html=True)
        st.markdown("<hr style='margin: 0.5rem 0 1.5rem 0; border-color: #1f2937;'>", unsafe_allow_html=True)
        
        # Database Status
        db_stats = get_database_status()
        
        st.markdown(
            f"""
            <div class="glass-card" style="padding: 1rem; margin-bottom: 1.5rem; background: #1e293b;">
                <div style="font-size: 0.8rem; color: #94a3b8; text-transform: uppercase; font-weight: 600;">DB Connection</div>
                <div style="font-size: 1.1rem; color: #10b981; font-weight: 700; display: flex; align-items: center; margin-bottom: 0.8rem;">
                    ● Active (Local MySQL)
                </div>
                <div style="font-size: 0.8rem; color: #94a3b8; text-transform: uppercase; font-weight: 600;">Total Records</div>
                <div style="font-size: 1.2rem; color: #ffffff; font-weight: 700; margin-bottom: 0.8rem;">
                    {db_stats['price_count']:,}
                </div>
                <div style="font-size: 0.8rem; color: #94a3b8; text-transform: uppercase; font-weight: 600;">Last Data Point</div>
                <div style="font-size: 0.95rem; color: #f1f5f9; font-weight: 600;">
                    {db_stats['last_update']}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        # Trigger buttons
        st.subheader("🛠️ Manual Actions")
        
        if st.button("🔄 Trigger Incremental Ingest"):
            with st.spinner("Executing pipeline in incremental mode..."):
                success = run_pipeline(seed=False)
                if success:
                    st.success("Incremental Ingest Succeeded!")
                    # Clear cache to load fresh data
                    st.cache_resource.clear()
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Pipeline Run Failed. Check Logs.")
                    
        if st.button("🌱 Re-Seed Historical Data (1y)"):
            with st.spinner("Seeding database... This might take a few seconds."):
                success = run_pipeline(seed=True)
                if success:
                    st.success("Database Seeding Completed!")
                    st.cache_resource.clear()
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Seeding Failed. Check Logs.")
                    
        st.markdown("<hr style='border-color: #1f2937; margin: 1.5rem 0;'>", unsafe_allow_html=True)
        st.caption("Developed as part of the Real-Time Stock Market Analytics Platform project (Phases 1-4).")

    # -------------------------------------------------------------
    # Main Header Section
    # -------------------------------------------------------------
    st.markdown("<h1 class='main-title'>Stock Analytics Operations Center</h1>", unsafe_allow_html=True)
    st.markdown("<div class='sub-title'>Real-time processing, metric tracking, and analytical visualizations</div>", unsafe_allow_html=True)

    # -------------------------------------------------------------
    # Option Menu Navigation
    # -------------------------------------------------------------
    selected_tab = option_menu(
        menu_title=None,
        options=["📈 Market Analytics", "🏆 Leaderboard", "⚙️ Pipeline Performance"],
        icons=["chart-line", "trophy", "cpu"],
        menu_icon="cast",
        default_index=0,
        orientation="horizontal",
        styles={
            "container": {"padding": "0!important", "background-color": "#111827", "border": "1px solid #1f2937", "border-radius": "8px"},
            "icon": {"color": "#94a3b8", "font-size": "15px"}, 
            "nav-link": {"font-size": "15px", "color": "#94a3b8", "text-align": "center", "margin":"0px", "font-weight": "600", "--hover-color": "rgba(255,255,255,0.03)"},
            "nav-link-selected": {"background-color": "#6366f1", "color": "white"},
        }
    )
    
    st.markdown("<br>", unsafe_allow_html=True)

    # -------------------------------------------------------------
    # TAB 1: MARKET ANALYTICS
    # -------------------------------------------------------------
    if selected_tab == "📈 Market Analytics":
        if db_stats['price_count'] == 0:
            st.info("The database is currently empty. Please run 'Re-Seed Historical Data' from the sidebar to populate records.")
            return
            
        col_ctrl, _ = st.columns([1, 3])
        with col_ctrl:
            selected_ticker = st.selectbox("Select Asset to Analyze:", DEFAULT_TICKERS)
            
        latest_data = get_latest_price_metrics(selected_ticker)
        
        if not latest_data.empty:
            row = latest_data.iloc[0]
            close_val = row['close_price']
            open_val = row['open_price']
            daily_ret = row['daily_return'] if pd.notna(row['daily_return']) else 0.0
            daily_change_pct = daily_ret * 100
            daily_change_val = close_val - open_val
            volume_val = row['volume']
            ma_5 = row['ma_5d'] if pd.notna(row['ma_5d']) else close_val
            ma_20 = row['ma_20d'] if pd.notna(row['ma_20d']) else close_val
            
            # Format and Display HTML Metric Cards
            delta_class = "positive" if daily_change_val >= 0 else "negative"
            delta_sign = "+" if daily_change_val >= 0 else ""
            delta_icon = "▲" if daily_change_val >= 0 else "▼"
            
            st.markdown(
                f"""
                <div class="metric-container">
                    <div class="metric-card">
                        <div class="metric-card-title">Ticker</div>
                        <div class="metric-card-value">{selected_ticker}</div>
                        <div style="font-size: 0.8rem; color: #94a3b8;">Primary Equity</div>
                    </div>
                    <div class="metric-card {delta_class}">
                        <div class="metric-card-title">Close Price</div>
                        <div class="metric-card-value">${close_val:,.2f}</div>
                        <div class="metric-card-delta {'delta-up' if daily_change_val >= 0 else 'delta-down'}">
                            {delta_icon} {delta_sign}${daily_change_val:.2f} ({delta_sign}{daily_change_pct:.2f}%)
                        </div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-card-title">5-Day SMA</div>
                        <div class="metric-card-value">${ma_5:,.2f}</div>
                        <div style="font-size: 0.8rem; color: #94a3b8;">Short-term Trend</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-card-title">20-Day SMA</div>
                        <div class="metric-card-value">${ma_20:,.2f}</div>
                        <div style="font-size: 0.8rem; color: #94a3b8;">Long-term Support</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-card-title">Trading Volume</div>
                        <div class="metric-card-value">{volume_val:,}</div>
                        <div style="font-size: 0.8rem; color: #94a3b8;">Shares Traded</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
            
            # Get historical values for charting
            history_df = get_stock_history(selected_ticker, limit=120)
            
            if not history_df.empty:
                # Plotly Close & Moving Averages Chart
                st.markdown("### 📊 Price Trend Analysis")
                fig_price = go.Figure()
                
                # Close price line
                fig_price.add_trace(go.Scatter(
                    x=history_df['timestamp'],
                    y=history_df['close_price'],
                    name='Close Price',
                    line=dict(color='#6366f1', width=2.5),
                    hovertemplate='Price: $%{y:.2f}'
                ))
                
                # 5-day SMA line
                fig_price.add_trace(go.Scatter(
                    x=history_df['timestamp'],
                    y=history_df['ma_5d'],
                    name='5-Day SMA',
                    line=dict(color='#10b981', width=1.5, dash='dash'),
                    hovertemplate='MA-5: $%{y:.2f}'
                ))
                
                # 20-day SMA line
                fig_price.add_trace(go.Scatter(
                    x=history_df['timestamp'],
                    y=history_df['ma_20d'],
                    name='20-Day SMA',
                    line=dict(color='#f59e0b', width=1.5, dash='dot'),
                    hovertemplate='MA-20: $%{y:.2f}'
                ))
                
                fig_price.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    font_color='#94a3b8',
                    hovermode='x unified',
                    margin=dict(l=0, r=0, t=10, b=10),
                    xaxis=dict(
                        showgrid=True, gridcolor='#1e293b',
                        rangeslider=dict(visible=False)
                    ),
                    yaxis=dict(showgrid=True, gridcolor='#1e293b', tickprefix='$'),
                    legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
                )
                st.plotly_chart(fig_price, use_container_width=True)
                
                # Volume bar chart
                st.markdown("### 📈 Trading Volume")
                fig_vol = go.Figure()
                
                # Volume bars (color green if price went up, red if price went down)
                colors = ['#10b981' if (c - o) >= 0 else '#ef4444' 
                          for c, o in zip(history_df['close_price'], history_df['open_price'])]
                          
                fig_vol.add_trace(go.Bar(
                    x=history_df['timestamp'],
                    y=history_df['volume'],
                    marker_color=colors,
                    name='Volume',
                    hovertemplate='Volume: %{y:,}'
                ))
                
                fig_vol.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    font_color='#94a3b8',
                    margin=dict(l=0, r=0, t=10, b=10),
                    xaxis=dict(showgrid=True, gridcolor='#1e293b'),
                    yaxis=dict(showgrid=True, gridcolor='#1e293b'),
                    showlegend=False
                )
                st.plotly_chart(fig_vol, use_container_width=True)
        else:
            st.warning(f"No records found for ticker {selected_ticker} in the database.")
            
    # -------------------------------------------------------------
    # TAB 2: LEADERBOARD / PERFORMANCE
    # -------------------------------------------------------------
    elif selected_tab == "🏆 Leaderboard":
        leaderboard_df = get_performance_leaderboard()
        
        if leaderboard_df.empty:
            st.info("The database is empty. Seed data first.")
            return
            
        st.markdown("### 🏆 Top Asset Performance")
        
        # Price change chart comparison
        fig_leader = go.Figure()
        
        leaderboard_df['daily_return_pct'] = leaderboard_df['daily_return'] * 100
        
        # Color positive columns green and negative columns red
        colors = ['#10b981' if val >= 0 else '#ef4444' for val in leaderboard_df['daily_return_pct']]
        
        fig_leader.add_trace(go.Bar(
            x=leaderboard_df['ticker'],
            y=leaderboard_df['daily_return_pct'],
            marker_color=colors,
            text=leaderboard_df['daily_return_pct'].round(2).astype(str) + '%',
            textposition='auto',
            hovertemplate='Ticker: %{x}<br>Daily Return: %{y:.2f}%'
        ))
        
        fig_leader.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font_color='#94a3b8',
            margin=dict(l=0, r=0, t=30, b=10),
            xaxis=dict(showgrid=False),
            yaxis=dict(showgrid=True, gridcolor='#1e293b', ticksuffix='%'),
            title="Daily Percentage Changes Across Selected Equities"
        )
        st.plotly_chart(fig_leader, use_container_width=True)
        
        # Tabular leaderboard layout
        st.markdown("### 📊 Market Summary Table")
        
        display_df = leaderboard_df.copy()
        display_df['daily_return'] = display_df['daily_return_pct'].round(2).astype(str) + '%'
        display_df['close_price'] = '$' + display_df['close_price'].round(2).astype(str)
        display_df['open_price'] = '$' + display_df['open_price'].round(2).astype(str)
        display_df['ma_5d'] = '$' + display_df['ma_5d'].round(2).astype(str)
        display_df['ma_20d'] = '$' + display_df['ma_20d'].round(2).astype(str)
        display_df['volume'] = display_df['volume'].apply(lambda x: f"{x:,}")
        
        display_df = display_df.drop(columns=['daily_return_pct'])
        display_df.columns = ['Ticker', 'Latest Timestamp', 'Open Price', 'Close Price', 'Volume', '5-Day SMA', '20-Day SMA', 'Daily Change']
        
        st.table(display_df.reset_index(drop=True))

    # -------------------------------------------------------------
    # TAB 3: PIPELINE PERFORMANCE & LOGS
    # -------------------------------------------------------------
    elif selected_tab == "⚙️ Pipeline Performance":
        st.markdown("### ⚙️ Ingestion & Operational Pipeline Statistics")
        
        metrics_df = run_query("SELECT * FROM pipeline_metrics ORDER BY timestamp ASC")
        
        if metrics_df.empty:
            st.info("No pipeline run records logged in pipeline_metrics yet.")
        else:
            col_graph1, col_graph2 = st.columns(2)
            
            with col_graph1:
                st.markdown("#### ⏱️ Pipeline Execution Time")
                fig_time = go.Figure()
                fig_time.add_trace(go.Scatter(
                    x=metrics_df['timestamp'],
                    y=metrics_df['execution_time_seconds'],
                    mode='lines+markers',
                    name='Exec Time',
                    line=dict(color='#8b5cf6', width=2),
                    marker=dict(size=6)
                ))
                fig_time.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    font_color='#94a3b8',
                    xaxis=dict(showgrid=True, gridcolor='#1e293b'),
                    yaxis=dict(showgrid=True, gridcolor='#1e293b', ticksuffix='s'),
                    margin=dict(l=0, r=0, t=10, b=10)
                )
                st.plotly_chart(fig_time, use_container_width=True)
                
            with col_graph2:
                st.markdown("#### 📥 Volume of Records Ingested")
                fig_vol_proc = go.Figure()
                fig_vol_proc.add_trace(go.Bar(
                    x=metrics_df['timestamp'],
                    y=metrics_df['records_processed'],
                    name='Records',
                    marker_color='#6366f1'
                ))
                fig_vol_proc.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    font_color='#94a3b8',
                    xaxis=dict(showgrid=True, gridcolor='#1e293b'),
                    yaxis=dict(showgrid=True, gridcolor='#1e293b'),
                    margin=dict(l=0, r=0, t=10, b=10)
                )
                st.plotly_chart(fig_vol_proc, use_container_width=True)
            
            # Summary Metrics Table
            st.markdown("#### 📝 Pipeline Run Logs (DB Table)")
            metrics_display = metrics_df.sort_values(by='timestamp', ascending=False).copy()
            metrics_display.columns = ['Run ID', 'Run Timestamp', 'Execution Duration (s)', 'Job Status', 'New Records Ingested', 'Error Details']
            st.dataframe(metrics_display.reset_index(drop=True), use_container_width=True)
            
        # File log display
        st.markdown("<br>#### 📂 System Log File Output (logs/pipeline.log)", unsafe_allow_html=True)
        log_path = Path(LOG_FILE)
        if log_path.exists():
            try:
                with open(log_path, 'r') as f:
                    log_lines = f.readlines()
                # Display last 40 lines
                tail_logs = "".join(log_lines[-40:])
                st.code(tail_logs, language="text")
            except Exception as e:
                st.error(f"Could not read log file: {e}")
        else:
            st.info("No log file found. Logs will appear after running the pipeline.")

if __name__ == "__main__":
    main()
