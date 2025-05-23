#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import xlsxwriter
from datetime import datetime
from io import BytesIO
import tempfile

def genera_excel_riepilogo_weekend(risultati_weekend, inizio_weekend_str, fine_weekend_str):
    """
    Genera un file Excel con il riepilogo delle partite del weekend.
    
    Args:
        risultati_weekend: Lista dei risultati delle partite del weekend
        inizio_weekend_str: Data di inizio del weekend in formato stringa
        fine_weekend_str: Data di fine del weekend in formato stringa
        
    Returns:
        BytesIO: Buffer contenente il file Excel
    """
    # Converti le date in oggetti datetime
    inizio_weekend = datetime.strptime(inizio_weekend_str, "%d/%m/%Y")
    fine_weekend = datetime.strptime(fine_weekend_str, "%d/%m/%Y")
    
    # Crea un titolo per il file
    titolo = f"Riepilogo Weekend {inizio_weekend.strftime('%d')} - {fine_weekend.strftime('%d %B %Y')}"
    
    # Prepara i dati per il DataFrame
    dati = []
    for r in risultati_weekend:
        categoria = r.get('categoria', 'Altra categoria')
        genere = r.get('genere', '')
        categoria_completa = f"{categoria} {genere}".strip()
        tipo_partita = r.get('tipo_partita', 'normale')
        data_partita = r.get('data_partita', '')
        arbitro = r.get('arbitro', '')
        
        if tipo_partita == 'triangolare':
            # Partita 1: Squadra1 vs Squadra2
            squadra1 = r.get('squadra1', '')
            squadra2 = r.get('squadra2', '')
            punteggio1 = int(r.get('partita1_punteggio1', 0))
            punteggio2 = int(r.get('partita1_punteggio2', 0))
            mete1 = int(r.get('partita1_mete1', 0))
            mete2 = int(r.get('partita1_mete2', 0))
            
            # Determina il vincitore
            if punteggio1 > punteggio2:
                vincitore = squadra1
            elif punteggio2 > punteggio1:
                vincitore = squadra2
            else:
                vincitore = "Pareggio"
            
            # Aggiungi i dati alla lista
            dati.append({
                'Categoria': categoria_completa + " (Triangolare 1)",
                'Data': data_partita,
                'Squadra Casa': squadra1,
                'Squadra Ospite': squadra2,
                'Punteggio Casa': punteggio1,
                'Punteggio Ospite': punteggio2,
                'Mete Casa': mete1,
                'Mete Ospite': mete2,
                'Vincitore': vincitore,
                'Arbitro': arbitro
            })
            
            # Partita 2: Squadra1 vs Squadra3
            squadra1 = r.get('squadra1', '')
            squadra3 = r.get('squadra3', '')
            punteggio1 = int(r.get('partita2_punteggio1', 0))
            punteggio2 = int(r.get('partita2_punteggio2', 0))
            mete1 = int(r.get('partita2_mete1', 0))
            mete2 = int(r.get('partita2_mete2', 0))
            
            # Determina il vincitore
            if punteggio1 > punteggio2:
                vincitore = squadra1
            elif punteggio2 > punteggio1:
                vincitore = squadra3
            else:
                vincitore = "Pareggio"
            
            # Aggiungi i dati alla lista
            dati.append({
                'Categoria': categoria_completa + " (Triangolare 2)",
                'Data': data_partita,
                'Squadra Casa': squadra1,
                'Squadra Ospite': squadra3,
                'Punteggio Casa': punteggio1,
                'Punteggio Ospite': punteggio2,
                'Mete Casa': mete1,
                'Mete Ospite': mete2,
                'Vincitore': vincitore,
                'Arbitro': arbitro
            })
            
            # Partita 3: Squadra2 vs Squadra3
            squadra2 = r.get('squadra2', '')
            squadra3 = r.get('squadra3', '')
            punteggio1 = int(r.get('partita3_punteggio1', 0))
            punteggio2 = int(r.get('partita3_punteggio2', 0))
            mete1 = int(r.get('partita3_mete1', 0))
            mete2 = int(r.get('partita3_mete2', 0))
            
            # Determina il vincitore
            if punteggio1 > punteggio2:
                vincitore = squadra2
            elif punteggio2 > punteggio1:
                vincitore = squadra3
            else:
                vincitore = "Pareggio"
            
            # Aggiungi i dati alla lista
            dati.append({
                'Categoria': categoria_completa + " (Triangolare 3)",
                'Data': data_partita,
                'Squadra Casa': squadra2,
                'Squadra Ospite': squadra3,
                'Punteggio Casa': punteggio1,
                'Punteggio Ospite': punteggio2,
                'Mete Casa': mete1,
                'Mete Ospite': mete2,
                'Vincitore': vincitore,
                'Arbitro': arbitro
            })
        else:
            # Partita normale
            squadra1 = r.get('squadra1', '')
            squadra2 = r.get('squadra2', '')
            punteggio1 = int(r.get('punteggio1', 0))
            punteggio2 = int(r.get('punteggio2', 0))
            mete1 = int(r.get('mete1', 0))
            mete2 = int(r.get('mete2', 0))
            
            # Determina il vincitore
            if punteggio1 > punteggio2:
                vincitore = squadra1
            elif punteggio2 > punteggio1:
                vincitore = squadra2
            else:
                vincitore = "Pareggio"
            
            # Aggiungi i dati alla lista
            dati.append({
                'Categoria': categoria_completa,
                'Data': data_partita,
                'Squadra Casa': squadra1,
                'Squadra Ospite': squadra2,
                'Punteggio Casa': punteggio1,
                'Punteggio Ospite': punteggio2,
                'Mete Casa': mete1,
                'Mete Ospite': mete2,
                'Vincitore': vincitore,
                'Arbitro': arbitro
            })
    
    # Calcola le statistiche
    totale_partite = len(risultati_weekend)
    totale_punti = sum(int(r.get('punteggio1', 0)) + int(r.get('punteggio2', 0)) for r in risultati_weekend)
    totale_mete = sum(int(r.get('mete1', 0)) + int(r.get('mete2', 0)) for r in risultati_weekend)
    media_punti = round(totale_punti / totale_partite, 1) if totale_partite > 0 else 0
    media_mete = round(totale_mete / totale_partite, 1) if totale_partite > 0 else 0
    
    # Crea un buffer in memoria per il file Excel
    output = BytesIO()
    
    # Crea un workbook e aggiungi i worksheet
    workbook = xlsxwriter.Workbook(output)
    worksheet_risultati = workbook.add_worksheet('Risultati')
    worksheet_stats = workbook.add_worksheet('Statistiche')
        
    # Formatta il foglio dei risultati
    header_format = workbook.add_format({
        'bold': True,
        'text_wrap': True,
        'valign': 'top',
        'fg_color': '#D7E4BC',
        'border': 1
    })
    
    # Definisci le colonne
    columns = ["Categoria", "Data", "Squadra Casa", "Squadra Ospite", "Punteggio Casa", 
               "Punteggio Ospite", "Mete Casa", "Mete Ospite", "Vincitore", "Arbitro"]
    
    # Imposta la larghezza delle colonne
    worksheet_risultati.set_column(0, 0, 20)  # Categoria
    worksheet_risultati.set_column(1, 1, 12)  # Data
    worksheet_risultati.set_column(2, 3, 25)  # Squadre
    worksheet_risultati.set_column(4, 7, 15)  # Punteggi e Mete
    worksheet_risultati.set_column(8, 8, 20)  # Vincitore
    worksheet_risultati.set_column(9, 9, 20)  # Arbitro
    
    # Imposta la larghezza delle colonne per le statistiche
    worksheet_stats.set_column(0, 4, 15)
    
    # Aggiungi un titolo al foglio dei risultati
    title_format = workbook.add_format({
        'bold': True,
        'font_size': 16,
        'align': 'center',
        'valign': 'vcenter'
    })
    worksheet_risultati.merge_range(0, 0, 0, 9, titolo, title_format)
    
    # Scrivi le intestazioni
    for col_num, column in enumerate(columns):
        worksheet_risultati.write(1, col_num, column, header_format)
    
    # Scrivi i dati
    for row_num, row_data in enumerate(dati):
        for col_num, column in enumerate(columns):
            worksheet_risultati.write(row_num + 2, col_num, row_data.get(column, ""))
    
    # Scrivi le statistiche
    stats_columns = ["Totale Partite", "Totale Punti", "Media Punti", "Totale Mete", "Media Mete"]
    stats_values = [totale_partite, totale_punti, media_punti, totale_mete, media_mete]
    
    # Scrivi le intestazioni delle statistiche
    for col_num, column in enumerate(stats_columns):
        worksheet_stats.write(0, col_num, column, header_format)
    
    # Scrivi i valori delle statistiche
    for col_num, value in enumerate(stats_values):
        worksheet_stats.write(1, col_num, value)
    
    # Chiudi il workbook
    workbook.close()
    
    # Riporta il puntatore all'inizio del buffer
    output.seek(0)
    
    return output

