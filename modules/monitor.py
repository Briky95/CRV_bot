#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
import os
import psutil
import platform
import logging
import json
from datetime import datetime, timedelta
from collections import deque

logger = logging.getLogger(__name__)

class BotMonitor:
    """
    Classe per il monitoraggio della salute e delle prestazioni del bot.
    Raccoglie metriche su utilizzo, prestazioni e risorse di sistema.
    """
    
    def __init__(self, max_history=100):
        """
        Inizializza il monitor del bot.
        
        Args:
            max_history (int): Numero massimo di eventi da mantenere nella cronologia
        """
        self.start_time = time.time()
        self.max_history = max_history
        
        # Metriche di base
        self.metrics = {
            'commands_processed': 0,
            'errors': 0,
            'active_users': set(),
            'active_users_24h': set(),
            'active_admins': set()
        }
        
        # Cronologia dei tempi di risposta (ultimi N comandi)
        self.response_times = deque(maxlen=max_history)
        
        # Cronologia degli errori (ultimi N errori)
        self.error_history = deque(maxlen=max_history)
        
        # Cronologia dei comandi (ultimi N comandi)
        self.command_history = deque(maxlen=max_history)
        
        # Contatori per tipo di comando
        self.command_counts = {}
        
        # Timestamp dell'ultimo controllo delle metriche
        self.last_metrics_check = time.time()
        
        # Metriche di sistema
        self.system_metrics = {
            'cpu_percent': 0,
            'memory_percent': 0,
            'disk_percent': 0
        }
        
        # Aggiorna le metriche di sistema all'avvio
        self._update_system_metrics()
        
        logger.info("BotMonitor inizializzato")
    
    def track_command(self, user_id, user_name, command, is_admin=False):
        """
        Traccia l'esecuzione di un comando.
        
        Args:
            user_id (int): ID dell'utente che ha eseguito il comando
            user_name (str): Nome dell'utente
            command (str): Comando eseguito
            is_admin (bool): Se l'utente è un amministratore
        """
        start_time = time.time()
        
        # Aggiorna le metriche di base
        self.metrics['commands_processed'] += 1
        self.metrics['active_users'].add(user_id)
        
        # Aggiorna gli utenti attivi nelle ultime 24 ore
        self.metrics['active_users_24h'].add(user_id)
        
        # Traccia gli admin attivi
        if is_admin:
            self.metrics['active_admins'].add(user_id)
        
        # Aggiorna i contatori per tipo di comando
        if command not in self.command_counts:
            self.command_counts[command] = 0
        self.command_counts[command] += 1
        
        # Aggiungi alla cronologia dei comandi
        self.command_history.append({
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'user_id': user_id,
            'user_name': user_name,
            'command': command,
            'is_admin': is_admin
        })
        
        return start_time
    
    def track_command_completion(self, start_time):
        """
        Traccia il completamento di un comando e il suo tempo di risposta.
        
        Args:
            start_time (float): Timestamp di inizio del comando
        """
        duration = time.time() - start_time
        self.response_times.append(duration)
    
    def track_error(self, error_type, error_message, user_id=None, command=None):
        """
        Traccia un errore verificatosi durante l'esecuzione del bot.
        
        Args:
            error_type (str): Tipo di errore
            error_message (str): Messaggio di errore
            user_id (int, optional): ID dell'utente che ha riscontrato l'errore
            command (str, optional): Comando che ha generato l'errore
        """
        self.metrics['errors'] += 1
        
        # Aggiungi alla cronologia degli errori
        self.error_history.append({
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'error_type': error_type,
            'error_message': str(error_message),
            'user_id': user_id,
            'command': command
        })
        
        # Log dell'errore
        logger.error(f"Bot error: {error_type} - {error_message} (User: {user_id}, Command: {command})")
    
    def _update_system_metrics(self):
        """Aggiorna le metriche di sistema (CPU, memoria, disco)."""
        try:
            # Aggiorna solo ogni 5 secondi per evitare sovraccarichi
            current_time = time.time()
            if current_time - self.last_metrics_check < 5:
                return
                
            self.last_metrics_check = current_time
            
            # Metriche CPU
            self.system_metrics['cpu_percent'] = psutil.cpu_percent(interval=0.1)
            
            # Metriche memoria
            memory = psutil.virtual_memory()
            self.system_metrics['memory_percent'] = memory.percent
            self.system_metrics['memory_used'] = self._format_bytes(memory.used)
            self.system_metrics['memory_total'] = self._format_bytes(memory.total)
            
            # Metriche disco
            disk = psutil.disk_usage('/')
            self.system_metrics['disk_percent'] = disk.percent
            self.system_metrics['disk_used'] = self._format_bytes(disk.used)
            self.system_metrics['disk_total'] = self._format_bytes(disk.total)
            
        except Exception as e:
            logger.error(f"Errore nell'aggiornamento delle metriche di sistema: {e}")
    
    def _format_bytes(self, bytes):
        """Formatta i byte in un formato leggibile (KB, MB, GB)."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes < 1024:
                return f"{bytes:.2f} {unit}"
            bytes /= 1024
        return f"{bytes:.2f} PB"
    
    def _clean_old_data(self):
        """Pulisce i dati degli utenti attivi più vecchi di 24 ore."""
        # Questa funzione verrebbe chiamata periodicamente per pulire i dati vecchi
        # Per ora è una semplificazione, in un'implementazione reale si terrebbe traccia
        # dei timestamp per ogni utente attivo
        pass
    
    def get_health_status(self):
        """
        Ottiene lo stato di salute completo del bot.
        
        Returns:
            dict: Dizionario con tutte le metriche di salute
        """
        # Aggiorna le metriche di sistema
        self._update_system_metrics()
        
        # Calcola l'uptime
        uptime_seconds = time.time() - self.start_time
        days, remainder = divmod(uptime_seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{int(days)}d {int(hours)}h {int(minutes)}m {int(seconds)}s"
        
        # Calcola il tempo medio di risposta
        avg_response_time = sum(self.response_times) / len(self.response_times) if self.response_times else 0
        
        # Determina lo stato di salute
        if self.system_metrics['cpu_percent'] > 90 or self.system_metrics['memory_percent'] > 90:
            health_status = "critical"
        elif self.system_metrics['cpu_percent'] > 70 or self.system_metrics['memory_percent'] > 70:
            health_status = "warning"
        elif self.metrics['errors'] > 10:
            health_status = "degraded"
        else:
            health_status = "healthy"
        
        # Comandi più utilizzati (top 5)
        top_commands = sorted(self.command_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Ultimi errori (top 5)
        recent_errors = list(self.error_history)[-5:] if self.error_history else []
        
        return {
            'status': health_status,
            'uptime': uptime_str,
            'uptime_seconds': uptime_seconds,
            'start_time': datetime.fromtimestamp(self.start_time).strftime('%Y-%m-%d %H:%M:%S'),
            'active_users': len(self.metrics['active_users']),
            'active_users_24h': len(self.metrics['active_users_24h']),
            'active_admins': len(self.metrics['active_admins']),
            'commands_processed': self.metrics['commands_processed'],
            'errors': self.metrics['errors'],
            'avg_response_time': f"{avg_response_time:.4f}s",
            'system': {
                'platform': platform.platform(),
                'python_version': platform.python_version(),
                'cpu_percent': f"{self.system_metrics['cpu_percent']}%",
                'memory_percent': f"{self.system_metrics['memory_percent']}%",
                'memory_used': self.system_metrics['memory_used'],
                'memory_total': self.system_metrics['memory_total'],
                'disk_percent': f"{self.system_metrics['disk_percent']}%",
                'disk_used': self.system_metrics['disk_used'],
                'disk_total': self.system_metrics['disk_total']
            },
            'top_commands': top_commands,
            'recent_errors': recent_errors
        }
    
    def format_health_message(self):
        """
        Formatta lo stato di salute in un messaggio leggibile per Telegram.
        
        Returns:
            str: Messaggio formattato in HTML
        """
        health = self.get_health_status()
        
        # Emoji per lo stato
        status_emoji = {
            'healthy': '✅',
            'degraded': '⚠️',
            'warning': '🟠',
            'critical': '🔴'
        }
        
        emoji = status_emoji.get(health['status'], '❓')
        
        message = f"<b>🤖 STATO DEL BOT {emoji}</b>\n\n"
        
        # Stato generale
        message += f"<b>Stato:</b> {emoji} {health['status'].upper()}\n"
        message += f"<b>Uptime:</b> {health['uptime']}\n"
        message += f"<b>Avviato il:</b> {health['start_time']}\n\n"
        
        # Statistiche utenti
        message += f"<b>👥 UTENTI</b>\n"
        message += f"• Utenti attivi (totale): <b>{health['active_users']}</b>\n"
        message += f"• Utenti attivi (24h): <b>{health['active_users_24h']}</b>\n"
        message += f"• Admin attivi: <b>{health['active_admins']}</b>\n\n"
        
        # Statistiche comandi
        message += f"<b>📊 COMANDI</b>\n"
        message += f"• Comandi processati: <b>{health['commands_processed']}</b>\n"
        message += f"• Tempo medio risposta: <b>{health['avg_response_time']}</b>\n"
        
        # Comandi più utilizzati
        if health['top_commands']:
            message += "\n<b>Comandi più utilizzati:</b>\n"
            for cmd, count in health['top_commands']:
                message += f"• {cmd}: <b>{count}</b>\n"
        
        # Statistiche errori
        message += f"\n<b>⚠️ ERRORI</b>\n"
        message += f"• Totale errori: <b>{health['errors']}</b>\n"
        
        # Ultimi errori
        if health['recent_errors']:
            message += "\n<b>Errori recenti:</b>\n"
            for error in health['recent_errors']:
                message += f"• {error['timestamp']} - {error['error_type']}: {error['error_message'][:50]}...\n"
        
        # Statistiche sistema
        message += f"\n<b>💻 SISTEMA</b>\n"
        message += f"• CPU: <b>{health['system']['cpu_percent']}</b>\n"
        message += f"• Memoria: <b>{health['system']['memory_percent']}</b> ({health['system']['memory_used']} / {health['system']['memory_total']})\n"
        message += f"• Disco: <b>{health['system']['disk_percent']}</b> ({health['system']['disk_used']} / {health['system']['disk_total']})\n"
        message += f"• Piattaforma: <b>{health['system']['platform']}</b>\n"
        message += f"• Python: <b>{health['system']['python_version']}</b>\n"
        
        return message

# Istanza globale del monitor
bot_monitor = BotMonitor()