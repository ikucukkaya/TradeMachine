import os
import re
import pandas as pd
import unicodedata
from datetime import datetime
import streamlit as st  # type: ignore
from io import BytesIO
import urllib.parse
import streamlit.components.v1 as components  # type: ignore
import glob
from rapidfuzz import process, fuzz  # type: ignore
import matplotlib.pyplot as plt
import base64
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode  # type: ignore
from st_aggrid.shared import GridUpdateMode  # type: ignore


# ----------------------- Paths Configuration -----------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
data_dir = os.path.join(current_dir, "data")
image_dir = os.path.join(current_dir, "player_images")
placeholder_image_path = os.path.join(current_dir, "placeholder.jpg")
yahoo_dir = os.path.join(current_dir, "yahoo")  # Yahoo folder
player_scores_dir = os.path.join(current_dir, "TotalScore")  # New path
gifs_dir = os.path.join(current_dir, "gifs")

# GIF dosyalarını bulmak için `gifs` klasörünü kontrol edin
gif_files = sorted(
    [os.path.join(gifs_dir, file) for file in os.listdir(gifs_dir) if file.endswith('.gif')],
    key=lambda x: int(os.path.basename(x).split('.')[0])  # Sadece dosya adındaki numarayı sıralamak için
)

# GIF dosyalarını base64 formatına dönüştüren fonksiyon
def get_base64_gif(gif_path):
    with open(gif_path, "rb") as file:
        contents = file.read()
        data_url = base64.b64encode(contents).decode("utf-8")
    return data_url


# ----------------------- Utility Functions -----------------------

