from fastapi.responses import HTMLResponse, RedirectResponse
import stripe
from fastapi import FastAPI, HTTPException
from pydantic_settings import BaseSettings
import os
from uuid import uuid4
from stripe_recorder.recorded import get_recorded_path
from json import dumps as json_dumps

app = FastAPI()

class Settings(BaseSettings):
    STRIPE_API_KEY: str
    STRIPE_WEBHOOK_SECRET: str

settings = Settings(_env_file=".env")
stripe.api_key = settings.STRIPE_API_KEY

SESSION_TYPE : str | None = None
SESSION_PATH = get_recorded_path(f"{uuid4()}")

# Representative products
PRODUCT_IDS = {
    "subscription": "price_1RPpoIRGAudMahWRkfjEf4xl",
    "one_time": "price_1RPs8ZRGAudMahWRPpKlesnE"
}

@app.post("/webhook")
async def record_stripe_event(stripe_event: dict):
    full_session_path = SESSION_PATH / str(SESSION_TYPE)
    full_session_path.mkdir(parents=True, exist_ok=True)

    current_items = list(full_session_path.glob("*.json"))
    new_event_path = full_session_path / f"{len(current_items)}_{stripe_event['type']}.json"

    new_event_path.write_text(json_dumps(stripe_event, indent=4))

    # Additional processing to grab related objects
    if stripe_event["type"] == "checkout.session.completed":
        stripe_checkout_id = stripe_event["data"]["object"]["id"]
        session_line_items = stripe.checkout.Session.list_line_items(
          stripe_checkout_id,
          api_key=settings.STRIPE_API_KEY
        )
        line_item_path = new_event_path.with_suffix(".extra.line_items.json")
        line_item_path.write_text(json_dumps(session_line_items, indent=4))

@app.get("/")
def home():
    return HTMLResponse(
        """
        <html>
            <body>
                <div><a href="/subscribe">Subscribe</a></div>
                <div><a href="/buy_product">Buy Product</a></div>
            </body>
        </html>
        """
    )

@app.get("/success")
def success():
    return "Success"

@app.get("/cancel")
def cancel():
    return "Cancel"

@app.get("/subscribe")
def create_subscription():
    global SESSION_TYPE
    SESSION_TYPE = "subscription"

    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price": PRODUCT_IDS["subscription"],
                    "quantity": 1,
                }
            ],
            mode="subscription",
            success_url="http://127.0.0.1:5084/success",
            cancel_url="http://127.0.0.1:5084/cancel",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    assert checkout_session.url
    return RedirectResponse(
        url=checkout_session.url,
    )

@app.get("/buy_product")
def buy_product():
    global SESSION_TYPE
    SESSION_TYPE = "one_time"

    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price": PRODUCT_IDS["one_time"],
                    "quantity": 1,
                }
            ],
            # Mirror the fact that we will pre-create a customer
            customer_creation="always",
            mode="payment",
            success_url="http://127.0.0.1:5084/success",
            cancel_url="http://127.0.0.1:5084/cancel",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    assert checkout_session.url
    return RedirectResponse(
        url=checkout_session.url,
    )
