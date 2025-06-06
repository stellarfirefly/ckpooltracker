import pandas as pd
import requests
import json
import time
import matplotlib.pyplot as plt
import numpy as np
import matplotlib.dates as mdates

DATA_PROTOCOL = "http"
DATA_HOST = "192.168.0.50"
DATA_PORT = "80"
DATA_SCRIPT = "~firefly/ckpool/userstats.py"
DATA_USER = "bc1q3fs68hnjtyshjzxtww9tp8me9jppc2jvlavk4w"
# Construct DATAURL from components
DATAURL = f"{DATA_PROTOCOL}://{DATA_HOST}:{DATA_PORT}/{DATA_SCRIPT}?user={DATA_USER}"

FETCH_INTERVAL_SECONDS = 60
DATA_WINDOW_MINUTES = 100 # Changed to show approximately 100 points if fetch interval is 1 min
DISPLAY_FRAMERATE = 20 # frames per second

def parse_hashrate_to_ths(hashrate_str):
    """
    Parses a hashrate string (e.g., "7.94T", "500G") and converts it to Terahashes/second (TH/s).
    Returns 0.0 if parsing fails or input is invalid.
    """
    if not isinstance(hashrate_str, str) or not hashrate_str:
        print(f"Warning: Invalid input to parse_hashrate_to_ths: {hashrate_str}")
        return 0.0

    multipliers_to_ths = {
        'H': 10**-12,  # Hash
        'K': 10**-9,   # KiloHash
        'M': 10**-6,   # MegaHash
        'G': 10**-3,   # GigaHash
        'T': 1,        # TeraHash
        'P': 10**3,    # PetaHash
        'E': 10**6,    # ExaHash
    }

    original_str = hashrate_str
    hashrate_str = hashrate_str.strip()
    
    unit_char = None
    value_part_str = hashrate_str

    if hashrate_str and hashrate_str[-1].isalpha():
        potential_unit = hashrate_str[-1].upper()
        if potential_unit in multipliers_to_ths:
            unit_char = potential_unit
            value_part_str = hashrate_str[:-1]
    
    try:
        numeric_val = float(value_part_str)
    except ValueError:
        print(f"Error: Could not parse numeric value from '{value_part_str}' (original: '{original_str}')")
        return 0.0

    if unit_char:
        return numeric_val * multipliers_to_ths[unit_char]
    else:
        # If no recognized unit, assume base H/s and convert to TH/s
        # This handles cases like "1000" (interpreted as 1000 H/s)
        print(f"Warning: No recognized unit suffix in '{original_str}'. Assuming H/s.")
        return numeric_val * multipliers_to_ths['H']