def normalize_player_name(player_name):
    """
    Normalizes player names: converts to lowercase, removes special characters, and trims whitespaces.
    """
    name = player_name.lower()
    name = unicodedata.normalize('NFKD', name)
    name = re.sub(r'[^a-z\s]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def get_player_image_path(player_name):
    """
    Returns the file path of the player's image if it exists, otherwise returns the path to the placeholder image.
    """
    image_file_name = f"{player_name}.jpg"
    image_path = os.path.join(image_dir, image_file_name)
    if os.path.exists(image_path):
        return image_path
    else:
        return placeholder_image_path

@st.cache_data
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
        formatted_datetime = latest_datetime.strftime("%d-%m-%Y %H:%M:%S")

        return formatted_datetime
    except Exception as e:
        return f"Error retrieving timestamp ({e})"

def calculate_week():
    """
    Calculates the current week based on a base date.
    """
    base_date = datetime(2024, 10, 21)  # Assuming the season starts on October 21, 2024
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

# ----------------------- WhatsApp Share Button Function -----------------------

def display_whatsapp_share_button(share_message):
    # URL encode the share message
    encoded_message = urllib.parse.quote(share_message)

    # Create WhatsApp share link
    whatsapp_url = f"https://api.whatsapp.com/send?text={encoded_message}"

    # HTML for WhatsApp share button
    button_html = f"""
        <style>
            .whatsapp-button-container {{
                text-align: center;
                margin-top: 40px;
            }}
            .whatsapp-button {{
                margin-right: 32px;
                padding: 12px 20px;
                color: white;
                background-color: #25D366;
                border: 2px solid #1DA1F2;
                border-radius: 30px;
                font-size: 18px;
                font-weight: bold;
                font-family: Arial, sans-serif;
                transition: transform 0.3s ease, background-color 0.3s ease, box-shadow 0.3s ease;
                cursor: pointer;
                text-decoration: none;
            }}
            .whatsapp-button:hover {{
                background-color: #1DA1F2;
                transform: scale(1.05);
                box-shadow: 0px 4px 15px rgba(0, 0, 0, 0.3);
            }}
        </style>
        <div class="whatsapp-button-container">
            <a href="{whatsapp_url}" target="_blank" class="whatsapp-button">
                NBA Fantasy'de Paylaş
            </a>
        </div>
    """
    
    # Embed the HTML in Streamlit
    components.html(button_html, height=80)

# ----------------------- Fuzzy Matching Function -----------------------

def map_yahoo_to_db_players(yahoo_roster_df, db_player_names, threshold=80):
    """
    Maps Yahoo roster player names to database player names using fuzzy matching.

    Parameters:
    - yahoo_roster_df: DataFrame containing Yahoo roster with 'Player_Name_Normalized'.
    - db_player_names: List of normalized database player names.
    - threshold: Minimum similarity score to consider a match.

    Returns:
    - A dictionary mapping Yahoo player names to DB player names.
    - A list of Yahoo player names that could not be matched.
    """
    mapping = {}
    unmatched = []

    for yahoo_player in yahoo_roster_df['Player_Name_Normalized']:
        match, score, _ = process.extractOne(
            yahoo_player,
            db_player_names,
            scorer=fuzz.WRatio
        )
        if score >= threshold:
            mapping[yahoo_player] = match
        else:
            unmatched.append(yahoo_player)

    return mapping, unmatched

# ----------------------- Team Averages Calculation Function -----------------------

def parse_attempts(attempt_str):
    """
    Parses a string like '5.2/18.3' and returns made and attempted shots as floats.
    """
    try:
        made_str, attempts_str = attempt_str.split('/')
        made = float(made_str)
        attempts = float(attempts_str)
        return made, attempts
    except:
        return 0.0, 0.0

def calculate_team_averages(df, player_list_normalized, num_top_players):
    """
    Calculates the team averages for specified statistical categories,
    considering only the top N players based on 'R#' ranking.
    """
    # Filter the dataframe to include only the players in player_list_normalized
    team_df = df[df['Player_Name_Normalized'].isin(player_list_normalized)].copy()
    
    # Ensure 'R#' is numeric
    team_df['R#'] = pd.to_numeric(team_df['R#'], errors='coerce')
    
    # Sort the team_df by 'R#' ranking
    team_df = team_df.sort_values(by='R#').head(num_top_players)
    
    # Initialize variables to sum up FG made, FG attempts, FT made, FT attempts
    total_fg_made = 0.0
    total_fg_attempts = 0.0
    total_ft_made = 0.0
    total_ft_attempts = 0.0

    # For each player, parse FGA and FTA columns to get made and attempted shots
    for idx, row in team_df.iterrows():
        # FGA and FTA are strings like '5.2/18.3'
        fga_str = row['FGA']
        fta_str = row['FTA']

        # Parse the made and attempted shots
        fg_made, fg_attempts = parse_attempts(fga_str)
        ft_made, ft_attempts = parse_attempts(fta_str)

        total_fg_made += fg_made
        total_fg_attempts += fg_attempts
        total_ft_made += ft_made
        total_ft_attempts += ft_attempts

    # Calculate team FG% and FT%
    team_fg_pct = (total_fg_made / total_fg_attempts) if total_fg_attempts > 0 else 0
    team_ft_pct = (total_ft_made / total_ft_attempts) if total_ft_attempts > 0 else 0

    # For other categories, sum the values and divide by the number of players
    categories = ['3PM', 'PTS', 'TREB', 'AST', 'STL', 'BLK', 'TO']
    team_averages = {}

    num_players = len(team_df)
    for cat in categories:
        total = team_df[cat].sum()
        average = total / num_players if num_players > 0 else 0
        team_averages[cat] = average

    # Add FG% and FT% to team_averages
    team_averages['FG%'] = team_fg_pct
    team_averages['FT%'] = team_ft_pct

    return team_averages

# ----------------------- Trade Evaluation Function -----------------------

def evaluate_trade(data, team1_players, team2_players, team1_injury_adjustments, team2_injury_adjustments, team1_name, team2_name, df_regular_season, df_rest_of_season, df_last14, df_last30, num_top_players):
    week = calculate_week()
    st.markdown(f"<h3 style='text-align: center;'>Current Week: {week}</h3>", unsafe_allow_html=True)

    # ------------------ Evaluate Team 1 ------------------
    team1_scores = []
    team1_details = []

    for idx, player in enumerate(team1_players):
        score = calculate_score(player, week, data)
        injury_adjustment = team1_injury_adjustments[idx]
        score += injury_adjustment
        score = max(2.00, score)  # Ensure at least 2.00
        player_data = data[data['Player_Name'] == player].iloc[0]
        regular = player_data['Regular']
        projection = player_data['Projection']
        last14 = player_data.get('Last14', 'N/A')
        last30 = player_data.get('Last30', 'N/A')
        team1_scores.append(score)

        image_path = get_player_image_path(player)

        team1_details.append({
            'player': player,
            'regular': regular,
            'projection': projection,
            'last14': last14,
            'last30': last30,
            'score': score,
            'image_path': image_path,
            'injury_adjustment': injury_adjustment
        })

    team1_total = sum(team1_scores)

    # ------------------ Evaluate Team 2 ------------------
    team2_scores = []
    team2_details = []

    for idx, player in enumerate(team2_players):
        score = calculate_score(player, week, data)
        injury_adjustment = team2_injury_adjustments[idx]
        score += injury_adjustment
        score = max(2.00, score)
        player_data = data[data['Player_Name'] == player].iloc[0]
        regular = player_data['Regular']
        projection = player_data['Projection']
        last14 = player_data.get('Last14', 'N/A')
        last30 = player_data.get('Last30', 'N/A')
        team2_scores.append(score)

        image_path = get_player_image_path(player)

        team2_details.append({
            'player': player,
            'regular': regular,
            'projection': projection,
            'last14': last14,
            'last30': last30,
            'score': score,
            'image_path': image_path,
            'injury_adjustment': injury_adjustment
        })

    team2_total = sum(team2_scores)

    # ------------------ Handle Empty Slots ------------------
    if len(team1_players) < len(team2_players):
        empty_slots = len(team2_players) - len(team1_players)
        team1_scores.extend([2.00] * empty_slots)
        team1_total += 2.00 * empty_slots
        for _ in range(empty_slots):
            team1_details.append({
                'player': 'Empty Slot',
                'regular': '-',
                'projection': '-',
                'last14': '-',
                'last30': '-',
                'score': 2.00,
                'image_path': placeholder_image_path,
                'injury_adjustment': 0
            })
        empty_slots_info = f"{team1_name} receives {empty_slots} empty slot(s) with SCORE: 2.00 each."
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
                'last14': '-',
                'last30': '-',
                'score': 2.00,
                'image_path': placeholder_image_path,
                'injury_adjustment': 0
            })
        empty_slots_info = f"{team2_name} receives {empty_slots} empty slot(s) with SCORE: 2.00 each."
        st.markdown(f"<div style='text-align: center;'><strong>{empty_slots_info}</strong></div>", unsafe_allow_html=True)


    # Validate trade
    if team1_total == 0 or team2_total == 0:
        st.warning("Both teams must have at least one player.")
        return

    # ------------------ Calculate Trade Ratio ------------------
    trade_ratio = round(min(team1_total / team2_total, team2_total / team1_total), 2)

    # ------------------ Helper Functions ------------------
    def safe_sum_regular(details):
        total = 0.0
        for d in details:
            if d['player'] == 'Empty Slot':
                total += 2.0
            elif d['regular'] != '-' and d['regular'] is not None:
                try:
                    val = float(d['regular']) + d['injury_adjustment']
                    val = max(val, 2.0)
                    total += val
                except:
                    pass
        return total

    def safe_sum_last14(details):
        total = 0.0
        for d in details:
            if d['player'] == 'Empty Slot':
                total += 2.0
            else:
                val = d['last14']
                if val != 'N/A':
                    try:
                        val_float = float(val) + d['injury_adjustment']
                        val_float = max(val_float, 2.0)
                        total += val_float
                    except:
                        pass
        return total

    def safe_sum_last30(details):
        total = 0.0
        for d in details:
            if d['player'] == 'Empty Slot':
                total += 2.0
            else:
                val = d['last30']
                if val != 'N/A':
                    try:
                        val_float = float(val) + d['injury_adjustment']
                        val_float = max(val_float, 2.0)
                        total += val_float
                    except:
                        pass
        return total

    # ------------------ Compute Totals for Regular, Last14, Last30 ------------------
    team1_regular_total = safe_sum_regular(team1_details)
    team2_regular_total = safe_sum_regular(team2_details)

    team1_last14_total = safe_sum_last14(team1_details)
    team2_last14_total = safe_sum_last14(team2_details)

    team1_last30_total = safe_sum_last30(team1_details)
    team2_last30_total = safe_sum_last30(team2_details)

    # ------------------ Compute Ratios for Regular, Last14, Last30 ------------------
    def compute_ratio(a, b):
        if a > 0 and b > 0:
            return round(min(a / b, b / a), 2)
        return 0.00

    regular_trade_ratio = compute_ratio(team1_regular_total, team2_regular_total)
    last14_trade_ratio = compute_ratio(team1_last14_total, team2_last14_total)
    last30_trade_ratio = compute_ratio(team1_last30_total, team2_last30_total)

    # Dominant team belirleme
    def dominant_team(a, b):
        if a > b:
            return f" ({team1_name} is giving more)"
        elif b > a:
            return f" ({team2_name} is giving more)"
        else:
            return " (Equal)"  # Eşit olduğunda boş string yerine "Equal" döndür

    regular_dominant = dominant_team(team1_regular_total, team2_regular_total)
    last14_dominant = dominant_team(team1_last14_total, team2_last14_total)
    last30_dominant = dominant_team(team1_last30_total, team2_last30_total)

    # ------------------ Display Scores and Details ------------------
    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown(f"<h3 style='text-align: center;'>{team1_name} Total Score: {team1_total:.2f}</h3>", unsafe_allow_html=True)
        st.markdown(f"<h6 style='text-align: center;'>{team1_name} Regular Total: {team1_regular_total:.2f}</h6>", unsafe_allow_html=True)
        st.markdown(f"<h6 style='text-align: center;'>{team1_name} Last14 Total: {team1_last14_total:.2f}</h6>", unsafe_allow_html=True)
        st.markdown(f"<h6 style='text-align: center;'>{team1_name} Last30 Total: {team1_last30_total:.2f}</h6>", unsafe_allow_html=True)
        
        for detail in team1_details:
            with st.container():
                img_col, text_col = st.columns([1, 4])
                with img_col:
                    st.image(detail['image_path'], width=60)
                with text_col:
                    if detail['player'] == 'Empty Slot':
                        st.markdown(
                            f"<div style='color:gray; font-size:16px; margin-top:12px;'>- Empty Slot (Score: 2.00)</div>",
                            unsafe_allow_html=True
                        )
                    else:
                        injury_note = ""
                        if detail['injury_adjustment'] == -1:
                            injury_note = " (IL - Up to 4 Weeks)"
                        elif detail['injury_adjustment'] == -2:
                            injury_note = " (IL - Indefinitely)"
                        st.markdown(
                            f"<div style='font-size:16px; margin-top:12px;'>"
                            f"<strong>{detail['player']}</strong>{injury_note}<br>"
                            f"(Last14: {detail['last14']}, Last30: {detail['last30']}, Regular: {detail['regular']}, Projection: {detail['projection']}, Score: {detail['score']:.2f})"
                            f"</div>",
                            unsafe_allow_html=True
                        )

    with col2:
        st.markdown(f"<h3 style='text-align: center;'>{team2_name} Total Score: {team2_total:.2f}</h3>", unsafe_allow_html=True)
        st.markdown(f"<h6 style='text-align: center;'>{team2_name} Regular Total: {team2_regular_total:.2f}</h6>", unsafe_allow_html=True)
        st.markdown(f"<h6 style='text-align: center;'>{team2_name} Last14 Total: {team2_last14_total:.2f}</h6>", unsafe_allow_html=True)
        st.markdown(f"<h6 style='text-align: center;'>{team2_name} Last30 Total: {team2_last30_total:.2f}</h6>", unsafe_allow_html=True)
        
        for detail in team2_details:
            with st.container():
                img_col, text_col = st.columns([1, 4])
                with img_col:
                    st.image(detail['image_path'], width=60)
                with text_col:
                    if detail['player'] == 'Empty Slot':
                        st.markdown(
                            f"<div style='color:gray; font-size:16px; margin-top:12px;'>- Empty Slot (Score: 2.00)</div>",
                            unsafe_allow_html=True
                        )
                    else:
                        injury_note = ""
                        if detail['injury_adjustment'] == -1:
                            injury_note = " (IL - Up to 4 Weeks)"
                        elif detail['injury_adjustment'] == -2:
                            injury_note = " (IL - Indefinitely)"
                        st.markdown(
                            f"<div style='font-size:16px; margin-top:12px;'>"
                            f"<strong>{detail['player']}</strong>{injury_note}<br>"
                            f"(Last14: {detail['last14']}, Last30: {detail['last30']}, Regular: {detail['regular']}, Projection: {detail['projection']}, Score: {detail['score']:.2f})"
                            f"</div>",
                            unsafe_allow_html=True
                        )

    # ------------------ Display Ratios ------------------
    # Üç küçük oranı h6 ile yazdırıyoruz:
    st.markdown(f"<h6 style='text-align: center;'>Regular Trade Ratio = {regular_trade_ratio:.2f}{regular_dominant}</h6>", unsafe_allow_html=True)
    st.markdown(f"<h6 style='text-align: center;'>Last14 Trade Ratio = {last14_trade_ratio:.2f}{last14_dominant}</h6>", unsafe_allow_html=True)
    st.markdown(f"<h6 style='text-align: center;'>Last30 Trade Ratio = {last30_trade_ratio:.2f}{last30_dominant}</h6>", unsafe_allow_html=True)

    # Ana Trade Ratio daha büyük yazı boyutunda (h2):
    st.markdown(f"<h2 style='text-align: center;'>Trade Ratio: {trade_ratio:.2f}</h2>", unsafe_allow_html=True)

    if trade_ratio >= 0.80:
        approval_message = "<h2 style='color: green; text-align: center;'>TRADE APPROVED</h2>"
        trade_status_text = "TRADE APPROVED"
    else:
        approval_message = "<h2 style='color: red; text-align: center;'>TRADE NOT APPROVED</h2>"
        trade_status_text = "TRADE NOT APPROVED"
    
    st.markdown(approval_message, unsafe_allow_html=True)

    # ------------------ WhatsApp Share (no new totals included) ------------------
    team1_details_text = "\n\n".join(
        [
            f"*{detail['player']}:*\n"
            f"Last14: {detail['last14']}  Last30: {detail['last30']}\n"
            f"*Regular: {detail['regular']}  Projection: {detail['projection']}*\n"
            f"*Total: {detail['score']:.2f}*\n"
            f"Adjustment: {detail['injury_adjustment']}"
            for detail in team1_details
        ]
    )

    team2_details_text = "\n\n".join(
        [
            f"*{detail['player']}:*\n"
            f"Last14: {detail['last14']}  Last30: {detail['last30']}\n"
            f"*Regular: {detail['regular']}  Projection: {detail['projection']}*\n"
            f"*Total: {detail['score']:.2f}*\n"
            f"Adjustment: {detail['injury_adjustment']}"
            for detail in team2_details
        ]
    )

    share_message = (
        f"Trade Evaluation:\n\n"
        f"*{team1_name}* Total Score: *{team1_total:.2f}*\n"
        f"*{team2_name}* Total Score: *{team2_total:.2f}*\n"
        f"*Trade Ratio: {trade_ratio:.2f}*\n"
        f"*{trade_status_text}*\n\n"
        f"--- {team1_name} Player Details ---\n{team1_details_text}\n\n"
        f"--- {team2_name} Player Details ---\n{team2_details_text}\n"
    )

    display_whatsapp_share_button(share_message)

    # Takım ortalamaları vb. diğer kısımlar için ek kod değişikliğine gerek yok.
    # ------------------- Team Averages Calculation -------------------

    # Create a mapping from Player_Name to Player_Name_Normalized
    player_name_to_normalized = data.set_index('Player_Name')['Player_Name_Normalized'].to_dict()

    # Get current team rosters with normalized player names
    team1_players_current = data[data['Takım'] == team1_name]['Player_Name'].tolist()
    team1_players_current_normalized = [player_name_to_normalized[player] for player in team1_players_current if player in player_name_to_normalized]

    team2_players_current = data[data['Takım'] == team2_name]['Player_Name'].tolist()
    team2_players_current_normalized = [player_name_to_normalized[player] for player in team2_players_current if player in player_name_to_normalized]

    # Normalize selected player names
    team1_selected_normalized = [player_name_to_normalized[player] for player in team1_players if player in player_name_to_normalized]
    team2_selected_normalized = [player_name_to_normalized[player] for player in team2_players if player in player_name_to_normalized]

    # After Trade Rosters
    team1_players_after_normalized = [player for player in team1_players_current_normalized if player not in team1_selected_normalized] + team2_selected_normalized
    team2_players_after_normalized = [player for player in team2_players_current_normalized if player not in team2_selected_normalized] + team1_selected_normalized

    # Calculate Team Averages Before and After Trade for Regular Season
    team1_avg_before_regular = calculate_team_averages(df_regular_season, team1_players_current_normalized, num_top_players)
    team1_avg_after_regular = calculate_team_averages(df_regular_season, team1_players_after_normalized, num_top_players)

    team2_avg_before_regular = calculate_team_averages(df_regular_season, team2_players_current_normalized, num_top_players)
    team2_avg_after_regular = calculate_team_averages(df_regular_season, team2_players_after_normalized, num_top_players)

    # Calculate Team Averages Before and After Trade for Projections
    team1_avg_before_projection = calculate_team_averages(df_rest_of_season, team1_players_current_normalized, num_top_players)
    team1_avg_after_projection = calculate_team_averages(df_rest_of_season, team1_players_after_normalized, num_top_players)

    team2_avg_before_projection = calculate_team_averages(df_rest_of_season, team2_players_current_normalized, num_top_players)
    team2_avg_after_projection = calculate_team_averages(df_rest_of_season, team2_players_after_normalized, num_top_players)

    # Calculate Team Averages Before and After Trade for Last14
    team1_avg_before_last14 = calculate_team_averages(df_last14, team1_players_current_normalized, num_top_players)
    team1_avg_after_last14 = calculate_team_averages(df_last14, team1_players_after_normalized, num_top_players)

    team2_avg_before_last14 = calculate_team_averages(df_last14, team2_players_current_normalized, num_top_players)
    team2_avg_after_last14 = calculate_team_averages(df_last14, team2_players_after_normalized, num_top_players)

    # Calculate Team Averages Before and After Trade for Last30
    team1_avg_before_last30 = calculate_team_averages(df_last30, team1_players_current_normalized, num_top_players)
    team1_avg_after_last30 = calculate_team_averages(df_last30, team1_players_after_normalized, num_top_players)

    team2_avg_before_last30 = calculate_team_averages(df_last30, team2_players_current_normalized, num_top_players)
    team2_avg_after_last30 = calculate_team_averages(df_last30, team2_players_after_normalized, num_top_players)

