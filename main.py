# Hello, provider testing
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
from mangum import Mangum
from config import Config
from bot_handlers import handle_message, handle_update
import logging


# Import your custom modules if they are compatible with AWS Lambda
# Ensure that 'config' and 'bot_handlers' are included in your deployment package
# from config import Config
# from bot_handlers import handle_message

app = FastAPI()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.get("/")
async def index():
    return PlainTextResponse("Welcome to the Audio Transcribe Bot!")

@app.post("/webhook")
async def webhook(request: Request):
    try:
        update = await request.json()
        logger.info(f"Received update: {update}")
        handle_update(update)
        return JSONResponse({'status': 'ok'})
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return JSONResponse({'status': 'error', 'message': str(e)}, status_code=500)

@app.get("/webhook")
async def webhook_get():
    return PlainTextResponse(
        "Webhook is working. Send a POST request with a Telegram update to use the bot.",
        status_code=200
    )
# AWS Lambda handler using Mangum
# handler = Mangum(app) # if using AWS Lambda

