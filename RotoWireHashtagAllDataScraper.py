from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import pandas as pd
import os
import time
import re

# ----------------------- Ayarlar ve Yollar -----------------------

# WebDriver yolunu belirt
driver_path = "/Users/ibrahimkucukkaya/Downloads/chromedriver-mac-arm64/chromedriver"

# RotoWire URL
rotowire_url = 'https://www.rotowire.com/basketball/injury-report.php'

# Hashtag Basketball URL
hashtag_url = "https://hashtagbasketball.com/fantasy-basketball-rankings"

# İndirilen dosyanın kaydedileceği klasör
download_dir = '/Users/ibrahimkucukkaya/Desktop/Streamlit/data'

# Hashtag Basketball için veri kaydetme klasörü (Directly in 'AVG' folder)
output_dir = download_dir

# Klasör yoksa oluştur (Bu durumda zaten download_dir mevcut olduğundan gerek yok)
# Ancak güvenlik için kontrol edebiliriz
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# RotoWire Excel dosyası yolu
rotowire_file_path = os.path.join(download_dir, "nba-injury-report.xlsx")

# Selenium Chrome seçenekleri
options = Options()
options.add_argument("--headless")  # Headless modu etkinleştir
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_experimental_option("prefs", {
    "download.default_directory": download_dir,
    "download.prompt_for_download": False,
    "safebrowsing.enabled": True
})

# ----------------------- WebDriver Başlatma -----------------------

service = Service(driver_path)
driver = webdriver.Chrome(service=service, options=options)

# ----------------------- RotoWire İşlemleri -----------------------

def process_rotowire():
    print("RotoWire'den Excel dosyası indiriliyor...")
    driver.get(rotowire_url)
    
    try:
        # İndirmeye başlamadan önce mevcut dosya varsa sil
        if os.path.exists(rotowire_file_path):
            os.remove(rotowire_file_path)
            print(f"Mevcut dosya silindi: {rotowire_file_path}")
        
        # Excel düğmesini bulup tıklamak için bekleme
        wait = WebDriverWait(driver, 20)
        excel_button = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="injury-report"]/div[3]/div[2]/button[1]')))
        ActionChains(driver).move_to_element(excel_button).click().perform()
        print("Excel dosyası indiriliyor...")
        
        # İndirme işlemi için bekleme
        download_wait_time = 30  # Süreyi ihtiyaca göre artırabilirsiniz
        for _ in range(download_wait_time):
            if os.path.exists(rotowire_file_path):
                print("Excel dosyası indirildi.")
                break
            time.sleep(1)
        else:
            print("Excel dosyası indirme süresi aşıldı.")
            return
        
        # Excel dosyasını okuma ve takım isimlerini değiştirme
        df = pd.read_excel(rotowire_file_path)
        
        # Team sütunundaki isimleri değiştirme
        team_changes = {
            'GSW': 'GS',
            'NOP': 'NO',
            'NYK': 'NY',
            'PHX': 'PHO',
            'SAS': 'SA'
        }
        df['Team'] = df['Team'].replace(team_changes)
        
        # Est. Return sütununu silme
        if 'Est. Return' in df.columns:
            df = df.drop(columns=['Est. Return'])
        
        # Değişiklikleri kaydetme
        df.to_excel(rotowire_file_path, index=False)
        print("RotoWire Excel dosyası işlendi ve kaydedildi.")
    
    except Exception as e:
        print("RotoWire işlemi sırasında bir hata oluştu:", e)

# ----------------------- Hashtag Basketball İşlemleri -----------------------

def fetch_h2h_data(url, h2h_dropdown_xpath, yahoo_dropdown_xpath, show_dropdown_xpath, duration_xpath, duration_option):
    driver.get(url)
    time.sleep(5)

    try:
        wait = WebDriverWait(driver, 20)
        
        # DATA AND RANKINGS FROM dropdown seçimi
        duration_dropdown = wait.until(EC.presence_of_element_located((By.XPATH, duration_xpath)))
        duration_select = Select(duration_dropdown)
        duration_select.select_by_visible_text(duration_option)
        time.sleep(3)

        # H2H seçeneği seçimi
        h2h_dropdown = wait.until(EC.presence_of_element_located((By.XPATH, h2h_dropdown_xpath)))
        h2h_select = Select(h2h_dropdown)
        h2h_select.select_by_visible_text("H2H")
        time.sleep(3)

        # Yahoo dropdown seçimi
        yahoo_dropdown = wait.until(EC.presence_of_element_located((By.XPATH, yahoo_dropdown_xpath)))
        yahoo_select = Select(yahoo_dropdown)
        yahoo_select.select_by_visible_text("Yahoo")
        time.sleep(3)

        # Show dropdown seçimi
        show_dropdown = wait.until(EC.presence_of_element_located((By.XPATH, show_dropdown_xpath)))
        show_select = Select(show_dropdown)
        show_select.select_by_visible_text("All")
        time.sleep(5)

        # HTML yapısını çek ve işleyin
        page_source = driver.execute_script("return document.body.innerHTML;")
        soup = BeautifulSoup(page_source, 'html.parser')

        tables = soup.find_all('table')

        for i, table in enumerate(tables):
            headers = [th.get_text().strip() for th in table.find_all('th')]

            if 'PLAYER' in headers and 'TOTAL' in headers:
                rows = table.find('tbody').find_all('tr')
                data = []

                # Tablo verilerini çekme
                for row in rows:
                    cols = row.find_all('td')
                    row_data = [col.get_text().strip() for col in cols]
                    data.append(row_data)

                # DataFrame oluştur
                df = pd.DataFrame(data, columns=headers)
                df = df[df[headers[0]] != headers[0]]
                df.dropna(inplace=True)
                
                return df
        else:
            raise ValueError("Beklenen tablo yapısı bulunamadı.")

    except Exception as e:
        print(f"Error occurred while fetching H2H data: {e}")
        return None