# ------------------- Display Team Averages -------------------

    st.markdown("<h3 style='text-align: center;'>Team Averages Before and After Trade</h3>", unsafe_allow_html=True)

    categories = ['FG%', 'FT%', '3PM', 'PTS', 'TREB', 'AST', 'STL', 'BLK', 'TO']

    def create_avg_dataframe(team_name, avg_before, avg_after):
        # Create DataFrame with numerical values
        data = {
            'Category': categories,
            'Before Trade': [avg_before.get(cat, 0) for cat in categories],
            'After Trade': [avg_after.get(cat, 0) for cat in categories],
        }
        df = pd.DataFrame(data)
        
        # Round 'Before Trade' and 'After Trade' to match displayed precision
        def round_value(value, category):
            if category in ['FG%', 'FT%']:
                return round(value, 3)
            else:
                return round(value, 2)
        df['Before Trade'] = df.apply(lambda row: round_value(row['Before Trade'], row['Category']), axis=1)
        df['After Trade'] = df.apply(lambda row: round_value(row['After Trade'], row['Category']), axis=1)
        
        # Calculate the difference using rounded values
        df['Diff'] = df['After Trade'] - df['Before Trade']
        
        # Set 'Category' as index and transpose
        df.set_index('Category', inplace=True)
        df_transposed = df.transpose()
        return df_transposed

    def format_team_avg_dataframe(df):
        # Function to format and style the DataFrame
        def format_value(value, category):
            if category in ['FG%', 'FT%']:
                return f"{value:.3f}"
            else:
                return f"{value:.2f}"
        
        formatted_df = df.copy()
        for col in formatted_df.columns:
            formatted_df[col] = formatted_df[col].apply(lambda x: format_value(x, col))
        
        # Apply conditional formatting to 'Diff' row
        def highlight_diff_row(row):
            if row.name != 'Diff':
                return [''] * len(row)
            else:
                styles = []
                for col in row.index:
                    val = float(row[col])
                    if val == 0:
                        color = ''  # No coloring if difference is zero
                    else:
                        if col == 'TO':
                            # Invert logic for 'TO'
                            if val > 0:
                                color = 'salmon'      # Increased TO is bad (red)
                            elif val < 0:
                                color = 'lightgreen'  # Decreased TO is good (green)
                        else:
                            if val > 0:
                                color = 'lightgreen'  # Improvement (green)
                            elif val < 0:
                                color = 'salmon'      # Decline (red)
                    styles.append(f'background-color: {color}')
                return styles
        styled_df = formatted_df.style.apply(highlight_diff_row, axis=1)
        return styled_df

    # Display Regular Season Averages
    st.markdown("#### 📊 Regular Season Averages")

    col_team1, col_team2 = st.columns(2)

    with col_team1:
        st.markdown(f"### {team1_name}")
        df_team1_regular = create_avg_dataframe(team1_name, team1_avg_before_regular, team1_avg_after_regular)
        styled_df_team1_regular = format_team_avg_dataframe(df_team1_regular)
        st.write(styled_df_team1_regular)

    with col_team2:
        st.markdown(f"### {team2_name}")
        df_team2_regular = create_avg_dataframe(team2_name, team2_avg_before_regular, team2_avg_after_regular)
        styled_df_team2_regular = format_team_avg_dataframe(df_team2_regular)
        st.write(styled_df_team2_regular)

    # Display Rest of Season Projections Averages
    st.markdown("#### 🔮 Rest of Season Projections Averages")

    col_team1_proj, col_team2_proj = st.columns(2)

    with col_team1_proj:
        st.markdown(f"### {team1_name}")
        df_team1_projection = create_avg_dataframe(team1_name, team1_avg_before_projection, team1_avg_after_projection)
        styled_df_team1_projection = format_team_avg_dataframe(df_team1_projection)
        st.write(styled_df_team1_projection)

    with col_team2_proj:
        st.markdown(f"### {team2_name}")
        df_team2_projection = create_avg_dataframe(team2_name, team2_avg_before_projection, team2_avg_after_projection)
        styled_df_team2_projection = format_team_avg_dataframe(df_team2_projection)
        st.write(styled_df_team2_projection)

    # Display Last14 Averages
    st.markdown("#### 📊 Last 14 Days Averages")

    col_team1_last14, col_team2_last14 = st.columns(2)

    with col_team1_last14:
        st.markdown(f"### {team1_name}")
        df_team1_last14 = create_avg_dataframe(team1_name, team1_avg_before_last14, team1_avg_after_last14)
        styled_df_team1_last14 = format_team_avg_dataframe(df_team1_last14)
        st.write(styled_df_team1_last14)

    with col_team2_last14:
        st.markdown(f"### {team2_name}")
        df_team2_last14 = create_avg_dataframe(team2_name, team2_avg_before_last14, team2_avg_after_last14)
        styled_df_team2_last14 = format_team_avg_dataframe(df_team2_last14)
        st.write(styled_df_team2_last14)

    # Display Last30 Averages
    st.markdown("#### 📊 Last 30 Days Averages")

    col_team1_last30, col_team2_last30 = st.columns(2)

    with col_team1_last30:
        st.markdown(f"### {team1_name}")
        df_team1_last30 = create_avg_dataframe(team1_name, team1_avg_before_last30, team1_avg_after_last30)
        styled_df_team1_last30 = format_team_avg_dataframe(df_team1_last30)
        st.write(styled_df_team1_last30)

    with col_team2_last30:
        st.markdown(f"### {team2_name}")
        df_team2_last30 = create_avg_dataframe(team2_name, team2_avg_before_last30, team2_avg_after_last30)
        styled_df_team2_last30 = format_team_avg_dataframe(df_team2_last30)
        st.write(styled_df_team2_last30)

    # ------------------- Prepare Share Message and Display WhatsApp Button -------------------

    # Prepare the team averages data for sharing
    def df_to_text(df, team_name, title):
        """
        Converts the DataFrame to a formatted text table for sharing.

        Parameters:
        - df: DataFrame containing the team averages (transposed)
        - team_name: Name of the team
        - title: Title for the table (e.g., "Regular Season Averages")

        Returns:
        - A string representing the formatted table
        """
        lines = []
        lines.append(f"{team_name} - {title}")
        lines.append("Category |   Before  |   After   |    Diff")
        lines.append("-----------------------------------------")

        for category in df.columns:
            before = df.at['Before Trade', category]
            after = df.at['After Trade', category]
            diff = df.at['Diff', category]

            # Format values with appropriate decimal places
            if category in ['FG%', 'FT%']:
                before_formatted = f"{float(before):.3f}"
                after_formatted = f"{float(after):.3f}"
                diff_formatted = f"{float(diff):+0.003f}"
            else:
                before_formatted = f"{float(before):.2f}"
                after_formatted = f"{float(after):.2f}"
                diff_formatted = f"{float(diff):+0.2f}"

            # Format the line with alignment
            line = f"{category:<8} | {before_formatted:>8} | {after_formatted:>8} | {diff_formatted:>8}"
            lines.append(line)

        table_text = "\n".join(lines)
        return table_text

    # Generate text representations of the tables
    team1_regular_avg_text = df_to_text(df_team1_regular, team1_name, "Regular Season Averages")
    team2_regular_avg_text = df_to_text(df_team2_regular, team2_name, "Regular Season Averages")
    team1_projection_avg_text = df_to_text(df_team1_projection, team1_name, "Rest of Season Projections")
    team2_projection_avg_text = df_to_text(df_team2_projection, team2_name, "Rest of Season Projections")
    team1_last14_avg_text = df_to_text(df_team1_last14, team1_name, "Last 14 Days Averages")
    team2_last14_avg_text = df_to_text(df_team2_last14, team2_name, "Last 14 Days Averages")
    team1_last30_avg_text = df_to_text(df_team1_last30, team1_name, "Last 30 Days Averages")
    team2_last30_avg_text = df_to_text(df_team2_last30, team2_name, "Last 30 Days Averages")

    # Create share message including the team averages
    share_message = (
        f"--- {team1_name} Player Details ---\n{team1_details_text}\n\n"
        f"--- {team2_name} Player Details ---\n{team2_details_text}\n\n"
        f"--- Team Averages Before and After Trade ---\n\n"
        f"{team1_regular_avg_text}\n\n"
        f"{team2_regular_avg_text}\n\n"
        f"{team1_projection_avg_text}\n\n"
        f"{team2_projection_avg_text}\n\n"
        f"{team1_last14_avg_text}\n\n"
        f"{team2_last14_avg_text}\n\n"
        f"{team1_last30_avg_text}\n\n"
        f"{team2_last30_avg_text}\n"
    )

    # Display WhatsApp share button
    display_whatsapp_share_button(share_message)