def main():
    # Initialize df with explicit dtypes to prevent FutureWarning on concat
    df = pd.DataFrame(columns=['timestamp', 'hashrate5m_THs', 'hashrate1h_THs']).astype({
        'timestamp': 'datetime64[ns]',
        'hashrate5m_THs': 'float64',
        'hashrate1h_THs': 'float64'
    })

    plt.ion() 
    fig, ax = plt.subplots(figsize=(12, 6))
    line_5m, = ax.plot([], [], marker='o', linestyle='-', label='Hashrate 5m Avg')
    line_1h, = ax.plot([], [], marker='x', linestyle='--', color='lightcoral', label='Hashrate 1h Avg')
    
    ax.set_xlabel("Time")
    ax.set_ylabel("Hashrate (TH/s)")
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
    plt.grid(True)
    ax.legend(loc='upper left') # Add legend
    fig.autofmt_xdate() # Auto-format x-axis dates for readability    
    # Adjust layout to provide more space at the top for the title
    plt.tight_layout(rect=[0, 0, 1, 0.92]) 

    print(f"Starting CKPool tracker. Data will be fetched every {FETCH_INTERVAL_SECONDS} seconds.")
    print(f"Graph will show data from the last {DATA_WINDOW_MINUTES} minutes.")

    next_data_fetch_time = time.monotonic() # Initialize to fetch data on the first iteration

    latest_workers_count = None # Variable to store the latest worker count
    while True:
        current_time = time.monotonic()
        new_data_processed_this_cycle = False # Reset for each potential fetch cycle

        # --- Data Fetching and Plot Logic (runs periodically) ---
        if current_time >= next_data_fetch_time:
            scheduled_fetch_start_time = next_data_fetch_time # Intended start for this fetch cycle
            actual_processing_start_time = time.monotonic()   # Actual start for measuring duration
            current_timestamp_for_loop = pd.Timestamp.now()   # Consistent timestamp for this fetch iteration

            try:
                response = None # Initialize for safer access in except blocks
                response = requests.get(DATAURL, timeout=10)
                response.raise_for_status()
                data = response.json()

                # Initialize with NaN, so if a value is not found, it remains NaN
                current_hashrate5m_val_ths = np.nan
                current_hashrate1h_val_ths = np.nan
                current_workers_count = None # Reset for this fetch cycle
                
                processed_5m_data = False
                processed_1h_data = False
                processed_workers = False
                log_parts = [f"{current_timestamp_for_loop}:"]

                hashrate5m_str = data.get("hashrate5m") # Fetch 5m hashrate
                if hashrate5m_str is None:
                    log_parts.append("hashrate5m (for 5m avg) not found.")
                else:
                    current_hashrate5m_val_ths = parse_hashrate_to_ths(hashrate5m_str)
                    log_parts.append(f"5m: {hashrate5m_str} -> {current_hashrate5m_val_ths:.4f} TH/s")
                    processed_5m_data = True

                hashrate1h_str = data.get("hashrate1hr") # Fetch 1h hashrate (corrected key)
                if hashrate1h_str is None:
                    log_parts.append("hashrate1hr (for 1h avg) not found.")
                else:
                    current_hashrate1h_val_ths = parse_hashrate_to_ths(hashrate1h_str)
                    log_parts.append(f"1h: {hashrate1h_str} -> {current_hashrate1h_val_ths:.4f} TH/s")
                    processed_1h_data = True

                workers_val = data.get("workers") # Get workers count
                if workers_val is None:
                    log_parts.append("workers not found.")
                else:
                    current_workers_count = workers_val # Assuming it's an int or string that doesn't need parsing
                    latest_workers_count = current_workers_count # Update the global latest
                    log_parts.append(f"Workers: {current_workers_count}")
                    processed_workers = True
                
                print(" ".join(log_parts))

                if processed_5m_data or processed_1h_data: # Add row if at least one hashrate value was processed
                    new_row_data = {
                        'timestamp': current_timestamp_for_loop,
                        'hashrate5m_THs': current_hashrate5m_val_ths,
                        'hashrate1h_THs': current_hashrate1h_val_ths
                    }
                    new_row = pd.DataFrame([new_row_data])
                    df = pd.concat([df, new_row], ignore_index=True)
                    new_data_processed_this_cycle = True

                # Prune data to the window size
                cutoff_time = current_timestamp_for_loop - pd.Timedelta(minutes=DATA_WINDOW_MINUTES)
                df = df[df['timestamp'] >= cutoff_time]

                # Update plot data and title
                if not df.empty:
                    line_5m.set_data(df['timestamp'], df['hashrate5m_THs'])
                    line_1h.set_data(df['timestamp'], df['hashrate1h_THs'])
                    ax.relim()
                    ax.autoscale_view(True,True,True)
                    
                    title_base = f"ckpool hashrate - last {DATA_WINDOW_MINUTES} min"
                    info_parts = []
                    source_label = ""

                    if new_data_processed_this_cycle:
                        source_label = "Current"
                        if not pd.isna(current_hashrate5m_val_ths):
                            info_parts.append(f"5m: {current_hashrate5m_val_ths:.2f}THs")
                        if not pd.isna(current_hashrate1h_val_ths):
                            info_parts.append(f"1h: {current_hashrate1h_val_ths:.2f}THs")
                        if current_workers_count is not None:
                            info_parts.append(f"workers: {current_workers_count}")

                    elif not df.empty: # df not empty, but no new data (e.g. pruning)
                        source_label = "Last in window"
                        if 'hashrate5m_THs' in df.columns and not df['hashrate5m_THs'].empty and not pd.isna(df['hashrate5m_THs'].iloc[-1]):
                            info_parts.append(f"5m: {df['hashrate5m_THs'].iloc[-1]:.2f}THs")
                        if 'hashrate1h_THs' in df.columns and not df['hashrate1h_THs'].empty and not pd.isna(df['hashrate1h_THs'].iloc[-1]):
                            info_parts.append(f"1h: {df['hashrate1h_THs'].iloc[-1]:.2f}THs")
                        if latest_workers_count is not None: # Use the globally stored latest if not a new fetch
                            info_parts.append(f"Workers: {latest_workers_count}")

                    if info_parts:
                        # Ensure "Workers" comes last if present
                        ax.set_title(f"{title_base}\n{source_label}: {', '.join(info_parts)}")
                    else:
                        ax.set_title(title_base + "\n(No data to display)")

                else: # df is empty
                    line_5m.set_data([], [])
                    line_1h.set_data([], [])
                    plot_window_start_time = current_timestamp_for_loop - pd.Timedelta(minutes=DATA_WINDOW_MINUTES)
                    ax.set_xlim(plot_window_start_time, current_timestamp_for_loop)
                    ax.set_ylim(0, 1)
                    ax.set_title(f"CKPool Hashrate - Last {DATA_WINDOW_MINUTES} Min\nWaiting for data...")
                
                fig.canvas.draw_idle() # Schedule redraw after plot updates

            except requests.exceptions.Timeout:
                print(f"{current_timestamp_for_loop}: Error: Request timed out while fetching data from {DATAURL}")
                # Optionally, update title to show error and redraw
                # ax.set_title(f"CKPool Hashrate - Error: Timeout\nLast {DATA_WINDOW_MINUTES} Min")
                # fig.canvas.draw_idle()
            except requests.exceptions.RequestException as e:
                print(f"{current_timestamp_for_loop}: Error fetching data: {e}")
            except json.JSONDecodeError as e:
                response_text = 'N/A'
                if response and hasattr(response, 'text'):
                    response_text = response.text[:200]
                print(f"{current_timestamp_for_loop}: Error decoding JSON: {e}. Response text: {response_text}")
            except Exception as e:
                print(f"{current_timestamp_for_loop}: An unexpected error occurred: {e}")

            # Calculate how long the actual data processing took
            processing_duration = time.monotonic() - actual_processing_start_time

            # Warning if processing took too long
            if new_data_processed_this_cycle and processing_duration > FETCH_INTERVAL_SECONDS:
                print(f"Warning: Data processing & plot update took {processing_duration:.2f}s, potentially delaying next fetch.")
                next_data_fetch_time = time.monotonic() # Schedule next fetch ASAP
            else:
                # Schedule the next fetch based on the *scheduled* start time of this fetch cycle
                next_data_fetch_time = scheduled_fetch_start_time + FETCH_INTERVAL_SECONDS

        # --- GUI Event Processing and Short Pause (runs every loop iteration) ---
        # This ensures the window remains responsive and processes clicks, resizes, and scheduled draws.
        if fig.canvas.manager is not None: # Ensure canvas manager exists
             fig.canvas.flush_events()

        # Short sleep to yield CPU and control GUI update rate.
        # Adjust this value to balance responsiveness and CPU usage.
        # 0.02s = 50Hz, 0.05s = 20Hz.
        time.sleep(1 / DISPLAY_FRAMERATE)

if __name__ == "__main__":
    # DATAURL is defined globally from the existing context
    # numpy and pandas are also imported from the existing context
    main()
