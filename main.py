from fastapi import FastAPI, Request, Header, Response, BackgroundTasks
import os
import requests
from fastapi.middleware.cors import CORSMiddleware
from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove, CallbackQuery
from fastapi.responses import HTMLResponse
from typing import Dict, List, Literal
from datetime import datetime, timedelta, timezone
import telegram
from telegram import constants
from pymongo import MongoClient
import string
import traceback
import json
from urllib.parse import urlparse, parse_qs, urlencode, quote
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from pymongo import MongoClient
from fastapi.templating import Jinja2Templates
import Fastbot as f
import noj as noj
import string
import os
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import random
import asyncio
from asyncio import Semaphore
import stripe
from openai import OpenAI
from dotenv import load_dotenv
import intelligence as intel
from langchain.chat_models import init_chat_model
from langchain_openai import ChatOpenAI

load_dotenv()
debugging = True #set to true to print all print statements for debugging

model = ChatOpenAI(model="gpt-4o-mini-2024-07-18")

class ExpectationBreak(BaseModel):
    breaks: Literal[True, False] = Field(
        None, description="Decision on if user breaks expectation set"
    )

expectationBreak = model.with_structured_output(ExpectationBreak)

class HandOver(BaseModel):
    chat_id: str
    event_id: str
    message: str
    expectation: str


# Token (Define all API tokens/credentials here) ___________
uri = "mongodb+srv://ticketit.jej2z.mongodb.net/?authSource=%24external&authMechanism=MONGODB-X509&retryWrites=true&w=majority&appName=TicketIT"
app = FastAPI()
mongo = MongoClient(uri,
                     tls=True,
                     tlsCertificateKeyFile='nm_db.pem')

ticketit_db = mongo['Ticketit']
users = ticketit_db['Users']
clients = ticketit_db['Clients']
tickets = ticketit_db['Tickets']
statistics = ticketit_db['Statistics']