# ----------------------- Load Data Functions -----------------------

@st.cache_data
def load_regular_season_data():
    """
    Loads and processes regular season data.
    """
    regular_season_path = os.path.join(data_dir, "2024-25_NBA_Regular_Season_Updated_daily.xlsx")
    try:
        df_regular_season = pd.read_excel(regular_season_path)
        # Select required columns including 'R#'
        required_columns = ['PLAYER', 'R#', 'FG%', 'FT%', '3PM', 'PTS', 'TREB', 'AST', 'STL', 'BLK', 'TO', 'FGA', 'FTA']
        missing_cols = set(required_columns) - set(df_regular_season.columns)
        if missing_cols:
            st.error(f"Regular Season Rankings is missing columns: {', '.join(missing_cols)}")
            df_regular_season = pd.DataFrame()
        else:
            df_regular_season = df_regular_season[required_columns].copy()
            # Rename 'PLAYER' to 'Player_Name'
            df_regular_season = df_regular_season.rename(columns={'PLAYER': 'Player_Name'})
            # Ensure numerical columns are float, except for FGA and FTA which are strings
            numerical_cols = ['3PM', 'PTS', 'TREB', 'AST', 'STL', 'BLK', 'TO', 'R#']
            for col in numerical_cols:
                df_regular_season[col] = pd.to_numeric(df_regular_season[col], errors='coerce')
            # Remove existing 'Rank' column if present
            if 'Rank' in df_regular_season.columns:
                df_regular_season.drop(columns=['Rank'], inplace=True)
            # Reset index and rename 'index' to 'Rank'
            df_regular_season.reset_index(inplace=True)
            df_regular_season.rename(columns={'index': 'Rank'}, inplace=True)
            df_regular_season['Rank'] = df_regular_season['Rank'] + 1
            # Reorder columns to have 'Rank' first
            columns_order = ['Rank', 'R#', 'Player_Name', 'FG%', 'FT%', '3PM', 'PTS', 'TREB', 'AST', 'STL', 'BLK', 'TO', 'FGA', 'FTA']
            df_regular_season = df_regular_season[columns_order]
        return df_regular_season
    except Exception as e:
        st.error(f"Failed to load Regular Season Rankings: {e}")
        return pd.DataFrame()

