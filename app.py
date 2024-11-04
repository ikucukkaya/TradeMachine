import os
import re
import pandas as pd
import unicodedata
from datetime import datetime
import streamlit as st
from io import BytesIO

# ----------------------- Utility Functions -----------------------

def normalize_player_name(player_name):
    """
    Normalizes player names by converting to lowercase, removing special characters,
    and trimming whitespace.
    """
    # Convert to lowercase
    name = player_name.lower()
    
    # Unicode normalization
    name = unicodedata.normalize('NFKD', name)
    
    # Keep only letters and spaces
    name = re.sub(r'[^a-z\s]', '', name)
    
    # Replace multiple spaces with a single space and strip
    name = re.sub(r'\s+', ' ', name).strip()
    
    return name

def read_data(scores_path, injury_path):
    """
    Reads and merges the scores and injury data from Excel files.
    """
    try:
        df_scores = pd.read_excel(scores_path)
        df_injuries = pd.read_excel(injury_path)

        # Check column names and merge accordingly
        if 'Player_Name' in df_scores.columns:
            merged_df = pd.merge(df_scores, df_injuries, left_on='Player_Name', right_on='Player', how='left')
        else:
            merged_df = pd.merge(df_scores, df_injuries, left_on='Player', right_on='Player', how='left')

        # Fill missing injury info
        merged_df['Injury'] = merged_df['Injury'].fillna('Healthy')
        merged_df['Status'] = merged_df['Status'].fillna('Active')

        # Drop unnecessary columns
        if 'Player' in merged_df.columns:
            merged_df.drop(columns=['Player'], inplace=True)

        # We no longer enforce minimums here

        return merged_df
    except Exception as e:
        st.error(f"Failed to read data: {e}")
        return pd.DataFrame()

def get_last_updated(scores_path, injury_path):
    """
    Determines the latest modification time between the scores and injury files.
    """
    try:
        rotowire_file_path = injury_path
        merged_scores_file_path = scores_path

        if not os.path.exists(rotowire_file_path) or not os.path.exists(merged_scores_file_path):
            return "Files not found."

        rotowire_mtime = os.path.getmtime(rotowire_file_path)
        merged_scores_mtime = os.path.getmtime(merged_scores_file_path)

        latest_datetime = max(datetime.fromtimestamp(rotowire_mtime), datetime.fromtimestamp(merged_scores_mtime))
        formatted_datetime = latest_datetime.strftime("%Y-%m-%d %H:%M:%S")

        return formatted_datetime
    except Exception as e:
        return f"Error retrieving timestamp ({e})"