def genera_pdf_riepilogo_weekend(risultati_weekend, inizio_weekend_str, fine_weekend_str):
    """
    Genera un file PDF con il riepilogo delle partite del weekend.
    
    Args:
        risultati_weekend: Lista dei risultati delle partite del weekend
        inizio_weekend_str: Data di inizio del weekend in formato stringa
        fine_weekend_str: Data di fine del weekend in formato stringa
        
    Returns:
        BytesIO: Buffer contenente il file PDF
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
    except ImportError:
        # Se reportlab non è installato, fallback a Excel
        print("Reportlab non installato. Generazione PDF non disponibile. Fallback a Excel.")
        return genera_excel_riepilogo_weekend(risultati_weekend, inizio_weekend_str, fine_weekend_str)
    
    # Converti le date in oggetti datetime
    inizio_weekend = datetime.strptime(inizio_weekend_str, "%d/%m/%Y")
    fine_weekend = datetime.strptime(fine_weekend_str, "%d/%m/%Y")
    
    # Crea un titolo per il file
    titolo = f"Riepilogo Weekend {inizio_weekend.strftime('%d')} - {fine_weekend.strftime('%d %B %Y')}"
    
    # Crea un buffer in memoria per il file PDF
    buffer = BytesIO()
    
    # Crea il documento PDF
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=1*cm, leftMargin=1*cm, topMargin=1*cm, bottomMargin=1*cm)
    
    # Stili per il documento
    styles = getSampleStyleSheet()
    title_style = styles['Title']
    heading_style = styles['Heading2']
    normal_style = styles['Normal']
    
    # Crea una lista di elementi da aggiungere al documento
    elements = []
    
    # Aggiungi il titolo
    elements.append(Paragraph(titolo, title_style))
    elements.append(Spacer(1, 0.5*cm))
    
    # Prepara i dati per la tabella
    dati = []
    
    # Intestazioni della tabella
    headers = ["Categoria", "Data", "Squadra Casa", "Squadra Ospite", "Punteggio", "Mete", "Vincitore"]
    dati.append(headers)
    
    # Raggruppa i risultati per categoria
    risultati_per_categoria = {}
    for r in risultati_weekend:
        categoria = r.get('categoria', 'Altra categoria')
        genere = r.get('genere', '')
        categoria_completa = f"{categoria} {genere}".strip()
        
        if categoria_completa not in risultati_per_categoria:
            risultati_per_categoria[categoria_completa] = []
        
        risultati_per_categoria[categoria_completa].append(r)
    
    # Aggiungi i dati alla tabella, categoria per categoria
    for categoria, partite in sorted(risultati_per_categoria.items()):
        # Aggiungi un'intestazione per la categoria
        elements.append(Paragraph(categoria, heading_style))
        elements.append(Spacer(1, 0.3*cm))
        
        # Tabella per questa categoria
        categoria_dati = [headers]
        
        for r in partite:
            tipo_partita = r.get('tipo_partita', 'normale')
            data_partita = r.get('data_partita', '')
            
            if tipo_partita == 'triangolare':
                # Partita 1: Squadra1 vs Squadra2
                squadra1 = r.get('squadra1', '')
                squadra2 = r.get('squadra2', '')
                punteggio1 = int(r.get('partita1_punteggio1', 0))
                punteggio2 = int(r.get('partita1_punteggio2', 0))
                mete1 = int(r.get('partita1_mete1', 0))
                mete2 = int(r.get('partita1_mete2', 0))
                
                # Determina il vincitore
                if punteggio1 > punteggio2:
                    vincitore = squadra1
                elif punteggio2 > punteggio1:
                    vincitore = squadra2
                else:
                    vincitore = "Pareggio"
                
                # Aggiungi i dati alla tabella
                categoria_dati.append([
                    "Triangolare 1",
                    data_partita,
                    squadra1,
                    squadra2,
                    f"{punteggio1} - {punteggio2}",
                    f"{mete1} - {mete2}",
                    vincitore
                ])
                
                # Partita 2: Squadra1 vs Squadra3
                squadra1 = r.get('squadra1', '')
                squadra3 = r.get('squadra3', '')
                punteggio1 = int(r.get('partita2_punteggio1', 0))
                punteggio2 = int(r.get('partita2_punteggio2', 0))
                mete1 = int(r.get('partita2_mete1', 0))
                mete2 = int(r.get('partita2_mete2', 0))
                
                # Determina il vincitore
                if punteggio1 > punteggio2:
                    vincitore = squadra1
                elif punteggio2 > punteggio1:
                    vincitore = squadra3
                else:
                    vincitore = "Pareggio"
                
                # Aggiungi i dati alla tabella
                categoria_dati.append([
                    "Triangolare 2",
                    data_partita,
                    squadra1,
                    squadra3,
                    f"{punteggio1} - {punteggio2}",
                    f"{mete1} - {mete2}",
                    vincitore
                ])
                
                # Partita 3: Squadra2 vs Squadra3
                squadra2 = r.get('squadra2', '')
                squadra3 = r.get('squadra3', '')
                punteggio1 = int(r.get('partita3_punteggio1', 0))
                punteggio2 = int(r.get('partita3_punteggio2', 0))
                mete1 = int(r.get('partita3_mete1', 0))
                mete2 = int(r.get('partita3_mete2', 0))
                
                # Determina il vincitore
                if punteggio1 > punteggio2:
                    vincitore = squadra2
                elif punteggio2 > punteggio1:
                    vincitore = squadra3
                else:
                    vincitore = "Pareggio"
                
                # Aggiungi i dati alla tabella
                categoria_dati.append([
                    "Triangolare 3",
                    data_partita,
                    squadra2,
                    squadra3,
                    f"{punteggio1} - {punteggio2}",
                    f"{mete1} - {mete2}",
                    vincitore
                ])
            else:
                # Partita normale
                squadra1 = r.get('squadra1', '')
                squadra2 = r.get('squadra2', '')
                punteggio1 = int(r.get('punteggio1', 0))
                punteggio2 = int(r.get('punteggio2', 0))
                mete1 = int(r.get('mete1', 0))
                mete2 = int(r.get('mete2', 0))
                
                # Determina il vincitore
                if punteggio1 > punteggio2:
                    vincitore = squadra1
                elif punteggio2 > punteggio1:
                    vincitore = squadra2
                else:
                    vincitore = "Pareggio"
                
                # Aggiungi i dati alla tabella
                categoria_dati.append([
                    "",
                    data_partita,
                    squadra1,
                    squadra2,
                    f"{punteggio1} - {punteggio2}",
                    f"{mete1} - {mete2}",
                    vincitore
                ])
        
        # Crea la tabella per questa categoria
        if len(categoria_dati) > 1:  # Se ci sono dati oltre all'intestazione
            table = Table(categoria_dati[1:], colWidths=[2*cm, 2.5*cm, 4*cm, 4*cm, 2*cm, 2*cm, 3.5*cm])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            elements.append(table)
            elements.append(Spacer(1, 0.5*cm))
    
    # Calcola le statistiche
    totale_partite = len(risultati_weekend)
    totale_punti = sum(int(r.get('punteggio1', 0)) + int(r.get('punteggio2', 0)) for r in risultati_weekend)
    totale_mete = sum(int(r.get('mete1', 0)) + int(r.get('mete2', 0)) for r in risultati_weekend)
    media_punti = round(totale_punti / totale_partite, 1) if totale_partite > 0 else 0
    media_mete = round(totale_mete / totale_partite, 1) if totale_partite > 0 else 0
    
    # Aggiungi le statistiche
    elements.append(Paragraph("Statistiche", heading_style))
    elements.append(Spacer(1, 0.3*cm))
    
    stats_data = [
        ["Totale Partite", "Totale Punti", "Media Punti", "Totale Mete", "Media Mete"],
        [str(totale_partite), str(totale_punti), str(media_punti), str(totale_mete), str(media_mete)]
    ]
    
    stats_table = Table(stats_data, colWidths=[3*cm, 3*cm, 3*cm, 3*cm, 3*cm])
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    
    elements.append(stats_table)
    
    # Aggiungi un disclaimer
    elements.append(Spacer(1, 1*cm))
    disclaimer_style = ParagraphStyle(
        'Disclaimer',
        parent=normal_style,
        fontSize=8,
        textColor=colors.gray
    )
    disclaimer = "Tutti i risultati sono in attesa di omologazione ufficiale da parte del Giudice Sportivo"
    elements.append(Paragraph(disclaimer, disclaimer_style))
    
    # Costruisci il documento
    doc.build(elements)
    
    # Riporta il puntatore all'inizio del buffer
    buffer.seek(0)
    
    return buffer