@st.cache_data
def load_rest_of_season_data():
    """
    Loads and processes rest of season projections data.
    """
    rest_of_season_path = os.path.join(data_dir, "2024-25_Rest_of_Season_Rankings_Projections_updated_daily.xlsx")
    try:
        df_rest_of_season = pd.read_excel(rest_of_season_path)
        # Select required columns including 'R#'
        required_columns = ['PLAYER', 'R#', 'FG%', 'FT%', '3PM', 'PTS', 'TREB', 'AST', 'STL', 'BLK', 'TO', 'FGA', 'FTA']
        missing_cols = set(required_columns) - set(df_rest_of_season.columns)
        if missing_cols:
            st.error(f"Rest of Season Projections is missing columns: {', '.join(missing_cols)}")
            df_rest_of_season = pd.DataFrame()
        else:
            df_rest_of_season = df_rest_of_season[required_columns].copy()
            # Rename 'PLAYER' to 'Player_Name'
            df_rest_of_season = df_rest_of_season.rename(columns={'PLAYER': 'Player_Name'})
            # Ensure numerical columns are float, except for FGA and FTA which are strings
            numerical_cols = ['3PM', 'PTS', 'TREB', 'AST', 'STL', 'BLK', 'TO', 'R#']
            for col in numerical_cols:
                df_rest_of_season[col] = pd.to_numeric(df_rest_of_season[col], errors='coerce')
            # Remove existing 'Rank' column if present
            if 'Rank' in df_rest_of_season.columns:
                df_rest_of_season.drop(columns=['Rank'], inplace=True)
            # Reset index and rename 'index' to 'Rank'
            df_rest_of_season.reset_index(inplace=True)
            df_rest_of_season.rename(columns={'index': 'Rank'}, inplace=True)
            df_rest_of_season['Rank'] = df_rest_of_season['Rank'] + 1
            # Reorder columns to have 'Rank' first
            columns_order = ['Rank', 'R#', 'Player_Name', 'FG%', 'FT%', '3PM', 'PTS', 'TREB', 'AST', 'STL', 'BLK', 'TO', 'FGA', 'FTA']
            df_rest_of_season = df_rest_of_season[columns_order]
        return df_rest_of_season
    except Exception as e:
        st.error(f"Failed to load Rest of Season Projections: {e}")
        return pd.DataFrame()

