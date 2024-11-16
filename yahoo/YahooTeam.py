from pathlib import Path
import pandas as pd
import unicodedata
from yfpy.query import YahooFantasySportsQuery
from datetime import datetime

# Liginizin ID'sini ve oyun kodunu girin
league_id = "40022"  # Örneğin: '123456'
game_code = "nba"  # Basketbol için oyun kodu (NBA için "nba")

# Yahoo API tüketici anahtarları
consumer_key = "dj0yJmk9dHV5dHFVUGtLM3liJmQ9WVdrOVZtOXNhR0ZuTm5ZbWNHbzlNQT09JnM9Y29uc3VtZXJzZWNyZXQmc3Y9MCZ4PTg4"  # Buraya kendi Consumer Key'inizi ekleyin
consumer_secret = "5b85c3599d87375da2f73b87864ccd3eed9e575d"  # Buraya kendi Consumer Secret'inizi ekleyin

# Özel isim düzeltmeleri için bir sözlük oluşturun
name_corrections = {
    "Jakob Poltl": "Jakob Poeltl",
    "Dennis Schroder": "Dennis Schröder",
    "Alperen Sengun": "Alperen Sengün",
    "Nic Claxton": "Nicolas Claxton",
    "Alex Sarr": "Alexandre Sarr"
}

# YahooFantasySportsQuery nesnesini oluşturun
query = YahooFantasySportsQuery(
    league_id=league_id,
    game_code=game_code,
    yahoo_consumer_key=consumer_key,
    yahoo_consumer_secret=consumer_secret,
    all_output_as_json_str=False
)

# Lig bilgilerini alın
league = query.get_league_info()
print(f"Lig Adı: {league.name}")

# Takım bilgilerini alın
teams = query.get_league_teams()

# Bugünün tarihini alın (YYYY-MM-DD formatında)
today_date = datetime.now().strftime('%Y-%m-%d')

# Her takım için oyuncu bilgilerini alın ve ayrı Excel dosyalarına kaydedin
for team in teams:
    # Takım adını bytes'tan str'ye dönüştürün
    team_name = team.name.decode('utf-8') if isinstance(team.name, bytes) else team.name
    roster = query.get_team_roster_player_info_by_date(team_id=team.team_id, chosen_date=today_date)

    # Oyuncu bilgilerini toplayın
    data = []
    for player in roster:
        original_player_name = player.name.full
        
        # Oyuncu ismini normalize edin (ASCII karakterlere dönüştür)
        normalized_player_name = unicodedata.normalize('NFKD', original_player_name).encode('ASCII', 'ignore').decode('ASCII')
        
        # Eğer normalize edilmiş isim düzeltme sözlüğünde varsa, düzeltin
        final_player_name = name_corrections.get(normalized_player_name, normalized_player_name)
        
        player_info = {
            'Oyuncu Adı': final_player_name,
            'Pozisyon': player.display_position,
            'Takım': player.editorial_team_full_name
        }
        data.append(player_info)

    # Verileri bir DataFrame'e dönüştürün
    df = pd.DataFrame(data)

    # Takım adını normalize edin ve geçersiz dosya adı karakterlerini temizleyin
    normalized_team_name = unicodedata.normalize('NFKD', team_name).encode('ASCII', 'ignore').decode('ASCII')
    valid_team_name = "".join(c for c in normalized_team_name if c.isalnum() or c in " _-").rstrip()
    file_name = f"{valid_team_name}.xlsx"
    df.to_excel(file_name, index=False)
    print(f"{team_name} için {today_date} tarihli oyuncu bilgileri {file_name} dosyasına kaydedildi.")