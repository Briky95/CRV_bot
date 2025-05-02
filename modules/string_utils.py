#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
from difflib import SequenceMatcher

def similarity_ratio(a, b):
    """
    Calcola il rapporto di somiglianza tra due stringhe.
    Restituisce un valore tra 0 e 1, dove 1 indica stringhe identiche.
    """
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def normalize_team_name(name):
    """
    Normalizza il nome di una squadra rimuovendo prefissi comuni, suffissi e parole non significative.
    """
    # Converti in minuscolo
    name = name.lower()
    
    # Rimuovi prefissi comuni
    prefixes = ["asd ", "a.s.d. ", "a.s.d ", "asd. ", "rugby ", "r. "]
    for prefix in prefixes:
        if name.startswith(prefix):
            name = name[len(prefix):]
    
    # Rimuovi suffissi comuni
    suffixes = [" rugby", " asd", " a.s.d.", " a.s.d", " r."]
    for suffix in suffixes:
        if name.endswith(suffix):
            name = name[:-len(suffix)]
    
    # Rimuovi caratteri non alfanumerici e spazi multipli
    name = re.sub(r'[^\w\s]', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip()
    
    return name

def find_similar_teams(team_name, team_list, threshold=0.8):
    """
    Trova squadre con nomi simili nella lista.
    
    Args:
        team_name (str): Nome della squadra da confrontare
        team_list (list): Lista di nomi di squadre
        threshold (float): Soglia di somiglianza (0-1)
        
    Returns:
        list: Lista di tuple (nome_squadra, somiglianza) ordinate per somiglianza decrescente
    """
    normalized_name = normalize_team_name(team_name)
    similar_teams = []
    
    for team in team_list:
        if team == team_name:  # Salta la squadra stessa
            continue
            
        normalized_team = normalize_team_name(team)
        similarity = similarity_ratio(normalized_name, normalized_team)
        
        if similarity >= threshold:
            similar_teams.append((team, similarity))
    
    # Ordina per somiglianza decrescente
    return sorted(similar_teams, key=lambda x: x[1], reverse=True)