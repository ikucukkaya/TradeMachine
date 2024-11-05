import os
import re
import pandas as pd
import unicodedata
from datetime import datetime
import streamlit as st
from io import BytesIO

# ----------------------- Paths Configuration -----------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
data_dir = os.path.join(current_dir, "data")
image_dir = os.path.join(current_dir, "player_images")
placeholder_image_path = os.path.join(current_dir, "placeholder.jpg")

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

def get_player_image_path(player_name):
    """
    Returns the file path of the player's image if it exists,
    otherwise returns the path to the placeholder image.
    """
    # Construct the image file name
    image_file_name = f"{player_name}.jpg"
    # Construct the full image path
    image_path = os.path.join(image_dir, image_file_name)
    # Check if the image file exists
    if os.path.exists(image_path):
        return image_path
    else:
        # Return the placeholder image path
        return placeholder_image_path

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
    regular = player_data['Regular']
    projection = player_data['Projection']
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
        regular = player_data['Regular']
        projection = player_data['Projection']
        team1_scores.append(score)
        
        # Get player image path
        image_path = get_player_image_path(player)
        
        # Append player details
        team1_details.append({
            'player': player,
            'regular': regular,
            'projection': projection,
            'score': score,
            'image_path': image_path
        })

    team1_total = sum(team1_scores)

    # Team 2 Evaluation
    team2_scores = []
    team2_details = []

    for player in team2_players:
        score = calculate_score(player, week, data)
        player_data = data[data['Player_Name'] == player].iloc[0]
        regular = player_data['Regular']
        projection = player_data['Projection']
        team2_scores.append(score)
        
        # Get player image path
        image_path = get_player_image_path(player)
        
        # Append player details
        team2_details.append({
            'player': player,
            'regular': regular,
            'projection': projection,
            'score': score,
            'image_path': image_path
        })

    team2_total = sum(team2_scores)

    # Handle empty slots for fair evaluation
    empty_slots_info = ""
    if len(team1_players) < len(team2_players):
        empty_slots = len(team2_players) - len(team1_players)
        team1_scores.extend([2.00] * empty_slots)
        team1_total += 2.00 * empty_slots
        for _ in range(empty_slots):
            team1_details.append({
                'player': 'Empty Slot',
                'regular': '-',
                'projection': '-',
                'score': 2.00,
                'image_path': placeholder_image_path  # Use placeholder image
            })
        empty_slots_info = f"Team 1 receives {empty_slots} empty slot(s) with SCORE: 2.00 each."
        st.markdown(f"<div style='text-align: center;'><strong>{empty_slots_info}</strong></div>", unsafe_allow_html=True)
    elif len(team2_players) < len(team1_players):
        empty_slots = len(team1_players) - len(team2_players)
        team2_scores.extend([2.00] * empty_slots)
        team2_total += 2.00 * empty_slots
        for _ in range(empty_slots):
            team2_details.append({
                'player': 'Empty Slot',
                'regular': '-',
                'projection': '-',
                'score': 2.00,
                'image_path': placeholder_image_path  # Use placeholder image
            })
        empty_slots_info = f"Team 2 receives {empty_slots} empty slot(s) with SCORE: 2.00 each."
        st.markdown(f"<div style='text-align: center;'><strong>{empty_slots_info}</strong></div>", unsafe_allow_html=True)

    # Display Trade Evaluation side by side with adjusted widths
    col1, col2 = st.columns([3, 2])  # Adjusted ratios for better layout

    with col1:
        st.markdown(f"<h3 style='text-align: center;'>Team 1 Total Score: {team1_total:.2f}</h3>", unsafe_allow_html=True)
        for detail in team1_details:
            with st.container():
                # Adjust column ratios if needed
                img_col, text_col = st.columns([1, 4])  # Photo column narrower
                with img_col:
                    st.image(detail['image_path'], width=60)
                with text_col:
                    if detail['player'] == 'Empty Slot':
                        st.markdown(
                            f"<div style='color:gray; font-size:16px; margin-top:12px;'>- Empty Slot (Score: 2.00)</div>",
                            unsafe_allow_html=True
                        )
                    else:
                        st.markdown(
                            f"<div style='font-size:16px; margin-top:12px;'>"
                            f"<strong>{detail['player']}</strong><br>"
                            f"(Regular: {detail['regular']}, Projection: {detail['projection']}, Score: {detail['score']:.2f})"
                            f"</div>",
                            unsafe_allow_html=True
                        )
    with col2:
        st.markdown(f"<h3 style='text-align: center;'>Team 2 Total Score: {team2_total:.2f}</h3>", unsafe_allow_html=True)
        for detail in team2_details:
            with st.container():
                img_col, text_col = st.columns([1, 4])  # Photo column narrower
                with img_col:
                    st.image(detail['image_path'], width=60)
                with text_col:
                    if detail['player'] == 'Empty Slot':
                        st.markdown(
                            f"<div style='color:gray; font-size:16px; margin-top:12px;'>- Empty Slot (Score: 2.00)</div>",
                            unsafe_allow_html=True
                        )
                    else:
                        st.markdown(
                            f"<div style='font-size:16px; margin-top:12px;'>"
                            f"<strong>{detail['player']}</strong><br>"
                            f"(Regular: {detail['regular']}, Projection: {detail['projection']}, Score: {detail['score']:.2f})"
                            f"</div>",
                            unsafe_allow_html=True
                        )

    # Validate trade (both teams must have at least one player)
    if team1_total == 0 or team2_total == 0:
        st.warning("Both teams must have at least one player.")
        return

    # Calculate Trade Ratio
    trade_ratio = round(min(team1_total / team2_total, team2_total / team1_total), 2)


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
            <h3 style='color: red;'>Trade Not Approved! (Girsin)</h3>
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
    Calculates and displays the player rankings based on Regular, Projection, and Total_Score.
    Displays three separate tables side by side with two decimal places and emojis in titles.
    """
    # Calculate week number
    week = calculate_week()
    
    # ----------------------- New: Regular Season Rankings -----------------------
    regular_season_path = os.path.join(data_dir, "2024-25_NBA_Regular_Season_Updated_daily.xlsx")
    try:
        df_regular_season = pd.read_excel(regular_season_path)
        # Select required columns
        required_columns = ['PLAYER', 'FG%', 'FT%', '3PM', 'PTS', 'TREB', 'AST', 'STL', 'BLK', 'TO', 'TOTAL']
        missing_cols = set(required_columns) - set(df_regular_season.columns)
        if missing_cols:
            st.error(f"Regular Season Rankings is missing columns: {', '.join(missing_cols)}")
            df_regular_season = pd.DataFrame()
        else:
            df_regular_season = df_regular_season[required_columns].copy()
            # Rename 'PLAYER' to 'Player_Name' if necessary
            if 'PLAYER' in df_regular_season.columns:
                df_regular_season = df_regular_season.rename(columns={'PLAYER': 'Player_Name'})
            # Add Rank column starting from 1
            df_regular_season.reset_index(inplace=True)
            df_regular_season.rename(columns={'index': 'Rank'}, inplace=True)
            df_regular_season['Rank'] = df_regular_season.index + 1
            # Reorder columns to have Rank first
            columns_order = ['Rank', 'Player_Name', 'FG%', 'FT%', '3PM', 'PTS', 'TREB', 'AST', 'STL', 'BLK', 'TO', 'TOTAL']
            df_regular_season = df_regular_season[columns_order]
            # Format numerical columns: FG% and FT% to three decimals, others to two
            for col in df_regular_season.columns:
                if col in ['FG%', 'FT%']:
                    df_regular_season[col] = df_regular_season[col].map("{:.3f}".format)
                elif col not in ['Rank', 'Player_Name']:
                    df_regular_season[col] = df_regular_season[col].map("{:.2f}".format)
    except Exception as e:
        st.error(f"Failed to load Regular Season Rankings: {e}")
        df_regular_season = pd.DataFrame()

    # ----------------------- New: Rest of Season Projections -----------------------
    rest_of_season_path = os.path.join(data_dir, "2024-25_Rest_of_Season_Rankings_Projections_updated_daily.xlsx")
    try:
        df_rest_of_season = pd.read_excel(rest_of_season_path)
        # Select required columns (assuming similar structure; adjust if different)
        required_columns = ['PLAYER', 'FG%', 'FT%', '3PM', 'PTS', 'TREB', 'AST', 'STL', 'BLK', 'TO', 'TOTAL']
        missing_cols = set(required_columns) - set(df_rest_of_season.columns)
        if missing_cols:
            st.error(f"Rest of Season Projections is missing columns: {', '.join(missing_cols)}")
            df_rest_of_season = pd.DataFrame()
        else:
            df_rest_of_season = df_rest_of_season[required_columns].copy()
            # Rename 'PLAYER' to 'Player_Name' if necessary
            if 'PLAYER' in df_rest_of_season.columns:
                df_rest_of_season = df_rest_of_season.rename(columns={'PLAYER': 'Player_Name'})
            # Add Rank column starting from 1
            df_rest_of_season.reset_index(inplace=True)
            df_rest_of_season.rename(columns={'index': 'Rank'}, inplace=True)
            df_rest_of_season['Rank'] = df_rest_of_season.index + 1
            # Reorder columns to have Rank first
            columns_order = ['Rank', 'Player_Name', 'FG%', 'FT%', '3PM', 'PTS', 'TREB', 'AST', 'STL', 'BLK', 'TO', 'TOTAL']
            df_rest_of_season = df_rest_of_season[columns_order]
            # Format numerical columns: FG% and FT% to three decimals, others to two
            for col in df_rest_of_season.columns:
                if col in ['FG%', 'FT%']:
                    df_rest_of_season[col] = df_rest_of_season[col].map("{:.3f}".format)
                elif col not in ['Rank', 'Player_Name']:
                    df_rest_of_season[col] = df_rest_of_season[col].map("{:.2f}".format)
    except Exception as e:
        st.error(f"Failed to load Rest of Season Projections: {e}")
        df_rest_of_season = pd.DataFrame()

    # ----------------------- Existing: Total_Score Rankings -----------------------
    data['Total_Score'] = data.apply(
        lambda row: (((20 - week) * row['Projection']) / 20) + ((week * row['Regular']) / 20),
        axis=1
    ).round(2)
    
    # Create Total_Score DataFrame
    df_total = data[['Player_Name', 'Total_Score']].copy()
    df_total_sorted = df_total.sort_values(by='Total_Score', ascending=False).reset_index(drop=True)
    df_total_sorted.index += 1
    df_total_sorted.index.name = 'Rank'
    df_total_sorted = df_total_sorted.rename(columns={'Total_Score': 'Score'})
    df_total_final = df_total_sorted.reset_index()[['Rank', 'Player_Name', 'Score']]
    df_total_final['Score'] = df_total_final['Score'].map("{:.2f}".format)

    # ----------------------- Display Tables Side by Side -----------------------
    # Create three columns with adjusted widths
    col1, col2, col3 = st.columns([3, 3, 1])  # Adjusted ratios: first two tables wider

    with col1:
        if not df_regular_season.empty:
            st.markdown("**📊 Regular Season Rankings**")
            st.dataframe(df_regular_season, hide_index=True)
        else:
            st.info("Regular Season Rankings not available.")

    with col2:
        if not df_rest_of_season.empty:
            st.markdown("**🔮 Rest of Season Projections**")
            st.dataframe(df_rest_of_season, hide_index=True)
        else:
            st.info("Rest of Season Projections not available.")

    with col3:
        st.markdown(f"**🏆 Total Scores (Week {week})**")
        st.dataframe(df_total_final, hide_index=True)

    # ----------------------- Provide option to download the rankings -----------------------
    # Combine all rankings into a single Excel file with separate sheets
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Regular Season Rankings
        if not df_regular_season.empty:
            # Convert numerical columns back to float for Excel
            df_regular_season_download = df_regular_season.copy()
            numerical_cols = ['FG%', 'FT%', '3PM', 'PTS', 'TREB', 'AST', 'STL', 'BLK', 'TO', 'TOTAL']
            for col in numerical_cols:
                df_regular_season_download[col] = df_regular_season_download[col].astype(float)
            df_regular_season_download.to_excel(writer, sheet_name='Regular Season Rankings', index=False)
        
        # Rest of Season Projections
        if not df_rest_of_season.empty:
            df_rest_of_season_download = df_rest_of_season.copy()
            numerical_cols = ['FG%', 'FT%', '3PM', 'PTS', 'TREB', 'AST', 'STL', 'BLK', 'TO', 'TOTAL']
            for col in numerical_cols:
                df_rest_of_season_download[col] = df_rest_of_season_download[col].astype(float)
            df_rest_of_season_download.to_excel(writer, sheet_name='Rest of Season Projections', index=False)
        
        # Total Scores
        df_total_download = df_total_sorted.copy()
        df_total_download['Score'] = df_total_download['Score'].astype(float)
        df_total_download.reset_index(inplace=True)  # Convert 'Rank' from index to column
        df_total_download.to_excel(writer, sheet_name='Total Scores', index=False)
    processed_data = output.getvalue()
    
    # Get current date for the filename
    current_date = datetime.now().strftime("%d_%m_%Y")
    
    # Center the download button
    col_center = st.columns([1, 0.5, 1])
    with col_center[1]:
        st.download_button(
            label="📥 Download Player Rankings",
            data=processed_data,
            file_name=f"Player_Rankings_{current_date}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# ----------------------- Streamlit Main Application -----------------------

def main():
    # Set Streamlit page configuration
    st.set_page_config(page_title="🏀 Trade Machine 🏀", layout="wide", initial_sidebar_state="collapsed")

    # Center the title
    st.markdown("<h1 style='text-align: center;'>🏀 Trade Machine 🏀</h1>", unsafe_allow_html=True)

    # ------------------- Load Data -------------------
    merged_scores_path = os.path.join(data_dir, "merged_scores.xlsx")
    injury_report_path = os.path.join(data_dir, "nba-injury-report.xlsx")

    if os.path.exists(merged_scores_path) and os.path.exists(injury_report_path):
        merged_df = read_data(merged_scores_path, injury_report_path)
        if not merged_df.empty:
            st.session_state['data'] = merged_df
            st.session_state['last_updated'] = get_last_updated(merged_scores_path, injury_report_path)
            data = merged_df
            st.sidebar.success("Data loaded successfully.")
        else:
            st.sidebar.error("Loaded data is empty. Please ensure the data files are correct.")
            data = None
    else:
        st.sidebar.error("Data files not found. Please place 'merged_scores.xlsx' and 'nba-injury-report.xlsx' in the 'data' directory.")
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