@st.cache_data
def load_last14_data():
    """
    Loads and processes Last 14 Days data.
    """
    last14_path = os.path.join(data_dir, "Last_14_days_of_the_2024-25_NBA_Regular_Season_Updated_daily.xlsx")
    try:
        df_last14 = pd.read_excel(last14_path)
        # Process similar to regular season data
        required_columns = ['PLAYER', 'R#', 'FG%', 'FT%', '3PM', 'PTS', 'TREB', 'AST', 'STL', 'BLK', 'TO', 'FGA', 'FTA']
        df_last14 = df_last14[required_columns].copy()
        df_last14 = df_last14.rename(columns={'PLAYER': 'Player_Name'})
        numerical_cols = ['3PM', 'PTS', 'TREB', 'AST', 'STL', 'BLK', 'TO', 'R#']
        for col in numerical_cols:
            df_last14[col] = pd.to_numeric(df_last14[col], errors='coerce')
        df_last14['Player_Name_Normalized'] = df_last14['Player_Name'].apply(normalize_player_name)
        return df_last14
    except Exception as e:
        st.error(f"Failed to load Last 14 Days data: {e}")
        return pd.DataFrame()

@st.cache_data
def load_last30_data():
    """
    Loads and processes Last 30 Days data.
    """
    last30_path = os.path.join(data_dir, "Last_30_days_of_the_2024-25_NBA_Regular_Season_Updated_daily.xlsx")
    try:
        df_last30 = pd.read_excel(last30_path)
        # Process similar to regular season data
        required_columns = ['PLAYER', 'R#', 'FG%', 'FT%', '3PM', 'PTS', 'TREB', 'AST', 'STL', 'BLK', 'TO', 'FGA', 'FTA']
        df_last30 = df_last30[required_columns].copy()
        df_last30 = df_last30.rename(columns={'PLAYER': 'Player_Name'})
        numerical_cols = ['3PM', 'PTS', 'TREB', 'AST', 'STL', 'BLK', 'TO', 'R#']
        for col in numerical_cols:
            df_last30[col] = pd.to_numeric(df_last30[col], errors='coerce')
        df_last30['Player_Name_Normalized'] = df_last30['Player_Name'].apply(normalize_player_name)
        return df_last30
    except Exception as e:
        st.error(f"Failed to load Last 30 Days data: {e}")
        return pd.DataFrame()

# ----------------------- Load Team Rosters -----------------------

@st.cache_data
def load_team_rosters(yahoo_dir):
    """
    Loads team rosters from all XLSX files in the yahoo directory.
    Each file should contain columns: 'Oyuncu Adı', 'Pozisyon'
    Team name is extracted from the filename.
    """
    roster_files = glob.glob(os.path.join(yahoo_dir, "*.xlsx"))
    team_rosters = pd.DataFrame()

    for file in roster_files:
        try:
            df = pd.read_excel(file)
            # Ensure required columns are present
            if set(['Oyuncu Adı', 'Pozisyon']).issubset(df.columns):
                # Extract team name from filename
                filename = os.path.splitext(os.path.basename(file))[0]
                team_name = filename  # Assuming filename is the team name
                df['Takım'] = team_name  # Assign team name to 'Takım' column
                team_rosters = pd.concat([team_rosters, df], ignore_index=True)
            else:
                st.error(f"File {file} is missing required columns ('Oyuncu Adı', 'Pozisyon').")
        except Exception as e:
            st.error(f"Failed to read {file}: {e}")

    # Normalize player names for consistency
    team_rosters['Player_Name_Normalized'] = team_rosters['Oyuncu Adı'].apply(normalize_player_name)
    return team_rosters

# ----------------------- Player Scores Analysis Functions -----------------------

@st.cache_data
def load_player_scores(directory_path):
    """
    Loads and processes player scores from Excel files in the specified directory.
    """
    all_data = []
    date_pattern = r'Player_Scores_(\d{2}_\d{2}_\d{4})\.xlsx'
    
    # Find all Excel files matching the pattern
    file_path = os.path.join(directory_path, 'Player_Scores_*.xlsx')
    
    for file in glob.glob(file_path):
        try:
            filename = os.path.basename(file)
            match = re.search(date_pattern, filename)
            if match:
                date_str = match.group(1)  # '02_11_2024'
                date = pd.to_datetime(date_str, format='%d_%m_%Y', errors='coerce')
                if pd.isna(date):
                    print(f"Invalid date format: {filename}")
                    continue
            else:
                print(f"No date information found: {filename}")
                continue
            
            # Read Excel file
            df = pd.read_excel(file, engine='openpyxl')
            
            # Check for required columns
            required_columns = ['Player_Name', 'Regular', 'Projection']
            if not set(required_columns).issubset(df.columns):
                print(f"Missing required columns: {filename}")
                continue
            
            # Select only required columns and add date
            df = df[required_columns].copy()
            df['Date'] = date
            all_data.append(df)
            
        except Exception as e:
            print(f"Error reading {filename}: {e}")
    
    if not all_data:
        raise ValueError("No Excel files could be loaded. Please check the file path and formats.")
    
    # Combine all data
    combined_df = pd.concat(all_data, ignore_index=True)
    
    # Clean data
    combined_df = combined_df.dropna(subset=['Player_Name', 'Regular', 'Projection', 'Date'])
    combined_df['Regular'] = pd.to_numeric(combined_df['Regular'], errors='coerce')
    combined_df['Projection'] = pd.to_numeric(combined_df['Projection'], errors='coerce')
    combined_df = combined_df.dropna(subset=['Regular', 'Projection'])
    
    return combined_df

# ----------------------- Main Application -----------------------