def extract_FGA_FTA(df):
    """
    FGA ve FTA değerlerini FG% ve FT% değerlerini koruyarak ayıklar.
    FG% formatı: "0.450 (9.0/20.0)"
    FT% formatı: "0.862 (12.5/14.5)"
    """
    df['FGA'] = None
    df['FTA'] = None

    pattern_fg = r'^(?P<FG_percentage>[\d.]+)\s*\((?P<FGA_full>[\d.]+/[\d.]+)\)$'
    pattern_ft = r'^(?P<FT_percentage>[\d.]+)\s*\((?P<FTA_full>[\d.]+/[\d.]+)\)$'

    if 'FG%' in df.columns:
        fg_extracted = df['FG%'].str.extract(pattern_fg)
        df['FG%'] = fg_extracted['FG_percentage'].astype(float).map(lambda x: f"{x:.3f}")
        df['FGA'] = fg_extracted['FGA_full']

    if 'FT%' in df.columns:
        ft_extracted = df['FT%'].str.extract(pattern_ft)
        df['FT%'] = ft_extracted['FT_percentage'].astype(float).map(lambda x: f"{x:.3f}")
        df['FTA'] = ft_extracted['FTA_full']
    
    if 'R#' in df.columns:
        df['R#'] = range(1, len(df) + 1)
        
    return df

def process_hashtag_basketball():
    # Belirli seçimler için Excel dosyalarını kaydetme
    selections = [
        "2024-25 Rest of Season Rankings (Projections updated daily)",
        "2024-25 NBA Regular Season (Updated daily)",
        "2023-24 NBA Regular Season"
    ]
    
    print("Hashtag Basketball verileri çekiliyor ve işleniyor...")
    for selection in selections:
        df = fetch_h2h_data(
            url=hashtag_url,
            h2h_dropdown_xpath='//*[@id="ContentPlaceHolder1_DDTYPE"]',
            yahoo_dropdown_xpath='//*[@id="ContentPlaceHolder1_DDPOSFROM"]',
            show_dropdown_xpath='//*[@id="ContentPlaceHolder1_DDSHOW"]',
            duration_xpath='//*[@id="ContentPlaceHolder1_DDDURATION"]',
            duration_option=selection
        )
    
        if df is not None:
            # Veriyi işleyerek FGA ve FTA sütunlarını ekliyoruz
            df_processed = extract_FGA_FTA(df.copy())

            # İşlenmiş veriyi kaydetme
            safe_selection = re.sub(r'[()/]', '', selection).replace(' ', '_').replace(',', '')
            file_name = f"{safe_selection}.xlsx"
            output_file = os.path.join(output_dir, file_name)
            df_processed.to_excel(output_file, index=False)
            print(f"{selection} için veriler kaydedildi: {output_file}")
        else:
            print(f"{selection} için veri çekilemedi.")
    
    # İki tabloyu birleştirip TOTAL değerlerini ekleme
    try:
        # Dosya adlarını kontrol edin; daha önceki kodda bazı isim hataları vardı, düzelttim
        df_projection_path = os.path.join(output_dir, "2024-25_Rest_of_Season_Rankings_Projections_updated_daily.xlsx")
        df_regular_path = os.path.join(output_dir, "2024-25_NBA_Regular_Season_Updated_daily.xlsx")
        
        if not os.path.exists(df_projection_path):
            raise FileNotFoundError(f"{df_projection_path} dosyası bulunamadı.")
        if not os.path.exists(df_regular_path):
            raise FileNotFoundError(f"{df_regular_path} dosyası bulunamadı.")
        
        df_projection = pd.read_excel(df_projection_path)
        df_regular = pd.read_excel(df_regular_path)

        # TOTAL sütunlarını birleştirerek yeni bir DataFrame oluşturma
        df_projection_total = df_projection[['PLAYER', 'TOTAL']].rename(columns={'TOTAL': 'Projection', 'PLAYER': 'Player_Name'})
        df_regular_total = df_regular[['PLAYER', 'TOTAL']].rename(columns={'TOTAL': 'Regular', 'PLAYER': 'Player_Name'})

        merged_scores = pd.merge(df_projection_total, df_regular_total, on="Player_Name", how="outer")

        # Boş değerleri 2 ile doldurma
        merged_scores.fillna(0, inplace=True)

        # Birleştirilen veriyi kaydetme
        merged_file_path = os.path.join(output_dir, "merged_scores.xlsx")
        merged_scores.to_excel(merged_file_path, index=False)
        print(f"Birleştirilmiş veriler 'merged_scores.xlsx' olarak kaydedildi: {merged_file_path}")

    except Exception as e:
        print(f"Error occurred during merging: {e}")

# ----------------------- Ana İşlem Akışı -----------------------

try:
    # RotoWire işlemleri
    process_rotowire()
    
    # Hashtag Basketball işlemleri
    process_hashtag_basketball()

except Exception as main_e:
    print(f"Genel bir hata oluştu: {main_e}")

finally:
    # Tarayıcıyı kapat
    driver.quit()
    print("WebDriver kapatıldı.")