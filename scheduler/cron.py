"""
Scheduler module - Cron-style scheduling for scrape jobs
"""
import time
import threading
from datetime import datetime, timedelta
import json
from pathlib import Path
import sys

class CronScheduler:
    """Simple cron-style scheduler for Reddit scraping jobs."""
    
    def __init__(self):
        self.jobs = []
        self.running = False
        self.thread = None
    
    def add_job(self, target, mode='full', limit=100, is_user=False, 
                interval_minutes=60, run_at_start=True):
        """
        Add a scheduled scraping job.
        
        Args:
            target: Subreddit or username
            mode: 'full', 'history', or 'monitor'
            limit: Post limit per run
            is_user: True if target is a user
            interval_minutes: Minutes between runs
            run_at_start: Run immediately when scheduler starts
        """
        job = {
            'id': len(self.jobs) + 1,
            'target': target,
            'mode': mode,
            'limit': limit,
            'is_user': is_user,
            'interval_minutes': interval_minutes,
            'run_at_start': run_at_start,
            'last_run': None,
            'next_run': datetime.now() if run_at_start else datetime.now() + timedelta(minutes=interval_minutes),
            'enabled': True,
            'run_count': 0
        }
        self.jobs.append(job)
        print(f"📅 Added job #{job['id']}: {'u/' if is_user else 'r/'}{target} every {interval_minutes}min")
        return job['id']
    
    def remove_job(self, job_id):
        """Remove a scheduled job."""
        self.jobs = [j for j in self.jobs if j['id'] != job_id]
        print(f"🗑️ Removed job #{job_id}")
    
    def disable_job(self, job_id):
        """Temporarily disable a job."""
        for job in self.jobs:
            if job['id'] == job_id:
                job['enabled'] = False
                print(f"⏸️ Disabled job #{job_id}")
    
    def enable_job(self, job_id):
        """Enable a disabled job."""
        for job in self.jobs:
            if job['id'] == job_id:
                job['enabled'] = True
                print(f"▶️ Enabled job #{job_id}")
    
    def list_jobs(self):
        """List all scheduled jobs."""
        print("\n📋 Scheduled Jobs:")
        print("-" * 60)
        for job in self.jobs:
            status = "✅" if job['enabled'] else "⏸️"
            prefix = "u/" if job['is_user'] else "r/"
            next_run = job['next_run'].strftime("%H:%M:%S") if job['next_run'] else "Never"
            print(f"{status} #{job['id']} | {prefix}{job['target']} | "
                  f"Every {job['interval_minutes']}min | Next: {next_run} | "
                  f"Runs: {job['run_count']}")
        print()
        return self.jobs
    
    def _run_job(self, job):
        """Execute a single job."""
        # Import here to avoid circular imports
        try:
            from main import run_full_history
            
            prefix = "u/" if job['is_user'] else "r/"
            print(f"\n🚀 Running scheduled job: {prefix}{job['target']}")
            
            run_full_history(
                job['target'],
                job['limit'],
                job['is_user'],
                download_media_flag=(job['mode'] == 'full'),
                scrape_comments_flag=(job['mode'] == 'full')
            )
            
            job['last_run'] = datetime.now()
            job['run_count'] += 1
            print(f"✅ Job completed: {prefix}{job['target']}")
            
        except Exception as e:
            print(f"❌ Job failed: {e}")
    
    def _scheduler_loop(self):
        """Main scheduler loop."""
        print("🔄 Scheduler started")
        
        while self.running:
            now = datetime.now()
            
            for job in self.jobs:
                if not job['enabled']:
                    continue
                
                if job['next_run'] and now >= job['next_run']:
                    self._run_job(job)
                    job['next_run'] = now + timedelta(minutes=job['interval_minutes'])
            
            # Check every 30 seconds
            time.sleep(30)
        
        print("🛑 Scheduler stopped")
    
    def start(self):
        """Start the scheduler in background."""
        if self.running:
            print("⚠️ Scheduler already running")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.thread.start()
        print("✅ Scheduler started in background")
    
    def stop(self):
        """Stop the scheduler."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        print("🛑 Scheduler stopped")
    
    def save_jobs(self, filepath='scheduler_jobs.json'):
        """Save jobs to file."""
        jobs_data = []
        for job in self.jobs:
            job_copy = job.copy()
            job_copy['last_run'] = job_copy['last_run'].isoformat() if job_copy['last_run'] else None
            job_copy['next_run'] = job_copy['next_run'].isoformat() if job_copy['next_run'] else None
            jobs_data.append(job_copy)
        
        with open(filepath, 'w') as f:
            json.dump(jobs_data, f, indent=2)
        print(f"💾 Saved {len(self.jobs)} jobs to {filepath}")
    
    def load_jobs(self, filepath='scheduler_jobs.json'):
        """Load jobs from file."""
        if not Path(filepath).exists():
            print("⚠️ No saved jobs found")
            return
        
        with open(filepath, 'r') as f:
            jobs_data = json.load(f)
        
        for job_data in jobs_data:
            if job_data['last_run']:
                job_data['last_run'] = datetime.fromisoformat(job_data['last_run'])
            if job_data['next_run']:
                job_data['next_run'] = datetime.fromisoformat(job_data['next_run'])
            self.jobs.append(job_data)
        
        print(f"📂 Loaded {len(jobs_data)} jobs from {filepath}")


# Simple interval-based scheduler for CLI
def run_scheduled(target, interval_minutes, mode='full', limit=100, is_user=False):
    """
    Run a scrape job on a schedule.
    
    Args:
        target: Subreddit or username
        interval_minutes: Minutes between runs
        mode: 'full', 'history', or 'monitor'
        limit: Post limit per run
        is_user: True if target is a user
    """
    from main import run_full_history
    
    prefix = "u/" if is_user else "r/"
    print(f"📅 Scheduled: {prefix}{target} every {interval_minutes} minutes")
    print("Press Ctrl+C to stop\n")
    
    run_count = 0
    
    try:
        while True:
            run_count += 1
            print(f"\n{'='*50}")
            print(f"🔄 Run #{run_count} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'='*50}")
            
            run_full_history(
                target,
                limit,
                is_user,
                download_media_flag=(mode == 'full'),
                scrape_comments_flag=(mode == 'full')
            )
            
            print(f"\n⏰ Next run in {interval_minutes} minutes...")
            time.sleep(interval_minutes * 60)
            
    except KeyboardInterrupt:
        print(f"\n\n🛑 Scheduler stopped after {run_count} runs")
