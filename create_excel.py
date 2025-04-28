import pandas as pd

# Elenco delle squadre
squadre = [
    "ASD AVALON",
    "BOLZANO RUGBY ASD",
    "ASD C'E' L'ESTE RUGBY",
    "PATAVIUM RUGBY JUNIOR A.S.D.",
    "ASD I MAI SOBRI - BEACH RUGBY",
    "OMBRE ROSSE WLFTM OLD R.PADOVA ASD PD",
    "ASD RUGBY TRENTO",
    "RUGBY ROVIGO DELTA SRL SSD",
    "RUGBY PAESE ASD",
    "RUGBY BASSANO 1976 ASD",
    "RUGBY FELTRE ASD",
    "RUGBY BELLUNO ASD",
    "RUGBY CONEGLIANO ASD",
    "RUGBY CASALE ASD",
    "RUGBY VICENZA ASD",
    "RUGBY MIRANO 1957 ASD",
    "RUGBY VALPOLICELLA ASD",
    "VERONA RUGBY ASD"
]

# Crea un DataFrame con le squadre
df = pd.DataFrame(squadre, columns=['Nome Squadra'])

# Salva il DataFrame in un file Excel
df.to_excel('squadre.xlsx', index=False)

print("File Excel 'squadre.xlsx' creato con successo!")