origins = [
    'http://localhost:5173'
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#global non persistent variables
timeLog = {}


@app.post("/telegram/{client_id}")
async def echo(request: Request, client_id: str):
    inputTime = datetime.now()
    await f.printer(f"Input Time: {inputTime}", debugging)
    client = clients.find_one({'client_id': client_id}) #immediately get client info for their telegram_token
    if client is None:
        return {"status": "not ok"}
    event_id = client.get('active_event', None)
    f.bot = telegram.Bot(client['client_telegram_token']) #initialize the bot with the token

    await f.printer(f"Client ID: {client_id}", debugging)
    await f.printer(f"Event ID: {event_id}", debugging)


    try:
        update_data = await request.json()
        update = telegram.Update.de_json(update_data, f.bot)

        if update.message: # parsing input from user
            if update.message.text:
                chat_id = update.message.chat_id
                user_input = update.message.text
            elif update.message.contact:
                chat_id = update.message.chat_id
                user_input = update.message.contact.phone_number
            else:
                chat_id = update.message.chat_id
        elif update.callback_query:
            chat_id = update.callback_query.message.chat_id
            user_input = update.callback_query.data
        else:
            await f.send_text(chat_id, "Your message type isn't supported.")
            return {"status": "ok"}
        
        if chat_id not in timeLog:
            print("First input" + str(chat_id) + str(inputTime))
            timeLog[chat_id] = inputTime
        else:
            print("Repeated input" + str(chat_id) + str(inputTime))
            delta = inputTime - timeLog[chat_id]
            print("diff in time is " + str(delta))
            timeLog[chat_id] = inputTime
            if (delta).total_seconds() < 3:
                print("Ghost input detected. Ignoring.")
                return {"status": "ok"}
        
        if "/cancel" == user_input.lower() or "/end" == user_input.lower():
            await f.send_text(chat_id, "You have cancelled your current opeation. Please press /start to start again.")
            await f.reset_all({"chat_id": chat_id, "event_id": event_id})
            return {"status": "ok"}

        await f.printer("State management begins here", debugging)

        user = users.find_one({'sid.telegram': chat_id})

        if user is not None:
            cd = client_id #re-referencing client_id to increse performance
            if event_id not in user['client_customer_relation']: #logic to check if user is new to the particular bot
                new_user = {
                    "identity": "new", #2 identifiers. new or repeat. new is synonymous with lead and repeat is synonymous with customer
                    "info_payload": {},
                    "state": ["/start", 0], #we should look into making this a tree to entertain 2 completely different lines of questioning
                    "validator": ["any", []],
                    "payload_collector": None,
                }
                users.update_one({'sid.telegram': chat_id}, {'$set': {f'client_customer_relation.{event_id}': new_user}})
                user['client_customer_relation'][event_id] = new_user
                await f.incrementEventStats('new',cd, event_id, ['leadCount'])
                await f.appendEventStats('new', cd, event_id, ['leads'], user['_id']) #these 2 lines can be abtracted down further but lets keep it here for now
            elif user_input == "/start": #this is to set the identity of the user to see if he is recurring or new for analytics / dashboard purposes.
                if client['_id'] in user['pastClients']:
                    identity = "repeat" 
                    user['client_customer_relation'][event_id]['identity'] = identity
                    users.update_one({'sid.telegram': chat_id}, {'$set': {f'client_customer_relation.{event_id}.identity': identity}})
                    await f.incrementEventStats('repeat', cd, event_id, ['recLeadsCount'])
                    await f.appendEventStats('repeat', cd, event_id, ['recLeads'], user['_id'])
                else:
                    await f.incrementEventStats('new',cd, event_id, ['leadCount'])
                    await f.appendEventStats('new', cd, event_id, ['leads'], user['_id']) #these 2 lines can be abtracted down further but lets keep it here for now
            else:
                pass
            
            expectation = "only a valid name"
            expectationStatus: ExpectationBreak = expectationBreak.invoke(
                f"""
                Expectation:{expectation}
                User Input:{user_input}
                """)
            
            if expectationStatus.breaks: 
                await f.send_text(chat_id, "TicketIT Intelligence taking over")
                response = await intel.intelligenceTakeOver(HandOver(chat_id=str(chat_id), event_id=event_id, message=user_input, expectation=expectation))
                #await f.send_text(chat_id, response)
                return {"status": "ok"}
            
            context = await f.generate_context(chat_id, client, user_input, user, f)
            await f.printer('context generated and now calling state manager', debugging)
            await f.state_manager(context)
            await f.printer("State management ends here", debugging)

        else:
            random_id = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
            new_user = {
                "_id": f"{random_id}",
                "sid": {
                    "telegram": chat_id
                },
                "client_customer_relation": {
                    f"{event_id}": {
                        "identity": "new",
                        "info_payload": {},
                        "state" : ["/start", 0],
                        "validator": ["any", []],
                        "payload_collector": None
                    }
                },
                "profile": {"profile_retrieval_permission": False, "flag": False},
                "transactions": {},
                "pastClients": []          
            }
            users.insert_one(new_user)
            await f.incrementEventStats('new',client['_id'], event_id, ['leadCount'])
            await f.appendEventStats('new', event_id, ['leads'], user['_id']) #these 2 lines can be abtracted down further but lets keep it here for now
            await f.genesis({'chat_id':chat_id, 'client': client, 'event_id': event_id })
    except Exception as e:
        print(f"An error occurred with incoming object in Main.py: {e}")
        await f.send_text(chat_id, "An error occurred. Please try again soon. If the problem persists, please contact support @nm35x. Thanks!")
        #await f.reset_all({"chat_id": chat_id, "event_id": event_id})
        #there should be a way to log this error to a log file to our internal tools
        return {"status": "not ok"}
    return {"status": "ok"}


@app.post("/stripe")
async def webhook_received(request: Request, background_tasks: BackgroundTasks, stripe_signature: str = Header(None)):
    data = await request.body()
    response = JSONResponse(content={"status": "success"})
    try:
        event = stripe.Webhook.construct_event(
            payload=data,
            sig_header=stripe_signature,
            secret=os.environ['webhook_key']
        )
        event_data = event['data']
        f.bot = telegram.Bot(event_data['object']['metadata']['telegram_token']) #initialize the bot with the token
    except Exception as e:
        print(e)
        return {"status": "ok"}
    
    try:
        debugging = False
        await f.printer("Webhook received", debugging)
        await f.printer(event_data['object'], debugging)
        amount = event_data['object']['amount_total'] / 100
        user_reference_id = event_data['object']['client_reference_id']
        stripe_id = event_data['object']['payment_intent']
        status = event_data['object']['status']
        event_id = event_data['object']['metadata']['event_id']
        bookingID = event_data['object']['metadata']['bookingID']
        user = users.find_one({'_id': user_reference_id}) #user info
        client = clients.find_one({'active_event': event_id}) #client info
        await f.printer(user, debugging)
        chat_id = user['sid']['telegram']
        if not user: 
            return response
        try:
            if status == 'complete':
                await f.send_text(chat_id, f"<b>Payment of ${amount} received!</b>\n<b>Payment ID:</b> {stripe_id}\n🎫 Generating your tickets...\n<b>PLEASE WAIT\n<i>If there is any issue use /contact</i></b>")
                try:
                    # Set a timeout for context generation
                    context = await asyncio.wait_for(
                        f.generate_context(chat_id, client, None, user, f),
                        timeout=10  # Timeout in seconds
                    )
                    await f.printer("Context generated successfully", debugging)
                    await f.printer(context, debugging)
                except asyncio.TimeoutError:
                    context = None  # Fallback if context generation times out
                    print(f"Warning: generate_context timed out for chat_id {chat_id}")
                except Exception as e:
                    context = None  # Fallback if any other error occurs
                    print(f"Error: generate_context failed for chat_id {chat_id}: {e}")
            
                # Ensure context is valid before proceeding
                if context is not None:
                    await f.printer("Processing payment...", debugging) 
                    transactionInfo = await f.process_payment_async(amount, stripe_id, bookingID, context)
                    await f.printer(transactionInfo, debugging)
                    await f.send_text(chat_id, f"<b>Thank you for your purchase! 🥳🙏</b>\n\n#️⃣ <b>Your Booking ID:</b> {bookingID}\n\n✅ <i>You have successfully booked {transactionInfo['qty']} tickets of {transactionInfo['ticket_type']} for ${amount}.</i>\n\n⚠️ <i>Please save and keep the above QR codes safe and only display it upon entry.</i>\n\n🔍 You may view your tickets again at\n/view_tickets.\n\nPress /buy to buy more tickets to {client['events'][event_id]['event_name']}!\n\n<b>See you soon ❤️‍🔥</b>")
                    users.update_one({'_id': user['_id']}, {'$push': {'pastClients': client['_id']}})
                    try:
                        count = -1 if user['client_customer_relation'][event_id]['info_payload'].get('promocode', None) is not None else 0
                        customArr = ['leadCount', 'newCustomerCount', 'newCustomers', 'leads'] if user['client_customer_relation'][event_id].get('identity', 'new') == 'new' else ['recLeadsCount', 'recCustomerCount', 'recCustomers', 'recLeads']
                        statistics.update_one({'client_id': client['client_id'], 'event_id': event_id}, {'$inc': { f'ticketTypes.{transactionInfo['ticket_type']}': transactionInfo['qty'], 
                                                                                                                    'revenue': amount, 
                                                                                                                    customArr[0]: -1,
                                                                                                                    customArr[1]: 1,
                                                                                                                    'voucherUnused' : count
                                                                                                                    }})
                        await f.appendEventStats('new', client['client_id'], event_id, [customArr[2]], user['_id'])
                        await f.removeEventStats(client['client_id'], event_id, [customArr[3]], user['_id'])
                    except Exception as e:
                        print(f"Error updating statistics for chat_id {chat_id}: {e}")
                    await f.reset_all({"chat_id": chat_id, "event_id": event_id})
                else:
                    await f.send_text(chat_id, "⚠️ An error occurred while generating your tickets. Please contact support.")
        except Exception as e:
            # Log or handle the error globally
            print(f"Error processing payment for chat_id {chat_id}: {e}")

    except Exception as e:
        print(f"An error occurred: {e}")
        return response
