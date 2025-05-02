#!/usr/bin/env python
# -*- coding: utf-8 -*-

import threading
import time
import logging
import asyncio
from datetime import datetime, timedelta

# Configura il logger
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class JobManager:
    """
    Gestore di job alternativo quando la job_queue di python-telegram-bot non è disponibile.
    Implementa funzionalità simili a run_once e run_daily.
    """
    
    def __init__(self):
        self.jobs = []
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
    
    def start(self):
        """Avvia il gestore di job in un thread separato."""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        logger.info("JobManager avviato")
    
    def stop(self):
        """Ferma il gestore di job."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
            self.thread = None
        logger.info("JobManager fermato")
    
    def _run(self):
        """Loop principale che controlla e esegue i job."""
        while self.running:
            now = datetime.now()
            
            with self.lock:
                # Copia la lista dei job per evitare modifiche durante l'iterazione
                jobs_to_check = self.jobs.copy()
            
            # Controlla quali job devono essere eseguiti
            jobs_to_run = []
            jobs_to_remove = []
            
            for job in jobs_to_check:
                if job["next_run"] <= now:
                    jobs_to_run.append(job)
                    
                    # Se è un job one-time, lo rimuoviamo
                    if job["type"] == "once":
                        jobs_to_remove.append(job)
                    # Se è un job daily, calcoliamo la prossima esecuzione
                    elif job["type"] == "daily":
                        # Calcola il prossimo giorno valido
                        next_day = now.date() + timedelta(days=1)
                        while next_day.weekday() not in job["days"]:
                            next_day += timedelta(days=1)
                        
                        # Imposta l'orario specificato
                        next_run = datetime.combine(next_day, job["time"])
                        job["next_run"] = next_run
            
            # Rimuovi i job completati
            with self.lock:
                for job in jobs_to_remove:
                    if job in self.jobs:
                        self.jobs.remove(job)
            
            # Esegui i job in thread separati
            for job in jobs_to_run:
                threading.Thread(
                    target=self._execute_job,
                    args=(job["callback"], job["data"]),
                    daemon=True
                ).start()
            
            # Dormi per un secondo prima di controllare di nuovo
            time.sleep(1)
    
    def _execute_job(self, callback, data):
        """Esegue un job in modo asincrono."""
        try:
            # Crea un nuovo event loop per questo thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Esegui la callback asincrona
            loop.run_until_complete(callback(data))
            loop.close()
        except Exception as e:
            logger.error(f"Errore nell'esecuzione del job: {e}")
    
    def run_once(self, callback, delay, data=None, name=None):
        """
        Pianifica un job da eseguire una sola volta dopo un certo ritardo.
        
        Args:
            callback: Funzione asincrona da chiamare
            delay: Ritardo in secondi
            data: Dati da passare alla callback
            name: Nome del job (opzionale)
        """
        next_run = datetime.now() + timedelta(seconds=delay)
        
        job = {
            "type": "once",
            "callback": callback,
            "next_run": next_run,
            "data": data,
            "name": name
        }
        
        with self.lock:
            self.jobs.append(job)
        
        logger.info(f"Job 'once' pianificato per {next_run}")
        return job
    
    def run_daily(self, callback, time, days, data=None, name=None):
        """
        Pianifica un job da eseguire ogni giorno a un orario specifico.
        
        Args:
            callback: Funzione asincrona da chiamare
            time: Orario del giorno (datetime.time)
            days: Lista di giorni della settimana (0-6, dove 0 è lunedì)
            data: Dati da passare alla callback
            name: Nome del job (opzionale)
        """
        # Calcola la prossima esecuzione
        now = datetime.now()
        today = now.date()
        
        # Converti days in una lista se è un singolo valore
        if not isinstance(days, list):
            days = [days]
        
        # Trova il prossimo giorno valido
        next_day = today
        while next_day.weekday() not in days or (next_day == today and now.time() >= time):
            next_day += timedelta(days=1)
        
        # Imposta l'orario specificato
        next_run = datetime.combine(next_day, time)
        
        job = {
            "type": "daily",
            "callback": callback,
            "next_run": next_run,
            "time": time,
            "days": days,
            "data": data,
            "name": name
        }
        
        with self.lock:
            self.jobs.append(job)
        
        logger.info(f"Job 'daily' pianificato per {next_run} e successivamente ogni giorno alle {time} nei giorni {days}")
        return job
    
    def get_jobs_by_name(self, name):
        """
        Restituisce tutti i job con un determinato nome.
        
        Args:
            name: Nome del job da cercare
            
        Returns:
            Lista di job con il nome specificato
        """
        with self.lock:
            return [job for job in self.jobs if job.get("name") == name]
    
    def remove_job(self, job):
        """
        Rimuove un job dalla lista.
        
        Args:
            job: Job da rimuovere
        """
        with self.lock:
            if job in self.jobs:
                self.jobs.remove(job)
                logger.info(f"Job rimosso: {job.get('name', 'unnamed')}")
                return True
        return False

# Istanza globale del JobManager
job_manager = JobManager()

# Avvia il JobManager all'importazione del modulo
job_manager.start()