# TicketIT

TicketIT is a chatbot system built on top of an in-house abstraction framework called **NOJ**, designed to make chatbot development more structured and state-driven. The system demonstrates how to manage chatbot states effectively while integrating with the **Telegram API** for the user interface.

---

## ✨ Features

- **State-Driven Design** – Every chatbot interaction is modeled as a deterministic sequence of states  
- **Custom Abstractions (NOJ)** – Functional-programming-inspired framework for chatbot construction  
- **Payment Support** – Integrated with Stripe for ticket sales  
- **Extensible Architecture** – Validators, payload collectors, and profile retrieval modules for adaptability  
- **Telegram Integration** – Works seamlessly with Telegram bots created via [@BotFather](https://t.me/BotFather)  

---

## ⚡ Getting Started

### Requirements

- AWS account with **S3** and **Lambda** permissions  
- Docker (for local MongoDB)  
- ngrok (for webhook port forwarding)  
- A `.pem` MongoDB connection file (`nm_db.pem`)  

### Environment Variables

Create a `.env` file and add the following keys:

ACCESS_KEY_LAMBDA=
OPENAI_API_KEY=
qrscanner= # password for scanner
REGION_LAMBDA=
SECRET_KEY_LAMBDA=
stripe_key=
webhook_key= # for Stripe API
MISTRAL_API_KEY=


### Running Locally

1. Spin up MongoDB (recommended via Docker for speed).  
2. Place `nm_db.pem` in the repo root for secure MongoDB access.  
3. Start **ngrok** to expose your localhost.  
4. Register webhooks:
   - **Stripe webhook** → points to your server  
   - **Telegram webhook** → points to your server (set up via @BotFather)  

---

## 🛠️ High-Level Design

TicketIT uses **NOJ**, a state-based abstraction for chatbot design.  

- **State Invariant** – At any point, a chatbot is always in a defined state  
- **Each State**:
  - Expects an input  
  - Runs a handler function (`handlingFn`)  
  - Returns true/false  
  - Optionally sends an output  

A state is represented as:

[conversation flow, conversation stage]


### Example

Conversation: `/buy`

[genesis, collecttickettype, collectname, collectgender, collectdob, confirmation, collectticketqty, paymentpending]



If a user is at **confirmation**:

["/buy", 5]


The **stateManager** acts as a router: it determines what state the user is in, then forwards execution to `handleState`.  

---

## 📦 Supporting Modules

- **payloadCollector** – Captures and stores user inputs into an `infoPayload` (grouped by eventId)  
- **Validator** – Ensures state inputs are valid, defined as:  

[validatorType, [dependencies]]


- **profileRetrieval** – TicketIT-specific module for fetching static user metadata from the DB (extendable to other use cases)  

---

## 📧 Contact

For questions or suggestions: [nihaalmanaf@gmail.com](mailto:nihaalmanaf@gmail.com)
