import pandas as pd
import requests


def fetch_meteoswiss_stac(zip_code="1400"):
    # Endpoint STAC de la Confédération (Admin.ch)
    STAC_URL = "https://data.geo.admin.ch/api/stac/v0.9/collections/ch.meteoschweiz.prognosen/items"

    try:
        # 1. Recherche du dernier item (prévision la plus récente)
        response = requests.get(STAC_URL, timeout=15)
        response.raise_for_status()
        items = response.json()['features']

        # On prend le premier item (généralement le plus récent)
        latest_item = items[0]
        print(f"Dernier run MétéoSuisse trouvé : {latest_item['id']}")

        # 2. Récupération de l'URL du fichier CSV pour les localités (PLZ)
        # L'asset 'ch.meteoschweiz.prognosen.csv' contient les données par code postal
        csv_url = latest_item['assets']['ch.meteoschweiz.prognosen_plz.csv']['href']

        # 3. Téléchargement et filtrage immédiat
        # On lit le CSV directement depuis l'URL pour économiser du CPU/RAM
        full_df = pd.read_csv(csv_url, sep=';')

        # Filtrage sur Yverdon (PointId 1400)
        df_yverdon = full_df[full_df['PointId'] == int(zip_code)].copy()

        # 4. Nettoyage et typage
        # MétéoSuisse utilise souvent le format YYYYMMDDHHMM
        df_yverdon['time'] = pd.to_datetime(df_yverdon['Timestamp'], format='%Y%m%d%H%M')
        df_yverdon.set_index('time', inplace=True)

        return df_yverdon

    except Exception as e:
        print(f"Erreur d'accès STAC MétéoSuisse : {e}")
        return None


if __name__ == "__main__":
    df = fetch_meteoswiss_stac("1400")

    if df is not None:
        print("\n--- Données MétéoSuisse pour Yverdon ---")
        print(f"Nombre de lignes : {len(df)}")
        print("\nColonnes disponibles :")
        print(df.columns.tolist())

        # Focus sur les variables clés (selon nomenclature MétéoSuisse)
        # tre200h0 = Température, sre000h0 = Ensoleillement, etc.
        cols_interet = ['tre200h0', 'rre150h0', 'sre000h0', 'gre000h0']
        existing_cols = [c for c in cols_interet if c in df.columns]

        print("\nAperçu des variables énergétiques :")
        print(df[existing_cols].head())