def main():
    # Set Streamlit page configuration
    st.set_page_config(page_title="🏀 Trade Machine 🏀", layout="wide")
    
    if gif_files:
        gif_html = ""
        for gif_path in gif_files:
            data_url = get_base64_gif(gif_path)
            gif_html += f'<img src="data:image/gif;base64,{data_url}" alt="GIF" style="width:100px; height:100px; margin:0; padding:0; display:inline-block; object-fit:cover;">'

        st.markdown(
            f"""
            <div style="text-align:center; margin:0; padding:0; display:flex; justify-content:center; gap:0;">
                {gif_html}
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.warning("No GIFs found in the 'gifs' directory.")

    # Center the title
    st.markdown(
        """
        <div style="text-align: center; font-size: 48px; font-weight: bold; margin-bottom: 20px;">
            Trade Machine
        </div>
        """,
        unsafe_allow_html=True
    )

    # ------------------- Load Data -------------------
    merged_scores_path = os.path.join(data_dir, "merged_scores.xlsx")
    injury_report_path = os.path.join(data_dir, "nba-injury-report.xlsx")

    if os.path.exists(merged_scores_path) and os.path.exists(injury_report_path):
        merged_df = read_data(merged_scores_path, injury_report_path)
        if not merged_df.empty:
            st.session_state['data'] = merged_df
            st.session_state['last_updated'] = get_last_updated(merged_scores_path, injury_report_path)
            data = merged_df
            data_load_status = "Data loaded successfully."
        else:
            data_load_status = "Loaded data is empty. Please ensure the data files are correct."
            data = None
    else:
        data_load_status = "Please place 'merged_scores.xlsx' and 'nba-injury-report.xlsx' in the 'data' directory."
        data = None

    # ------------------- Load Team Rosters -------------------
    if os.path.exists(yahoo_dir):
        team_rosters = load_team_rosters(yahoo_dir)
        if not team_rosters.empty:
            # Normalize player names in merged_df for matching
            data['Player_Name_Normalized'] = data['Player_Name'].apply(normalize_player_name)

            # Get list of normalized database player names
            db_player_names = data['Player_Name_Normalized'].tolist()

            # Perform fuzzy matching
            mapping, unmatched = map_yahoo_to_db_players(team_rosters, db_player_names, threshold=80)

            # Add a new column to team_rosters with matched DB player names
            team_rosters['DB_Player_Name'] = team_rosters['Player_Name_Normalized'].map(mapping)

            # Handle unmatched players
            if unmatched:
                st.warning(f"{len(unmatched)} player(s) could not be matched to the database. They will be excluded from trade evaluations.")
                team_rosters = team_rosters[team_rosters['DB_Player_Name'].notna()]

            # Merge team rosters with player data using DB_Player_Name
            data = pd.merge(data, team_rosters[['DB_Player_Name', 'Takım']], left_on='Player_Name_Normalized', right_on='DB_Player_Name', how='left')
            data['Takım'] = data['Takım'].fillna('Free Agent')  # Assign 'Free Agent' to players not on any team
        else:
            st.error("Please check the 'yahoo' folder.")
    else:
        st.error(f"Yahoo directory not found at {yahoo_dir}. Please ensure the directory exists and contains the roster files.")
        data = None

    # ------------------- Load Regular Season and Projection Data -------------------
    df_regular_season = load_regular_season_data()
    df_rest_of_season = load_rest_of_season_data()

    # Load Last14 and Last30 data
    df_last14 = load_last14_data()
    df_last30 = load_last30_data()

    # Normalize player names in regular season and projection data
    df_regular_season['Player_Name_Normalized'] = df_regular_season['Player_Name'].apply(normalize_player_name)
    df_rest_of_season['Player_Name_Normalized'] = df_rest_of_season['Player_Name'].apply(normalize_player_name)
    df_last14['Player_Name_Normalized'] = df_last14['Player_Name'].apply(normalize_player_name)
    df_last30['Player_Name_Normalized'] = df_last30['Player_Name'].apply(normalize_player_name)

    # Merge 'Takım' column into regular season and projection data
    df_regular_season = pd.merge(df_regular_season, data[['Player_Name_Normalized', 'Takım']], on='Player_Name_Normalized', how='left')
    df_rest_of_season = pd.merge(df_rest_of_season, data[['Player_Name_Normalized', 'Takım']], on='Player_Name_Normalized', how='left')
    df_last14 = pd.merge(df_last14, data[['Player_Name_Normalized', 'Takım']], on='Player_Name_Normalized', how='left')
    df_last30 = pd.merge(df_last30, data[['Player_Name_Normalized', 'Takım']], on='Player_Name_Normalized', how='left')

    # ------------------- Display Data Information under the heading -------------------
    if 'last_updated' in st.session_state:
        last_updated = st.session_state['last_updated']
        st.markdown(
            f"<p style='text-align: right; font-style: italic;'>Last Updated: "
            f"<span style='color: green;'>{last_updated} UTC</span></p>",
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            f"<p style='text-align: center; font-style: italic;'>Last Updated: "
            f"<span style='color: red;'>Not Available</span></p>",
            unsafe_allow_html=True
        )
    if data_load_status != "Data loaded successfully.":
        st.error(data_load_status)

    if data is None or data.empty:
        st.info("No data available. Please ensure the data files are in place.")
        return

    # ------------------- Create Tabs -------------------
    tab1, tab2, tab3 = st.tabs(["Trade Evaluation", "Player Scores Analysis", "Team Scores Analysis"])

    # ------------------- Trade Evaluation Tab -------------------
    with tab1:
        # ------------------- Team Selection -------------------
        
        # Get list of unique fantasy teams excluding 'Free Agent'
        unique_teams = data['Takım'].unique().tolist()
        unique_teams = [team for team in unique_teams if team != 'Free Agent']
        
        if len(unique_teams) < 2:
            st.warning("Not enough teams available for trade evaluation.")
            return

        # Set default indices for the selectboxes
        default_index_team1 = 0  # First team in the list
        default_index_team2 = 1 if len(unique_teams) > 1 else 0  # Second team if available

        # Select Team 1 and Team 2 with different default selections
        col_team_selection = st.columns(2)
        with col_team_selection[0]:
            team1 = st.selectbox(
                "Select Team 1",
                options=unique_teams,
                index=default_index_team1,
                key="team1_select"
            )
        with col_team_selection[1]:
            team2 = st.selectbox(
                "Select Team 2",
                options=unique_teams,
                index=default_index_team2,
                key="team2_select"
            )
        
        if team1 == team2:
            st.error("Please select two different teams for the trade.")
            return

        # ------------------- Player Selection -------------------
        # Get players for each team
        team1_players_available = data[data['Takım'] == team1]['Player_Name'].tolist()
        team2_players_available = data[data['Takım'] == team2]['Player_Name'].tolist()

        # Create two columns for player selections to arrange them side by side
        col_player1, col_player2 = st.columns(2)

        with col_player1:
            st.markdown(f"### {team1} - Select Players to Trade to {team2}")
            team1_selected = st.multiselect(
                f"Select Players from {team1}",
                options=team1_players_available,
                key="team1_selected_players"
            )

        with col_player2:
            st.markdown(f"### {team2} - Select Players to Trade to {team1}")
            team2_selected = st.multiselect(
                f"Select Players from {team2}",
                options=team2_players_available,
                key="team2_selected_players"
            )

        # Injury Status Selection for both teams side by side
        if team1_selected or team2_selected:
            st.markdown("<h4 style='text-align: center;'>Player Injury Status</h4>", unsafe_allow_html=True)
            col_injuries_team1, col_injuries_team2 = st.columns(2)
            
            # Injury options and adjustments
            injury_options = {
                "No Injury": 0,
                "IL - Up to 4 Weeks (-1)": -1,
                "IL - Indefinitely (-2)": -2
            }
            
            # Team 1 Injury Status
            team1_injury_adjustments = []
            with col_injuries_team1:
                if team1_selected:
                    st.markdown(f"#### {team1} Injury Adjustments", unsafe_allow_html=True)
                    for idx, player in enumerate(team1_selected):
                        col_player, col_status = st.columns([1, 3])
                        with col_player:
                            st.write(player)
                        with col_status:
                            injury_status = st.selectbox(
                                "Injury Status",
                                options=list(injury_options.keys()),
                                key=f"team1_{player}_injury_status"
                            )
                        # Get the adjustment from the dictionary
                        injury_adjustment = injury_options[injury_status]
                        team1_injury_adjustments.append(injury_adjustment)
                else:
                    team1_injury_adjustments = []

            # Team 2 Injury Status
            team2_injury_adjustments = []
            with col_injuries_team2:
                if team2_selected:
                    st.markdown(f"#### {team2} Injury Adjustments", unsafe_allow_html=True)
                    for idx, player in enumerate(team2_selected):
                        col_player, col_status = st.columns([1, 3])
                        with col_player:
                            st.write(player)
                        with col_status:
                            injury_status = st.selectbox(
                                "Injury Status",
                                options=list(injury_options.keys()),
                                key=f"team2_{player}_injury_status"
                            )
                        # Get the adjustment from the dictionary
                        injury_adjustment = injury_options[injury_status]
                        team2_injury_adjustments.append(injury_adjustment)
                else:
                    team2_injury_adjustments = []

        else:
            team1_injury_adjustments = []
            team2_injury_adjustments = []

        # Add a number input for selecting the number of top players
        num_top_players = st.number_input(
            "Number of Top Players to Consider for Team Averages",
            min_value=1,
            max_value=18,  # Adjust based on your league's maximum team size
            value=15,      # Default value
            step=1
        )

        # Center the Evaluate Trade button using columns
        col_center = st.columns([1, 0.275, 1])
        with col_center[1]:
            submitted = st.button("Evaluate Trade")

        if submitted:
            # Check for duplicates
            duplicate_players = set(team1_selected) & set(team2_selected)
            if duplicate_players:
                st.error(f"Error: The following player(s) are selected for both teams: {', '.join(duplicate_players)}. Please select different players for each team.")
            else:
                if not team1_selected and not team2_selected:
                    st.warning("Please select players for both teams to evaluate a trade.")
                else:
                    evaluate_trade(
                        data,
                        team1_selected,
                        team2_selected,
                        team1_injury_adjustments,
                        team2_injury_adjustments,
                        team1,
                        team2,
                        df_regular_season,
                        df_rest_of_season,
                        df_last14,
                        df_last30,
                        num_top_players  # Pass the number of top players
                    )

     # ------------------- Player Scores Analysis Tab -------------------
    with tab2:

        # Load Player Scores Data
        try:
            player_scores = load_player_scores(player_scores_dir)
            #st.success("Player scores data loaded successfully.")
        except ValueError as ve:
            st.error(ve)
            return
        except Exception as e:
            st.error(f"An unexpected error occurred: {e}")
            return

        if player_scores.empty:
            st.info("No player scores data available.")
            return

        # Get list of unique players
        players = sorted(player_scores['Player_Name'].unique())

        # Player selection
        selected_player = st.selectbox("Select a Player", options=players)

        if selected_player:
            player_data = player_scores[player_scores['Player_Name'] == selected_player].sort_values('Date')

            if player_data.empty:
                st.warning(f"No data available for {selected_player}.")
            else:
                # Plotting
                fig, ax = plt.subplots(figsize=(10, 6))
                ax.plot(player_data['Date'], player_data['Regular'], label='Regular Score', marker='o', color='blue')
                ax.plot(player_data['Date'], player_data['Projection'], label='Projection Score', marker='o', color='orange')

                ax.set_xlabel('Date')
                ax.set_ylabel('Score')
                ax.set_title(f'{selected_player} - Regular and Projection Scores Over Time')
                ax.legend()
                ax.grid(True)
                plt.xticks(rotation=45)
                plt.tight_layout()
                st.pyplot(fig)

    # ------------------- Team Scores Analysis Tab -------------------
    with tab3:

        # Load Player Scores Data
        try:
            player_scores = load_player_scores(player_scores_dir)
            #st.success("Player scores data loaded successfully.")
        except ValueError as ve:
            st.error(ve)
            return
        except Exception as e:
            st.error(f"An unexpected error occurred: {e}")
            return

        if player_scores.empty:
            st.info("No player scores data available.")
            return

        # Get list of teams excluding 'Free Agent'
        teams = sorted([team for team in data['Takım'].unique() if team != 'Free Agent'])

        # Team selection
        selected_team = st.selectbox("Select a Team", options=teams)

        if selected_team:
            # Get list of players in the selected team
            team_players = data[data['Takım'] == selected_team]['Player_Name'].unique()

            if len(team_players) == 0:
                st.warning(f"No players found for team {selected_team}.")
            else:
                # Allow user to select which players to include
                selected_players = st.multiselect("Select Players to Include", options=team_players, default=team_players)

                if not selected_players:
                    st.warning("No players selected.")
                else:
                    # Allow user to select which scores to display
                    score_type = st.radio(
                        "Select Score Type to Display",
                        options=["Regular", "Projection", "Both"],
                        index=2  # Default to "Both"
                    )

                    # Initialize the plot
                    fig, ax = plt.subplots(figsize=(12, 8))

                    # Define line styles for Regular and Projection scores
                    line_styles = {'Regular': '-', 'Projection': '--'}

                    # For each selected player, plot their scores over time based on selected score type
                    for player in selected_players:
                        player_data = player_scores[player_scores['Player_Name'] == player].sort_values('Date')
                        if player_data.empty:
                            st.warning(f"No data available for {player}.")
                            continue
                        else:
                            if score_type in ["Regular", "Both"]:
                                # Plot Regular Score
                                line1, = ax.plot(
                                    player_data['Date'],
                                    player_data['Regular'],
                                    linestyle=line_styles['Regular'],
                                    marker='o'
                                )
                                # Annotate the last point with player name
                                ax.annotate(
                                    f"{player} - Regular",
                                    xy=(player_data['Date'].iloc[-1], player_data['Regular'].iloc[-1]),
                                    xytext=(5, 0),
                                    textcoords='offset points',
                                    color=line1.get_color(),
                                    fontsize=9
                                )
                            if score_type in ["Projection", "Both"]:
                                # Plot Projection Score
                                line2, = ax.plot(
                                    player_data['Date'],
                                    player_data['Projection'],
                                    linestyle=line_styles['Projection'],
                                    marker='x'
                                )
                                # Annotate the last point with player name
                                ax.annotate(
                                    f"{player} - Projection",
                                    xy=(player_data['Date'].iloc[-1], player_data['Projection'].iloc[-1]),
                                    xytext=(5, 0),
                                    textcoords='offset points',
                                    color=line2.get_color(),
                                    fontsize=9
                                )

                    ax.set_xlabel('Date')
                    ax.set_ylabel('Score')
                    if score_type == "Both":
                        ax.set_title(f'{selected_team} Players - Regular and Projection Scores Over Time')
                    else:
                        ax.set_title(f'{selected_team} Players - {score_type} Scores Over Time')
                    # Remove the legend
                    # ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
                    ax.grid(True)
                    plt.xticks(rotation=45)
                    plt.tight_layout()
                    st.pyplot(fig)

# ----------------------- Run the Application -----------------------

if __name__ == "__main__":
    main()
