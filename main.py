from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import os
from pydantic import BaseModel
import json


FRESHDESK_API_KEY=""
POLLING_INTERVAL=""
# # Configuration class
# class Settings(BaseSettings):
#     FRESHDESK_DOMAIN: str
#     FRESHDESK_API_KEY: str
#     POLLING_INTERVAL: int = 300 
    
#     class Config:
#         env_file = ".env"

# # Initialize settings
# settings = Settings()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('freshdesk_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Freshdesk Ticket Monitor")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ticket model
class Ticket(BaseModel):
    id: int
    subject: str
    status: int
    priority: int
    created_at: str
    updated_at: str

# Global state to track the monitoring task
monitor_task: Optional[asyncio.Task] = None
is_monitoring = False

async def process_ticket(ticket: Dict) -> None:
    """
    Process a single ticket and perform necessary operations.
    Customize this function based on your requirements.
    """
    try:
        # Example processing logic
        ticket_id = ticket['id']
        status = ticket['status']
        priority = ticket['priority']

        # Add your custom processing logic here
        # For example, you might want to:
        # 1. Update ticket priority based on certain conditions
        # 2. Add notes or comments
        # 3. Assign to specific agents
        # 4. Update custom fields

        if status == 2 and priority < 3:  # Example condition
            await update_ticket(ticket_id, {"priority": 3})
            logger.info(f"Updated priority for ticket {ticket_id}")

    except Exception as e:
        logger.error(f"Error processing ticket {ticket.get('id')}: {str(e)}")

async def update_ticket(ticket_id: int, updates: Dict) -> None:
    """
    Update a ticket in Freshdesk with the given updates.
    """
    async with httpx.AsyncClient() as client:
        url = f"https://{settings.FRESHDESK_DOMAIN}/api/v2/tickets/{ticket_id}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Basic {FRESHDESK_API_KEY}"
        }
        
        try:
            response = await client.put(url, json=updates, headers=headers)
            response.raise_for_status()
            logger.info(f"Successfully updated ticket {ticket_id}")
        except Exception as e:
            logger.error(f"Error updating ticket {ticket_id}: {str(e)}")
            raise

async def fetch_tickets() -> List[Dict]:
    """
    Fetch tickets from Freshdesk API.
    """
    async with httpx.AsyncClient() as client:
        url = f"https://{settings.FRESHDESK_DOMAIN}/api/v2/tickets"
        headers = {
            "Authorization": f"Basic {FRESHDESK_API_KEY}"
        }
        
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching tickets: {str(e)}")
            return []

async def monitor_tickets():
    """
    Continuous monitoring function that runs in the background.
    """
    global is_monitoring
    
    while is_monitoring:
        try:
            logger.info("Fetching tickets...")
            tickets = await fetch_tickets()
            
            for ticket in tickets:
                await process_ticket(ticket)
            
            logger.info(f"Processed {len(tickets)} tickets")
            
        except Exception as e:
            logger.error(f"Error in monitoring loop: {str(e)}")
        
        # Wait for the configured polling interval
        await asyncio.sleep(POLLING_INTERVAL)

@app.on_event("startup")
async def startup_event():
    """
    Initialize the monitoring task on startup.
    """
    global monitor_task, is_monitoring
    
    if not is_monitoring:
        is_monitoring = True
        monitor_task = asyncio.create_task(monitor_tickets())
        logger.info("Ticket monitoring started")

@app.on_event("shutdown")
async def shutdown_event():
    """
    Clean up the monitoring task on shutdown.
    """
    global monitor_task, is_monitoring
    
    if is_monitoring:
        is_monitoring = False
        if monitor_task:
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("Ticket monitoring stopped")

@app.get("/status")
async def get_status():
    """
    Get the current status of the monitoring service.
    """
    return {
        "is_monitoring": is_monitoring,
        "last_check": datetime.now().isoformat(),
        "polling_interval": POLLING_INTERVAL
    }

@app.post("/start")
async def start_monitoring():
    """
    Start the monitoring service if it's not already running.
    """
    global monitor_task, is_monitoring
    
    if is_monitoring:
        raise HTTPException(status_code=400, detail="Monitoring is already running")
    
    is_monitoring = True
    monitor_task = asyncio.create_task(monitor_tickets())
    return {"status": "Monitoring started"}

@app.post("/stop")
async def stop_monitoring():
    """
    Stop the monitoring service if it's running.
    """
    global monitor_task, is_monitoring
    
    if not is_monitoring:
        raise HTTPException(status_code=400, detail="Monitoring is not running")
    
    is_monitoring = False
    if monitor_task:
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass
    
    return {"status": "Monitoring stopped"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)