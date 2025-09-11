from fastapi import FastAPI, Request, Header, Response, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import re
import os
import requests
import json
from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove, CallbackQuery, constants
from datetime import datetime, timedelta
from typing import Dict, List
import time
import telegram
from urllib.parse import urlparse, parse_qs, urlencode, quote
from pymongo import MongoClient
import Fastbot as f
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing_extensions import Literal
import getpass
from langchain.chat_models import init_chat_model
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langgraph.graph import MessagesState
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage

load_dotenv()

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


# Token (Define all API tokens/credentials here) ___________
model = ChatOpenAI(model="gpt-4o-mini-2024-07-18")

#expectation and state model
class ExpectationandState(BaseModel):
    breakExpectation: bool = Field(description="whether the provided input breaks the provided expectation")
    state: Literal['ENQUIRY', 'BUYING', 'SETTINGS'] = Field(description="the current state of the user depending on what the user has input and is trying to do")
    confidenceLevel: int = Field(description="confidence level in the evaluation")

esEvaluator = model.with_structured_output(ExpectationandState)

class HandOver(BaseModel):
    chat_id: str
    event_id: str
    message: str
    expectation: str


async def updateNOJState(chat_id: str, event_id: str, state: str):
    "Call this function once you finish all the necessary updates to the info payload"
    return

async def updateInfoPayload(chat_id: str, event_id:str, toUpdate: Literal['collectname', 'collectphonenumber', 'collectemail'], value: str):
    "Updates the infopayload of the specific user with their chat_id and event_id in the 'toUpdate' field with the 'value' provided"

    print(f"context: {chat_id}, {event_id}, {toUpdate}, {value}")
    print(f"client_customer_relation.{event_id}.info_payload.{toUpdate}")
    filter = {
        "sid.telegram": int(chat_id),
    }
    update = {
        "$set": {
            f"client_customer_relation.{event_id}.info_payload.{toUpdate}": value
        }
    }
    users.update_one(filter, update)
    print(f"Info payload updated with {toUpdate} as {value}")


async def RespondToUser(chat_id: str, event_id: str, input: str):
    "Answers the user's enquiry and and prompts them to buy tickets and retrieve information using tools if necessary"
    try:
        await f.send_text(chat_id, input)
    except Exception as e:
        print(f"Error: {e}")
        

tool_calls = [updateInfoPayload, RespondToUser, updateNOJState]
trixie = model.bind_tools(tool_calls)

async def intelligenceTakeOver(context: HandOver) -> bool:
    response = trixie.invoke(
    f"""
    This user was expected to input {context.expectation} but instead input {context.message}.

    Direct the user back to answer {context.expectation} and provide a response to the user.

    If the user provided more data than the expectation, refer to the info payload and update the payload with the all the new data, and call updateNOJState.
    If you call updateNOJState, do not call RespondToUser.

    If the user makes an enquiry, answer the enquiry and retrieve information using tools if necceasry.

    Context:
    Chat ID: {context.chat_id}
    event ID: {context.event_id}
    """)
    print('\n\n\n')
    print(response.additional_kwargs['tool_calls'])
    for call in response.additional_kwargs['tool_calls']:
        arguments = call['function']['arguments']
        arguments_dict = json.loads(arguments)  
        functionCall = call['function']['name']
        print("\n")
        print(f"Calling {functionCall} with {arguments}")
        print("\n")
        print(f"Arguments: {arguments_dict}")
        function = globals()[functionCall]
        await function(**arguments_dict)
              
    return True