def calculate_week():
    """
    Calculates the current week based on a base date.
    """
    base_date = datetime(2024, 10, 21)
    current_date = datetime.now()
    delta = current_date - base_date
    week = max(0, (delta.days // 7) + 1)
    return week

def calculate_score(player_name, week, data):
    """
    Calculates the score for a player based on the current week.
    Enforces minimum values of 2 for 'Regular' and 'Projection'.
    """
    player_data = data[data['Player_Name'] == player_name].iloc[0]
    regular = max(2, player_data['Regular'])
    projection = max(2, player_data['Projection'])
    score = (((20 - week) * projection) / 20) + ((week * regular) / 20)
    score = max(2, score)  # Ensure the total score is at least 2
    return score

# ----------------------- Trade Evaluation Function -----------------------

def evaluate_trade(data, team1_players, team2_players):
    """
    Evaluates the trade between Team 1 and Team 2 based on selected players.
    """
    week = calculate_week()
    st.markdown(f"<h3 style='text-align: center;'>Current Week: {week}</h3>", unsafe_allow_html=True)

    # Team 1 Evaluation
    team1_scores = []
    team1_details = []

    for player in team1_players:
        score = calculate_score(player, week, data)
        player_data = data[data['Player_Name'] == player].iloc[0]
        regular = max(2, player_data['Regular'])
        projection = max(2, player_data['Projection'])
        team1_scores.append(score)

        formatted_detail = (
            f"**- {player}**<br>"
            f"(Regular: {regular}, Projection: {projection}, Score: {score:.2f})"
        )
        team1_details.append(formatted_detail)

    team1_total = sum(team1_scores)

    # Team 2 Evaluation
    team2_scores = []
    team2_details = []

    for player in team2_players:
        score = calculate_score(player, week, data)
        player_data = data[data['Player_Name'] == player].iloc[0]
        regular = max(2, player_data['Regular'])
        projection = max(2, player_data['Projection'])
        team2_scores.append(score)

        formatted_detail = (
            f"**- {player}**<br>"
            f"(Regular: {regular}, Projection: {projection}, Score: {score:.2f})"
        )
        team2_details.append(formatted_detail)

    team2_total = sum(team2_scores)

    # Handle empty slots for fair evaluation
    empty_slots_info = ""
    if len(team1_players) < len(team2_players):
        empty_slots = len(team2_players) - len(team1_players)
        team1_scores.extend([2.00] * empty_slots)
        team1_total += 2.00 * empty_slots
        team1_details.extend([f"<span style='color:gray;'>- Empty Slot (Score: 2.00)</span>"] * empty_slots)
        empty_slots_info = f"Team 1 receives {empty_slots} empty slot(s) with SCORE: 2.00 each."
        st.markdown(f"<div style='text-align: center;'><strong>{empty_slots_info}</strong></div>", unsafe_allow_html=True)
    elif len(team2_players) < len(team1_players):
        empty_slots = len(team1_players) - len(team2_players)
        team2_scores.extend([2.00] * empty_slots)
        team2_total += 2.00 * empty_slots
        team2_details.extend([f"<span style='color:gray;'>- Empty Slot (Score: 2.00)</span>"] * empty_slots)
        empty_slots_info = f"Team 2 receives {empty_slots} empty slot(s) with SCORE: 2.00 each."
        st.markdown(f"<div style='text-align: center;'><strong>{empty_slots_info}</strong></div>", unsafe_allow_html=True)

    # Display Trade Evaluation side by side
    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"<h3 style='text-align: center;'>Team 1 Total Score: {team1_total:.2f}</h3>", unsafe_allow_html=True)
        for detail in team1_details:
            st.markdown(f"<div style='text-align: center;'>{detail}</div>", unsafe_allow_html=True)

    with col2:
        st.markdown(f"<h3 style='text-align: center;'>Team 2 Total Score: {team2_total:.2f}</h3>", unsafe_allow_html=True)
        for detail in team2_details:
            st.markdown(f"<div style='text-align: center;'>{detail}</div>", unsafe_allow_html=True)

    # Validate trade (both teams must have at least one player)
    if team1_total == 0 or team2_total == 0:
        st.warning("Both teams must have at least one player.")
        return

    # Calculate Trade Ratio
    trade_ratio = min(team1_total / team2_total, team2_total / team1_total)

    # Center the Trade Ratio
    st.markdown(f"<h3 style='text-align: center;'>Trade Ratio: {trade_ratio:.2f}</h3>", unsafe_allow_html=True)

    # Determine Trade Approval
    if trade_ratio >= 0.80:
        approval_message = f"""
        <div style='text-align: center; color: white;'>
            <h3 style='color: green;'>Trade Approved!</h3>
        </div>
        """
    else:
        approval_message = f"""
        <div style='text-align: center; color: white;'>
            <h3 style='color: red;'>Trade Not Approved!</h3>
        </div>
        """

    st.markdown(approval_message, unsafe_allow_html=True)

# ----------------------- Injured Players Display Function -----------------------

def display_injured_players(data):
    """
    Displays a table of injured players with their injury details.
    """
    injured_df = data[data['Injury'].str.lower() != 'healthy']
    if injured_df.empty:
        st.info("No injured players currently.")
    else:
        injured_players_df = injured_df[['Player_Name', 'Injury', 'Status']].reset_index(drop=True)
        st.table(injured_players_df)

# ----------------------- Player Rankings Display Function -----------------------

def display_player_rankings(data):
    """
    Calculates and displays the player rankings based on Total Score.
    """
    # Calculate week number
    week = calculate_week()
    
    # Get current date for display purposes
    current_date = datetime.now().strftime("%d_%m_%Y")
    
    # Create display column name
    total_score_display_column = f"Total_Score (Week {week})"
    
    # Calculate Total_Score for each player without enforcing minimums
    data['Total_Score'] = data.apply(
        lambda row: (((20 - week) * row['Projection']) / 20) + ((week * row['Regular']) / 20),
        axis=1
    ).round(2)
    
    # Create display values for Total_Score
    data[total_score_display_column] = data['Total_Score'].apply(lambda x: f"{x:.2f}")
    
    # Sort data by Total_Score descending and reset index
    sorted_data = data.sort_values(by='Total_Score', ascending=False).reset_index(drop=True)
    
    # Set 'Rank' as the index starting from 1
    sorted_data.index = sorted_data.index + 1
    sorted_data.index.name = 'Rank'
    
    # Reorder columns
    sorted_data = sorted_data[['Player_Name', 'Regular', 'Projection', total_score_display_column]]
    
    # Center the table and download button together
    col_center = st.columns([1, 3, 1])
    with col_center[1]:
        # Display the DataFrame with 'Rank' as index
        st.dataframe(sorted_data)
        
        # Provide option to download the data
        output = BytesIO()
        # Save to Excel in memory, include the index to have 'Rank' in the Excel file
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            sorted_data.to_excel(writer, index=True)
        processed_data = output.getvalue()
        
        # Create a download button
        st.download_button(
            label="Download Player Rankings as Excel",
            data=processed_data,
            file_name=f"Player_Scores_{current_date}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# ----------------------- Streamlit Main Application -----------------------

def main():
    # Set Streamlit page configuration
    st.set_page_config(page_title="🏀 Trade Machine 🏀", layout="wide")

    # Center the title
    st.markdown("<h1 style='text-align: center;'>🏀 Trade Machine 🏀</h1>", unsafe_allow_html=True)

    # ------------------- Paths Configuration -------------------
    # Define relative paths
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(current_dir, "data")
    placeholder_image = os.path.join(current_dir, "placeholder.jpg")  # Placeholder not used but kept for reference

    # ------------------- Load Data -------------------
    merged_scores_path = os.path.join(data_dir, "merged_scores.xlsx")
    injury_report_path = os.path.join(data_dir, "nba-injury-report.xlsx")

    if os.path.exists(merged_scores_path) and os.path.exists(injury_report_path):
        merged_df = read_data(merged_scores_path, injury_report_path)
        if not merged_df.empty:
            st.session_state['data'] = merged_df
            st.session_state['last_updated'] = get_last_updated(merged_scores_path, injury_report_path)
            data = merged_df
            st.success("Data loaded successfully.")
        else:
            st.error("Loaded data is empty. Please ensure the data files are correct.")
            data = None
    else:
        st.error("Data files not found. Please place 'merged_scores.xlsx' and 'nba-injury-report.xlsx' in the 'data' directory.")
        data = None

    # ------------------- Sidebar: Data Information -------------------
    st.sidebar.header("📊 Data Information")

    # Display Last Updated
    if 'last_updated' in st.session_state:
        last_updated = st.session_state['last_updated']
        st.sidebar.markdown(f"**Last Updated:** {last_updated} Z")
    else:
        st.sidebar.markdown("**Last Updated:** Not Available")

    if data is None or data.empty:
        st.info("No data available. Please ensure the data files are in place.")
        return

    # ------------------- Player Selection -------------------
    # Center the heading
    st.markdown("<h3 style='text-align: center;'>Select Players for Trade</h3>", unsafe_allow_html=True)

    with st.form("trade_form"):
        # Create two columns for Team 1 and Team 2
        col1, col2 = st.columns(2)

        with col1:
            # Team 1 Heading
            st.markdown("<h3 style='text-align: center;'>Team 1: Select Players</h3>", unsafe_allow_html=True)
            # Team 1 Selection List
            team1_selected = st.multiselect(
                "Select Players for Team 1",
                options=data['Player_Name'].tolist(),
                key="team1_selected"
            )
            # Display Selected Players for Team 1
            if team1_selected:
                st.markdown("<div style='text-align: center;'><strong>Selected Players for Team 1:</strong></div>", unsafe_allow_html=True)
                for player in team1_selected:
                    st.markdown(f"<div style='text-align: center;'>- {player}</div>", unsafe_allow_html=True)

        with col2:
            # Team 2 Heading
            st.markdown("<h3 style='text-align: center;'>Team 2: Select Players</h3>", unsafe_allow_html=True)
            # Team 2 Selection List
            team2_selected = st.multiselect(
                "Select Players for Team 2",
                options=data['Player_Name'].tolist(),
                key="team2_selected"
            )
            # Display Selected Players for Team 2
            if team2_selected:
                st.markdown("<div style='text-align: center;'><strong>Selected Players for Team 2:</strong></div>", unsafe_allow_html=True)
                for player in team2_selected:
                    st.markdown(f"<div style='text-align: center;'>- {player}</div>", unsafe_allow_html=True)
        
        # Center the Evaluate Trade button using columns
        col_center = st.columns([1, 0.4, 1])
        with col_center[1]:
            submitted = st.form_submit_button("📈 Evaluate Trade")

    if submitted:
        # Check for duplicates
        duplicate_players = set(team1_selected) & set(team2_selected)
        if duplicate_players:
            st.error(f"Error: The following player(s) are selected for both teams: {', '.join(duplicate_players)}. Please select different players for each team.")
        else:
            if not team1_selected and not team2_selected:
                st.warning("Please select players for both teams to evaluate a trade.")
            else:
                evaluate_trade(data, team1_selected, team2_selected)

    # ------------------- Player Rankings Section -------------------
    st.markdown("---")

    # Center the heading
    st.markdown("<h3 style='text-align: center;'>🏀 Player Rankings</h3>", unsafe_allow_html=True)

    # Define the callback function for rankings
    def toggle_show_rankings():
        st.session_state['show_rankings'] = not st.session_state.get('show_rankings', False)

    # Determine the button label based on the current state
    button_label_rankings = "Hide Player Rankings" if st.session_state.get('show_rankings', False) else "Show Player Rankings"

    # Center the 'Show/Hide Player Rankings' button
    col_center = st.columns([1, 0.4, 1])
    with col_center[1]:
        st.button(button_label_rankings, on_click=toggle_show_rankings, key="rankings_button")

    # Display the player rankings based on the state
    if st.session_state.get('show_rankings', False):
        display_player_rankings(data)

    # ------------------- Injured Players Section -------------------
    st.markdown("---")

    # Center the heading
    st.markdown(
        "<h3 style='text-align: center;'>🏥 Injured Players Information</h3>",
        unsafe_allow_html=True
    )

    # Define the callback function for injured players
    def toggle_show_injured():
        st.session_state['show_injured'] = not st.session_state.get('show_injured', False)

    # Determine the button label based on the current state
    button_label_injured = "Hide Injured Players" if st.session_state.get('show_injured', False) else "Show Injured Players"

    # Center the 'Show/Hide Injured Players' button using columns
    col_center = st.columns([1, 0.4, 1])
    with col_center[1]:
        st.button(button_label_injured, on_click=toggle_show_injured, key="injured_button")

    # Display the injured players table based on the state
    if st.session_state.get('show_injured', False):
        display_injured_players(data)

if __name__ == "__main__":
    main()