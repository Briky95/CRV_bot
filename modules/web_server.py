#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import logging
import time
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime

# Importa il monitor del bot
from modules.monitor import bot_monitor

# Configurazione logging
logger = logging.getLogger(__name__)

# Configurazione semplificata senza autenticazione
# La dashboard è accessibile direttamente senza token

# Tempo di cache per le risposte (in secondi)
CACHE_TTL = 5
_last_health_data = None
_last_health_time = 0

class WebRequestHandler(BaseHTTPRequestHandler):
    """
    Handler per le richieste web che gestisce la dashboard di monitoraggio.
    """
    
    def do_GET(self):
        """Gestisce le richieste GET."""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        query = parse_qs(parsed_path.query)
        
        # Routing delle richieste
        if path == '/':
            self._serve_home_page()
        elif path == '/health':
            self._serve_health_status()
        elif path == '/admin/monitor' or path == '/monitor':
            self._serve_admin_monitor()
        elif path == '/admin/api/health' or path == '/api/health':
            self._serve_health_json()
        elif path == '/admin/api/stats' or path == '/api/stats':
            self._serve_stats_json()
        elif path.startswith('/static/'):
            self._serve_static_file(path[8:])  # Rimuove '/static/' dal percorso
        else:
            self._send_not_found()
    
    # I metodi di autenticazione sono stati rimossi per semplificare l'accesso
    # La dashboard è ora accessibile direttamente senza token
    
    def _send_not_found(self):
        """Invia una risposta 404 Not Found."""
        self.send_response(404)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b'<html><head><title>Pagina non trovata</title></head>')
        self.wfile.write(b'<body><h1>404 - Pagina non trovata</h1>')
        self.wfile.write(b'<p>La pagina richiesta non esiste.</p>')
        self.wfile.write(b'<p><a href="/">Torna alla home</a></p>')
        self.wfile.write(b'</body></html>')
    
    def _serve_home_page(self):
        """Serve la pagina home."""
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>CRV Rugby Bot</title>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    margin: 0;
                    padding: 20px;
                    color: #333;
                    max-width: 800px;
                    margin: 0 auto;
                }}
                h1 {{
                    color: #1a5276;
                    border-bottom: 2px solid #1a5276;
                    padding-bottom: 10px;
                }}
                .status {{
                    background-color: #e8f5e9;
                    border-left: 5px solid #4caf50;
                    padding: 15px;
                    margin: 20px 0;
                    border-radius: 4px;
                }}
                .info {{
                    background-color: #e3f2fd;
                    border-left: 5px solid #2196f3;
                    padding: 15px;
                    margin: 20px 0;
                    border-radius: 4px;
                }}
                a {{
                    color: #1a5276;
                    text-decoration: none;
                }}
                a:hover {{
                    text-decoration: underline;
                }}
            </style>
        </head>
        <body>
            <h1>🏉 CRV Rugby Bot</h1>
            
            <div class="status">
                <h2>Stato del Bot</h2>
                <p>✅ Il bot è attivo e funzionante.</p>
                <p>Ultimo aggiornamento: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</p>
            </div>
            
            <div class="info">
                <h2>Informazioni</h2>
                <p>Questo bot permette di inserire e visualizzare i risultati delle partite di rugby del Comitato Regionale Veneto.</p>
                <p>Per utilizzare il bot, cercalo su Telegram: <a href="https://t.me/CRV_Rugby_Bot">@CRV_Rugby_Bot</a></p>
                <p>I risultati vengono pubblicati sul canale: <a href="https://t.me/CRV_Rugby_Risultati_Partite">@CRV_Rugby_Risultati_Partite</a></p>
            </div>
            
            <div style="margin-top: 20px;">
                <h2>Dashboard</h2>
                <ul>
                    <li><a href="/health">Stato di salute base</a></li>
                    <li><a href="/monitor">Dashboard di monitoraggio completa</a></li>
                </ul>
            </div>
        </body>
        </html>
        """
        
        self.wfile.write(html.encode())
    
    def _serve_health_status(self):
        """Serve una pagina con lo stato di salute base del bot."""
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        
        # Ottieni i dati di salute di base
        health = self._get_basic_health()
        
        # Determina il colore in base allo stato
        status_color = {
            'healthy': '#4caf50',  # Verde
            'degraded': '#ff9800',  # Arancione
            'warning': '#ff9800',   # Arancione
            'critical': '#f44336'   # Rosso
        }.get(health['status'], '#4caf50')
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Stato di Salute - CRV Rugby Bot</title>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    margin: 0;
                    padding: 20px;
                    color: #333;
                    max-width: 800px;
                    margin: 0 auto;
                }}
                h1 {{
                    color: #1a5276;
                    border-bottom: 2px solid #1a5276;
                    padding-bottom: 10px;
                }}
                .status-card {{
                    background-color: #f9f9f9;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    padding: 20px;
                    margin: 20px 0;
                }}
                .status-header {{
                    display: flex;
                    align-items: center;
                    margin-bottom: 15px;
                }}
                .status-indicator {{
                    width: 20px;
                    height: 20px;
                    border-radius: 50%;
                    background-color: {status_color};
                    margin-right: 10px;
                }}
                .status-title {{
                    font-size: 1.2em;
                    font-weight: bold;
                    margin: 0;
                }}
                .status-details {{
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 15px;
                }}
                .status-item {{
                    background-color: #fff;
                    border-radius: 4px;
                    padding: 10px;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
                }}
                .status-item h3 {{
                    margin-top: 0;
                    font-size: 1em;
                    color: #666;
                }}
                .status-item p {{
                    margin: 0;
                    font-size: 1.2em;
                    font-weight: bold;
                }}
                a {{
                    color: #1a5276;
                    text-decoration: none;
                }}
                a:hover {{
                    text-decoration: underline;
                }}
                .footer {{
                    margin-top: 30px;
                    text-align: center;
                    font-size: 0.9em;
                    color: #666;
                }}
            </style>
        </head>
        <body>
            <h1>🏉 Stato di Salute - CRV Rugby Bot</h1>
            
            <div class="status-card">
                <div class="status-header">
                    <div class="status-indicator"></div>
                    <h2 class="status-title">Stato: {health['status'].upper()}</h2>
                </div>
                
                <div class="status-details">
                    <div class="status-item">
                        <h3>Uptime</h3>
                        <p>{health['uptime']}</p>
                    </div>
                    <div class="status-item">
                        <h3>Ultimo aggiornamento</h3>
                        <p>{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</p>
                    </div>
                    <div class="status-item">
                        <h3>Utenti attivi</h3>
                        <p>{health['active_users']}</p>
                    </div>
                    <div class="status-item">
                        <h3>Comandi processati</h3>
                        <p>{health['commands_processed']}</p>
                    </div>
                    <div class="status-item">
                        <h3>CPU</h3>
                        <p>{health['system']['cpu_percent']}</p>
                    </div>
                    <div class="status-item">
                        <h3>Memoria</h3>
                        <p>{health['system']['memory_percent']}</p>
                    </div>
                </div>
            </div>
            
            <p><a href="/">Torna alla home</a></p>
            
            <div class="footer">
                <p>CRV Rugby Bot - Versione 1.0</p>
                <p>© {datetime.now().year} Comitato Regionale Veneto Rugby</p>
            </div>
        </body>
        </html>
        """
        
        self.wfile.write(html.encode())
    
    def _serve_admin_monitor(self):
        """Serve la dashboard di monitoraggio avanzata per gli admin."""
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Dashboard di Monitoraggio - CRV Rugby Bot</title>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    margin: 0;
                    padding: 0;
                    color: #333;
                    background-color: #f5f5f5;
                }
                .container {
                    max-width: 1200px;
                    margin: 0 auto;
                    padding: 20px;
                }
                header {
                    background-color: #1a5276;
                    color: white;
                    padding: 15px 20px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }
                h1 {
                    margin: 0;
                    font-size: 1.8em;
                }
                .dashboard {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                    gap: 20px;
                    margin-top: 20px;
                }
                .card {
                    background-color: white;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    padding: 20px;
                    overflow: hidden;
                }
                .card h2 {
                    margin-top: 0;
                    font-size: 1.3em;
                    color: #1a5276;
                    border-bottom: 1px solid #eee;
                    padding-bottom: 10px;
                }
                .status-indicator {
                    display: inline-block;
                    width: 12px;
                    height: 12px;
                    border-radius: 50%;
                    margin-right: 5px;
                }
                .healthy { background-color: #4caf50; }
                .degraded { background-color: #ff9800; }
                .warning { background-color: #ff9800; }
                .critical { background-color: #f44336; }
                
                .stat-grid {
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 10px;
                }
                .stat-item {
                    padding: 10px;
                    background-color: #f9f9f9;
                    border-radius: 4px;
                }
                .stat-item h3 {
                    margin: 0;
                    font-size: 0.9em;
                    color: #666;
                }
                .stat-item p {
                    margin: 5px 0 0 0;
                    font-size: 1.2em;
                    font-weight: bold;
                }
                
                .progress-bar {
                    height: 8px;
                    background-color: #e0e0e0;
                    border-radius: 4px;
                    margin-top: 5px;
                    overflow: hidden;
                }
                .progress-fill {
                    height: 100%;
                    background-color: #2196f3;
                }
                
                .error-list {
                    max-height: 200px;
                    overflow-y: auto;
                }
                .error-item {
                    padding: 10px;
                    border-bottom: 1px solid #eee;
                    font-size: 0.9em;
                }
                .error-item:last-child {
                    border-bottom: none;
                }
                .error-time {
                    color: #666;
                    font-size: 0.8em;
                }
                .error-type {
                    font-weight: bold;
                    color: #f44336;
                }
                
                .command-list {
                    max-height: 200px;
                    overflow-y: auto;
                }
                .command-item {
                    padding: 8px;
                    border-bottom: 1px solid #eee;
                    font-size: 0.9em;
                    display: flex;
                    justify-content: space-between;
                }
                .command-item:last-child {
                    border-bottom: none;
                }
                
                .refresh-button {
                    background-color: #1a5276;
                    color: white;
                    border: none;
                    padding: 10px 15px;
                    border-radius: 4px;
                    cursor: pointer;
                    font-size: 1em;
                    margin-top: 20px;
                }
                .refresh-button:hover {
                    background-color: #154360;
                }
                
                .footer {
                    margin-top: 30px;
                    text-align: center;
                    font-size: 0.9em;
                    color: #666;
                    padding: 20px;
                    border-top: 1px solid #eee;
                }
                
                /* Stili per i grafici */
                .chart-container {
                    height: 200px;
                    margin-top: 15px;
                }
                
                /* Responsive */
                @media (max-width: 768px) {
                    .dashboard {
                        grid-template-columns: 1fr;
                    }
                }
            </style>
            <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        </head>
        <body>
            <header>
                <h1>🏉 Dashboard di Monitoraggio - CRV Rugby Bot</h1>
            </header>
            
            <div class="container">
                <div id="status-overview" class="card">
                    <h2>Panoramica</h2>
                    <div id="status-details"></div>
                </div>
                
                <div class="dashboard">
                    <div class="card">
                        <h2>Risorse di Sistema</h2>
                        <div class="stat-grid" id="system-resources"></div>
                        <div class="chart-container">
                            <canvas id="resourcesChart"></canvas>
                        </div>
                    </div>
                    
                    <div class="card">
                        <h2>Statistiche Utenti</h2>
                        <div class="stat-grid" id="user-stats"></div>
                        <div class="chart-container">
                            <canvas id="usersChart"></canvas>
                        </div>
                    </div>
                    
                    <div class="card">
                        <h2>Comandi Più Utilizzati</h2>
                        <div id="top-commands"></div>
                        <div class="chart-container">
                            <canvas id="commandsChart"></canvas>
                        </div>
                    </div>
                    
                    <div class="card">
                        <h2>Errori Recenti</h2>
                        <div id="recent-errors" class="error-list"></div>
                    </div>
                    
                    <div class="card">
                        <h2>Attività Recenti</h2>
                        <div id="recent-commands" class="command-list"></div>
                    </div>
                </div>
                
                <button id="refresh-button" class="refresh-button">Aggiorna Dati</button>
                
                <div class="footer">
                    <p>CRV Rugby Bot - Versione 1.0</p>
                    <p>© 2024 Comitato Regionale Veneto Rugby</p>
                </div>
            </div>
            
            <script>
                // Funzione per ottenere i dati di salute dal server
                async function fetchHealthData() {
                    try {
                        const response = await fetch('/admin/api/health' + window.location.search);
                        if (!response.ok) {
                            throw new Error('Errore nel caricamento dei dati');
                        }
                        return await response.json();
                    } catch (error) {
                        console.error('Errore:', error);
                        alert('Errore nel caricamento dei dati: ' + error.message);
                    }
                }
                
                // Funzione per aggiornare la dashboard
                async function updateDashboard() {
                    const data = await fetchHealthData();
                    if (!data) return;
                    
                    // Aggiorna panoramica
                    updateStatusOverview(data);
                    
                    // Aggiorna risorse di sistema
                    updateSystemResources(data);
                    
                    // Aggiorna statistiche utenti
                    updateUserStats(data);
                    
                    // Aggiorna comandi più utilizzati
                    updateTopCommands(data);
                    
                    // Aggiorna errori recenti
                    updateRecentErrors(data);
                    
                    // Aggiorna attività recenti
                    updateRecentCommands(data);
                    
                    // Aggiorna grafici
                    updateCharts(data);
                }
                
                function updateStatusOverview(data) {
                    const statusDetails = document.getElementById('status-details');
                    
                    const statusClass = {
                        'healthy': 'healthy',
                        'degraded': 'degraded',
                        'warning': 'warning',
                        'critical': 'critical'
                    }[data.status] || 'healthy';
                    
                    statusDetails.innerHTML = `
                        <div style="display: flex; align-items: center; margin-bottom: 15px;">
                            <span class="status-indicator ${statusClass}"></span>
                            <span style="font-size: 1.2em; font-weight: bold;">Stato: ${data.status.toUpperCase()}</span>
                        </div>
                        <div class="stat-grid">
                            <div class="stat-item">
                                <h3>Uptime</h3>
                                <p>${data.uptime}</p>
                            </div>
                            <div class="stat-item">
                                <h3>Avviato il</h3>
                                <p>${data.start_time}</p>
                            </div>
                            <div class="stat-item">
                                <h3>Comandi Processati</h3>
                                <p>${data.commands_processed}</p>
                            </div>
                            <div class="stat-item">
                                <h3>Errori Totali</h3>
                                <p>${data.errors}</p>
                            </div>
                        </div>
                    `;
                }
                
                function updateSystemResources(data) {
                    const systemResources = document.getElementById('system-resources');
                    
                    systemResources.innerHTML = `
                        <div class="stat-item">
                            <h3>CPU</h3>
                            <p>${data.system.cpu_percent}</p>
                            <div class="progress-bar">
                                <div class="progress-fill" style="width: ${data.system.cpu_percent}"></div>
                            </div>
                        </div>
                        <div class="stat-item">
                            <h3>Memoria</h3>
                            <p>${data.system.memory_percent}</p>
                            <div class="progress-bar">
                                <div class="progress-fill" style="width: ${data.system.memory_percent}"></div>
                            </div>
                        </div>
                        <div class="stat-item">
                            <h3>Disco</h3>
                            <p>${data.system.disk_percent}</p>
                            <div class="progress-bar">
                                <div class="progress-fill" style="width: ${data.system.disk_percent}"></div>
                            </div>
                        </div>
                        <div class="stat-item">
                            <h3>Tempo Medio Risposta</h3>
                            <p>${data.avg_response_time}</p>
                        </div>
                    `;
                }
                
                function updateUserStats(data) {
                    const userStats = document.getElementById('user-stats');
                    
                    userStats.innerHTML = `
                        <div class="stat-item">
                            <h3>Utenti Attivi (Totale)</h3>
                            <p>${data.active_users}</p>
                        </div>
                        <div class="stat-item">
                            <h3>Utenti Attivi (24h)</h3>
                            <p>${data.active_users_24h}</p>
                        </div>
                        <div class="stat-item">
                            <h3>Admin Attivi</h3>
                            <p>${data.active_admins}</p>
                        </div>
                        <div class="stat-item">
                            <h3>Piattaforma</h3>
                            <p>${data.system.python_version}</p>
                        </div>
                    `;
                }
                
                function updateTopCommands(data) {
                    const topCommands = document.getElementById('top-commands');
                    
                    if (!data.top_commands || data.top_commands.length === 0) {
                        topCommands.innerHTML = '<p>Nessun comando registrato</p>';
                        return;
                    }
                    
                    let html = '<div class="command-list">';
                    
                    data.top_commands.forEach(([command, count]) => {
                        html += `
                            <div class="command-item">
                                <span>${command}</span>
                                <span><strong>${count}</strong></span>
                            </div>
                        `;
                    });
                    
                    html += '</div>';
                    topCommands.innerHTML = html;
                }
                
                function updateRecentErrors(data) {
                    const recentErrors = document.getElementById('recent-errors');
                    
                    if (!data.recent_errors || data.recent_errors.length === 0) {
                        recentErrors.innerHTML = '<p>Nessun errore recente</p>';
                        return;
                    }
                    
                    let html = '';
                    
                    data.recent_errors.forEach(error => {
                        html += `
                            <div class="error-item">
                                <div class="error-time">${error.timestamp}</div>
                                <div class="error-type">${error.error_type}</div>
                                <div>${error.error_message}</div>
                            </div>
                        `;
                    });
                    
                    recentErrors.innerHTML = html;
                }
                
                function updateRecentCommands(data) {
                    const recentCommands = document.getElementById('recent-commands');
                    
                    if (!data.command_history || data.command_history.length === 0) {
                        recentCommands.innerHTML = '<p>Nessun comando recente</p>';
                        return;
                    }
                    
                    let html = '';
                    
                    data.command_history.forEach(cmd => {
                        html += `
                            <div class="command-item">
                                <span>${cmd.timestamp} - ${cmd.user_name}</span>
                                <span><strong>${cmd.command}</strong></span>
                            </div>
                        `;
                    });
                    
                    recentCommands.innerHTML = html;
                }
                
                // Grafici
                let resourcesChart, usersChart, commandsChart;
                
                function updateCharts(data) {
                    // Grafico risorse
                    updateResourcesChart(data);
                    
                    // Grafico utenti
                    updateUsersChart(data);
                    
                    // Grafico comandi
                    updateCommandsChart(data);
                }
                
                function updateResourcesChart(data) {
                    const ctx = document.getElementById('resourcesChart').getContext('2d');
                    
                    if (resourcesChart) {
                        resourcesChart.destroy();
                    }
                    
                    resourcesChart = new Chart(ctx, {
                        type: 'bar',
                        data: {
                            labels: ['CPU', 'Memoria', 'Disco'],
                            datasets: [{
                                label: 'Utilizzo (%)',
                                data: [
                                    parseFloat(data.system.cpu_percent),
                                    parseFloat(data.system.memory_percent),
                                    parseFloat(data.system.disk_percent)
                                ],
                                backgroundColor: [
                                    'rgba(54, 162, 235, 0.5)',
                                    'rgba(255, 99, 132, 0.5)',
                                    'rgba(75, 192, 192, 0.5)'
                                ],
                                borderColor: [
                                    'rgba(54, 162, 235, 1)',
                                    'rgba(255, 99, 132, 1)',
                                    'rgba(75, 192, 192, 1)'
                                ],
                                borderWidth: 1
                            }]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            scales: {
                                y: {
                                    beginAtZero: true,
                                    max: 100
                                }
                            }
                        }
                    });
                }
                
                function updateUsersChart(data) {
                    const ctx = document.getElementById('usersChart').getContext('2d');
                    
                    if (usersChart) {
                        usersChart.destroy();
                    }
                    
                    usersChart = new Chart(ctx, {
                        type: 'pie',
                        data: {
                            labels: ['Utenti Attivi (24h)', 'Admin Attivi'],
                            datasets: [{
                                data: [
                                    data.active_users_24h - data.active_admins,
                                    data.active_admins
                                ],
                                backgroundColor: [
                                    'rgba(54, 162, 235, 0.5)',
                                    'rgba(255, 99, 132, 0.5)'
                                ],
                                borderColor: [
                                    'rgba(54, 162, 235, 1)',
                                    'rgba(255, 99, 132, 1)'
                                ],
                                borderWidth: 1
                            }]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false
                        }
                    });
                }
                
                function updateCommandsChart(data) {
                    const ctx = document.getElementById('commandsChart').getContext('2d');
                    
                    if (!data.top_commands || data.top_commands.length === 0) {
                        return;
                    }
                    
                    if (commandsChart) {
                        commandsChart.destroy();
                    }
                    
                    const labels = data.top_commands.map(item => item[0]);
                    const values = data.top_commands.map(item => item[1]);
                    
                    commandsChart = new Chart(ctx, {
                        type: 'bar',
                        data: {
                            labels: labels,
                            datasets: [{
                                label: 'Utilizzo',
                                data: values,
                                backgroundColor: 'rgba(75, 192, 192, 0.5)',
                                borderColor: 'rgba(75, 192, 192, 1)',
                                borderWidth: 1
                            }]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            scales: {
                                y: {
                                    beginAtZero: true
                                }
                            }
                        }
                    });
                }
                
                // Inizializza la dashboard
                document.addEventListener('DOMContentLoaded', () => {
                    updateDashboard();
                    
                    // Aggiorna ogni 30 secondi
                    setInterval(updateDashboard, 30000);
                    
                    // Pulsante di aggiornamento manuale
                    document.getElementById('refresh-button').addEventListener('click', updateDashboard);
                });
            </script>
        </body>
        </html>
        """
        
        self.wfile.write(html.encode())
    
    def _serve_health_json(self):
        """Serve i dati di salute in formato JSON."""
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        
        # Ottieni i dati di salute completi
        health_data = bot_monitor.get_health_status()
        
        # Aggiungi la cronologia dei comandi
        health_data['command_history'] = list(bot_monitor.command_history)
        
        # Converti in JSON
        json_data = json.dumps(health_data, default=str)
        self.wfile.write(json_data.encode())
    
    def _serve_stats_json(self):
        """Serve le statistiche in formato JSON."""
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        
        # Qui potresti aggiungere statistiche aggiuntive specifiche
        stats = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'command_counts': bot_monitor.command_counts,
            'error_count': bot_monitor.metrics['errors'],
            'active_users': len(bot_monitor.metrics['active_users']),
            'active_users_24h': len(bot_monitor.metrics['active_users_24h'])
        }
        
        json_data = json.dumps(stats, default=str)
        self.wfile.write(json_data.encode())
    
    def _serve_static_file(self, path):
        """Serve un file statico."""
        # Per sicurezza, limitiamo i file che possono essere serviti
        # In un'implementazione reale, usare un sistema più robusto
        allowed_extensions = ['.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.svg']
        
        # Verifica che l'estensione sia consentita
        ext = os.path.splitext(path)[1].lower()
        if ext not in allowed_extensions:
            self._send_not_found()
            return
        
        # Costruisci il percorso completo
        static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static')
        file_path = os.path.join(static_dir, path)
        
        # Verifica che il file esista
        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            self._send_not_found()
            return
        
        # Determina il tipo MIME
        content_type = {
            '.css': 'text/css',
            '.js': 'application/javascript',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.svg': 'image/svg+xml'
        }.get(ext, 'application/octet-stream')
        
        # Serve il file
        try:
            with open(file_path, 'rb') as f:
                self.send_response(200)
                self.send_header('Content-type', content_type)
                self.end_headers()
                self.wfile.write(f.read())
        except Exception as e:
            logger.error(f"Errore nel servire il file statico {path}: {e}")
            self._send_not_found()
    
    def _get_basic_health(self):
        """
        Ottiene i dati di salute di base del bot.
        Usa la cache per evitare troppe chiamate.
        
        Returns:
            dict: Dati di salute di base
        """
        global _last_health_data, _last_health_time
        
        current_time = time.time()
        
        # Se i dati in cache sono ancora validi, usali
        if _last_health_data and (current_time - _last_health_time) < CACHE_TTL:
            return _last_health_data
        
        # Altrimenti, ottieni nuovi dati
        _last_health_data = bot_monitor.get_health_status()
        _last_health_time = current_time
        
        return _last_health_data
    
    def log_message(self, format, *args):
        """Disabilita i log delle richieste HTTP per evitare spam nel log."""
        # Commenta questa riga per abilitare i log delle richieste HTTP
        return